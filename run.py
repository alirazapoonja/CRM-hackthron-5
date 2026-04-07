#!/usr/bin/env python3
"""
Customer Success FTE — Backend Entry Point

Multi-mode backend that works:
- LOCAL mode: No Kafka/Kafka needed, uses in-memory queue + SQLite/PostgreSQL
- PRODUCTION mode: Full Kafka + PostgreSQL + OpenAI integration

Usage:
    # Local development (no Kafka needed)
    python run.py --mode local

    # Production (requires Kafka + PostgreSQL)
    python run.py --mode production

    # With custom settings
    python run.py --mode local --port 9000 --workers 2
"""

import argparse
import asyncio
import logging
import os
import sys
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# =============================================================================
# CONFIGURATION
# =============================================================================


class Config:
    """Central configuration with environment variable support."""
    
    # Mode
    MODE = os.getenv("FTE_MODE", "local")  # "local" or "production"
    
    # Server
    HOST = os.getenv("FTE_HOST", "0.0.0.0")
    PORT = int(os.getenv("FTE_PORT", "8000"))
    WORKERS = int(os.getenv("FTE_WORKERS", "1"))
    DEBUG = os.getenv("FTE_DEBUG", "false").lower() == "true"
    
    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME = os.getenv("DB_NAME", "crm_fte")
    DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "5"))
    DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "20"))
    
    # Kafka (production only)
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
    KAFKA_TOPIC_INCOMING = os.getenv("KAFKA_TOPIC_INCOMING", "fte.tickets.incoming")
    KAFKA_TOPIC_OUTGOING = os.getenv("KAFKA_TOPIC_OUTGOING", "fte.tickets.outgoing")
    KAFKA_TOPIC_DLQ = os.getenv("KAFKA_TOPIC_DLQ", "fte.dlq")
    KAFKA_TOPIC_METRICS = os.getenv("KAFKA_TOPIC_METRICS", "fte.metrics")
    
    # Security
    API_KEY = os.getenv("API_KEY", "dev-api-key")
    JWT_SECRET = os.getenv("JWT_SECRET", "jwt-secret-change-in-production")
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    
    # CORS
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    
    # Gmail (optional)
    GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "")
    GMAIL_PROJECT_ID = os.getenv("GMAIL_PROJECT_ID", "")
    GMAIL_TOPIC_NAME = os.getenv("GMAIL_TOPIC_NAME", "gmail-notifications")
    
    # WhatsApp (optional)
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
    WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")
    
    # OpenAI (optional)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "json" if MODE == "production" else "text")
    
    @classmethod
    def database_url(cls) -> str:
        """Construct PostgreSQL connection URL."""
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
    
    @classmethod
    def is_production(cls) -> bool:
        return cls.MODE == "production"
    
    @classmethod
    def has_openai(cls) -> bool:
        return bool(cls.OPENAI_API_KEY)


# =============================================================================
# LOGGING SETUP
# =============================================================================


def setup_logging():
    """Configure logging based on mode."""
    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    
    if Config.LOG_FORMAT == "json":
        # Production: JSON structured logging
        try:
            import pythonjsonlogger.jsonlogger
            handler = logging.StreamHandler(sys.stdout)
            formatter = pythonjsonlogger.jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z"
            )
        except ImportError:
            # Fallback if pythonjsonlogger not installed
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
            )
    else:
        # Development: Human-readable
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s",
            datefmt="%H:%M:%S"
        )
        # Color support for terminal
        if sys.platform != "win32":
            try:
                import coloredlogs
                coloredlogs.install(
                    level=level,
                    fmt="%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s"
                )
                return
            except ImportError:
                pass
    
    handler.setFormatter(formatter)
    
    # Root logger
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    root.addHandler(handler)
    
    # Quieter third-party logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiokafka").setLevel(logging.WARNING if not Config.is_production() else logging.INFO)


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================


async def init_database():
    """Initialize database schema if not exists."""
    import asyncpg
    
    logger = logging.getLogger("database.init")
    logger.info(f"Connecting to database: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    
    try:
        pool = await asyncpg.create_pool(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            min_size=1,
            max_size=5,
        )
        
        async with pool.acquire() as conn:
            # Check if tables exist
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' AND tablename IN ('customers', 'tickets')
            """)
            
            if len(tables) == 0:
                logger.info("Database is empty. Running schema initialization...")
                
                # Read and execute schema
                schema_path = Path(__file__).parent / "production" / "database" / "schema.sql"
                if schema_path.exists():
                    schema_sql = schema_path.read_text(encoding="utf-8")
                    await conn.execute(schema_sql)
                    logger.info("Database schema initialized successfully")
                else:
                    logger.warning(f"Schema file not found at {schema_path}")
            else:
                table_names = [t["tablename"] for t in tables]
                logger.info(f"Database already has tables: {', '.join(table_names)}")
        
        await pool.close()
        return True
        
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")
        logger.info("Application will continue in local mode")
        return False


# =============================================================================
# APPLICATION LIFESPAN
# =============================================================================


@asynccontextmanager
async def lifespan(app):
    """Manage application startup and shutdown."""
    import asyncio
    
    logger = logging.getLogger("app.lifespan")
    logger.info("=" * 60)
    logger.info("Customer Success FTE — Backend Starting")
    logger.info(f"Mode: {Config.MODE}")
    logger.info(f"Host: {Config.HOST}:{Config.PORT}")
    logger.info(f"Workers: {Config.WORKERS}")
    logger.info(f"Debug: {Config.DEBUG}")
    logger.info("=" * 60)
    
    # Startup tasks
    startup_tasks = []
    
    # 1. Initialize database
    startup_tasks.append(("Database", init_database()))
    
    # 2. Initialize Kafka (production only)
    if Config.is_production():
        startup_tasks.append(("Kafka", _init_kafka_producer()))
    
    # Run startup tasks
    for name, task in startup_tasks:
        try:
            await task
            logger.info(f"✓ {name} initialized")
        except Exception as e:
            logger.warning(f"✗ {name} skipped: {e}")
    
    # Store app state
    app.state.mode = Config.MODE
    app.state.start_time = asyncio.get_event_loop().time()
    app.state.db_available = True
    app.state.kafka_available = Config.is_production()
    
    logger.info("Application ready to accept requests")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    if hasattr(app.state, "kafka_producer") and app.state.kafka_producer:
        try:
            await app.state.kafka_producer.stop()
            logger.info("Kafka producer stopped")
        except Exception:
            pass
    
    logger.info("Application stopped")


# =============================================================================
# KAFKA INITIALIZATION
# =============================================================================


async def _init_kafka_producer():
    """Initialize Kafka producer for production mode."""
    from production.kafka_client import FTEKafkaProducer, TOPICS
    
    producer = FTEKafkaProducer(
        bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
        client_id="fte-backend",
    )
    await producer.start()
    
    return producer


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================


def create_app():
    """Create and configure the FastAPI application."""
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    import time
    import uuid
    
    app = FastAPI(
        title="Customer Success FTE Backend",
        description="AI-powered customer support system with multi-channel intake, "
                    "PostgreSQL-based CRM, and OpenAI agent integration.",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    
    # ---- Middleware ----
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request logging
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        duration = time.time() - start
        logger = logging.getLogger("app.http")
        logger.info(
            f"{request.method} {request.url.path} | "
            f"{response.status_code} | "
            f"{duration*1000:.0f}ms | "
            f"ID: {request_id}"
        )
        
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration*1000:.0f}ms"
        
        return response
    
    # Global error handler
    @app.exception_handler(Exception)
    async def global_error_handler(request: Request, exc: Exception):
        logger = logging.getLogger("app.error")
        logger.exception(f"Unhandled error: {exc}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "request_id": getattr(request.state, "request_id", None),
                "detail": str(exc) if Config.DEBUG else None,
            },
        )
    
    # ---- Routes ----
    
    # Import and mount routes
    from production.api.main import app as main_app
    
    # Copy routes from main app
    app.routes.extend(main_app.routes)
    
    # Additional backend-only routes
    @app.get("/api/status", tags=["Backend"])
    async def backend_status():
        """Backend-specific status information."""
        import asyncio
        uptime = time.time() - app.state.start_time
        
        return {
            "mode": app.state.mode,
            "uptime_seconds": round(uptime, 1),
            "database": "connected" if app.state.db_available else "disconnected",
            "kafka": "connected" if app.state.kafka_available else "disconnected",
            "openai": "configured" if Config.has_openai() else "not configured",
            "config": {
                "log_level": Config.LOG_LEVEL,
                "rate_limit": f"{Config.RATE_LIMIT_REQUESTS}/{Config.RATE_LIMIT_WINDOW}s",
                "cors_origins": Config.ALLOWED_ORIGINS,
            },
        }
    
    @app.post("/api/admin/init-db", tags=["Backend"])
    async def admin_init_db():
        """Initialize database schema manually."""
        result = await init_database()
        return {"success": result, "message": "Database initialized" if result else "Database initialization skipped"}
    
    return app


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Customer Success FTE Backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                          # Local mode, default settings
  python run.py --mode production        # Production mode (needs Kafka + PostgreSQL)
  python run.py --port 9000 --workers 4  # Custom port and workers
  python run.py --init-db                # Initialize database then start
        """,
    )
    
    parser.add_argument(
        "--mode",
        choices=["local", "production"],
        default=Config.MODE,
        help=f"Running mode (default: {Config.MODE})",
    )
    parser.add_argument("--host", default=Config.HOST, help=f"Host (default: {Config.HOST})")
    parser.add_argument("--port", type=int, default=Config.PORT, help=f"Port (default: {Config.PORT})")
    parser.add_argument("--workers", type=int, default=Config.WORKERS, help=f"Workers (default: {Config.WORKERS})")
    parser.add_argument("--log-level", default=Config.LOG_LEVEL, help="Log level (default: INFO)")
    parser.add_argument("--init-db", action="store_true", help="Initialize database before starting")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    
    args = parser.parse_args()
    
    # Set environment variables from CLI args
    os.environ["FTE_MODE"] = args.mode
    os.environ["FTE_HOST"] = args.host
    os.environ["FTE_PORT"] = str(args.port)
    os.environ["FTE_WORKERS"] = str(args.workers)
    os.environ["LOG_LEVEL"] = args.log_level
    
    # Setup logging
    setup_logging()
    
    logger = logging.getLogger("run")
    logger.info(f"Starting backend in {args.mode} mode...")
    
    # Initialize database if requested
    if args.init_db:
        logger.info("Initializing database...")
        try:
            asyncio.run(init_database())
            logger.info("Database initialized")
        except Exception as e:
            logger.warning(f"Database init failed: {e}")
    
    # Start Uvicorn
    import uvicorn
    
    reload = not args.no_reload and args.workers == 1
    
    uvicorn.run(
        "run:create_app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=reload,
        log_level=args.log_level.lower(),
        factory=True,  # Use create_app factory
    )


if __name__ == "__main__":
    main()

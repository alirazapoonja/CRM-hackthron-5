"""
FastAPI Service for Customer Success FTE.

This is the main API service that handles:
- Webhook endpoints for Gmail and WhatsApp
- Web form submissions
- Customer and conversation lookups
- Channel metrics
- Health checks

Architecture:
- FastAPI application with CORS middleware
- Async endpoint handlers
- Kafka integration for event streaming
- Database integration for lookups
- Graceful startup/shutdown
"""

import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, status, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from production.channels.gmail_handler import GmailHandler, GmailPollingHandler
from production.channels.whatsapp_handler import WhatsAppHandler, create_whatsapp_webhook_router
from production.channels.web_form_handler import (
    WebFormHandler,
    create_web_form_router,
    SupportFormSubmission,
    SupportFormResponse,
    TicketStatusResponse,
    initialize_web_form_handler,
    get_web_form_handler,
)

from production.kafka_client import (
    FTEKafkaProducer,
    FTEKafkaClient,
    TOPICS,
    KafkaEvent,
    EventType,
)

from production.database.queries import (
    get_customer_by_id,
    get_customer_history,
    get_conversation,
    get_conversation_messages,
    get_ticket,
    get_open_tickets,
    get_aggregate_metrics,
    health_check as db_health_check,
    get_db_pool,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Environment variables
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "crm_fte")

# Gmail config
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "")
GMAIL_PROJECT_ID = os.getenv("GMAIL_PROJECT_ID", "")
GMAIL_TOPIC_NAME = os.getenv("GMAIL_TOPIC_NAME", "gmail-notifications")

# WhatsApp config
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")

# Security
API_KEY = os.getenv("API_KEY", "dev-api-key")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")

# =============================================================================
# GLOBAL STATE
# =============================================================================

# These are initialized on startup
kafka_producer: Optional[FTEKafkaProducer] = None
gmail_handler: Optional[GmailHandler] = None
whatsapp_handler: Optional[WhatsAppHandler] = None
web_form_handler: Optional[WebFormHandler] = None

# Security scheme
security = HTTPBearer(auto_error=False)

# =============================================================================
# PYDANTIC MODELS
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall health status")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(..., description="API version")
    services: Dict[str, bool] = Field(..., description="Individual service health")


class CustomerLookupResponse(BaseModel):
    """Customer lookup response."""
    customer_id: str
    email: Optional[str]
    phone: Optional[str]
    name: Optional[str]
    created_at: str
    conversation_count: int = 0
    ticket_count: int = 0


class ConversationLookupResponse(BaseModel):
    """Conversation lookup response."""
    conversation_id: str
    customer_id: str
    initial_channel: str
    started_at: str
    ended_at: Optional[str]
    status: str
    message_count: int = 0
    ticket_id: Optional[str]


class ChannelMetricsResponse(BaseModel):
    """Channel metrics response."""
    channel: str
    total_messages: int
    messages_inbound: int
    messages_outbound: int
    avg_response_time_ms: float
    resolution_rate: float
    escalation_rate: float
    period_start: str
    period_end: str


class WebhookResponse(BaseModel):
    """Webhook processing response."""
    success: bool
    message_id: Optional[str]
    ticket_id: Optional[str]
    status: str


# =============================================================================
# LIFESPAN MANAGER
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan - startup and shutdown.

    This is where we initialize all handlers, connections, and resources.
    All initializations are non-blocking for local development.
    """
    # STARTUP
    logger.info("Starting Customer Success FTE API...")

    global kafka_producer, gmail_handler, whatsapp_handler, web_form_handler

    # Initialize Kafka producer (non-blocking with timeout)
    try:
        logger.info("Initializing Kafka producer...")
        kafka_producer = FTEKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            client_id="fte-api",
        )
        await asyncio.wait_for(kafka_producer.start(), timeout=5.0)
        logger.info("Kafka producer initialized")
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Kafka producer not available (local dev mode): {e}")
        kafka_producer = None

    # Initialize Gmail handler (if configured)
    if GMAIL_CREDENTIALS_PATH and GMAIL_PROJECT_ID:
        try:
            logger.info("Initializing Gmail handler...")
            gmail_handler = GmailHandler(
                credentials_path=GMAIL_CREDENTIALS_PATH,
                project_id=GMAIL_PROJECT_ID,
                topic_name=GMAIL_TOPIC_NAME,
            )
            await asyncio.wait_for(gmail_handler.setup_push_notifications(), timeout=10.0)
            logger.info("Gmail handler initialized")
        except Exception as e:
            logger.warning(f"Gmail handler initialization failed: {e}")
            gmail_handler = None
    else:
        logger.info("Gmail handler not configured (skipping)")

    # Initialize WhatsApp handler (if configured)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            logger.info("Initializing WhatsApp handler...")
            whatsapp_handler = WhatsAppHandler(
                account_sid=TWILIO_ACCOUNT_SID,
                auth_token=TWILIO_AUTH_TOKEN,
                whatsapp_number=TWILIO_WHATSAPP_NUMBER,
                webhook_verify_token=WHATSAPP_WEBHOOK_VERIFY_TOKEN,
            )
            logger.info("WhatsApp handler initialized")
        except Exception as e:
            logger.warning(f"WhatsApp handler initialization failed: {e}")
            whatsapp_handler = None
    else:
        logger.info("WhatsApp handler not configured (skipping)")

    # Initialize web form handler (non-blocking)
    try:
        logger.info("Initializing web form handler...")
        web_form_handler = WebFormHandler(
            kafka_servers=KAFKA_BOOTSTRAP_SERVERS,
            kafka_topic=TOPICS["tickets_incoming"],
        )
        await asyncio.wait_for(web_form_handler.initialize(), timeout=5.0)
        logger.info("Web form handler initialized")
    except Exception as e:
        logger.warning(f"Web form handler initialization failed: {e}")
        web_form_handler = None

    # Publish startup event (if Kafka available)
    if kafka_producer and kafka_producer.is_started:
        try:
            await kafka_producer.publish_event(
                topic=TOPICS["events"],
                event_type=EventType.SYSTEM_STARTED,
                payload={
                    "service": "fte-api",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except Exception:
            pass

    logger.info("Customer Success FTE API started successfully")
    
    yield  # Application runs here
    
    # SHUTDOWN
    logger.info("Shutting down Customer Success FTE API...")
    
    try:
        # Publish shutdown event
        if kafka_producer:
            await kafka_producer.publish_event(
                topic=TOPICS["events"],
                event_type=EventType.SYSTEM_STOPPED,
                payload={
                    "service": "fte-api",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        
        # Close handlers
        if gmail_handler:
            await gmail_handler.stop_notifications()
        
        if web_form_handler:
            await web_form_handler.shutdown()
        
        if kafka_producer:
            await kafka_producer.stop()
        
        logger.info("Customer Success FTE API shut down successfully")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================


app = FastAPI(
    title="Customer Success FTE API",
    description="API for multi-channel customer support automation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# DEPENDENCIES
# =============================================================================


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    Verify API key from Authorization header.
    
    Usage: Bearer <api-key>
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return credentials.credentials


async def get_db_pool_dep():
    """Get database pool dependency."""
    return await get_db_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns the health status of all services.
    """
    services = {}
    overall_status = "healthy"
    
    # Check database
    try:
        pool = await get_db_pool(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
        )
        db_healthy = await db_health_check(pool)
        services["database"] = db_healthy
        if not db_healthy:
            overall_status = "unhealthy"
    except Exception as e:
        services["database"] = False
        overall_status = "unhealthy"
        logger.error(f"Database health check failed: {e}")
    
    # Check Kafka
    services["kafka"] = kafka_producer is not None and kafka_producer.is_started
    
    # Check Gmail
    services["gmail"] = gmail_handler is not None
    
    # Check WhatsApp
    services["whatsapp"] = whatsapp_handler is not None
    
    # Check web form
    services["web_form"] = web_form_handler is not None
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        services=services,
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness check endpoint.
    
    Returns 200 if the service is ready to accept traffic.
    """
    # Check critical dependencies
    if kafka_producer is None or not kafka_producer.is_started:
        raise HTTPException(status_code=503, detail="Kafka not ready")
    
    return {"status": "ready"}


@app.get("/live", tags=["Health"])
async def liveness_check():
    """
    Liveness check endpoint.
    
    Returns 200 if the service is alive.
    """
    return {"status": "alive"}


# =============================================================================
# GMAIL WEBHOOK ENDPOINTS
# =============================================================================


@app.post("/webhooks/gmail", tags=["Webhooks", "Gmail"])
async def gmail_webhook(request: Request):
    """
    Gmail push notification webhook.
    
    Receives notifications from Google Cloud Pub/Sub when new emails arrive.
    """
    if gmail_handler is None:
        logger.warning("Gmail handler not initialized")
        raise HTTPException(status_code=503, detail="Gmail service not available")
    
    try:
        # Parse request body
        body = await request.json()
        
        # Process the notification
        # Note: In production, this would use the full Pub/Sub message format
        messages = await gmail_handler.process_notification(
            pubsub_message=type('obj', (object,), {'data': body.get('data', '')})()
        )
        
        # Publish each message to Kafka
        for message in messages:
            if kafka_producer:
                await kafka_producer.publish_ticket({
                    **message,
                    "channel": "email",
                })
        
        logger.info(f"Processed Gmail webhook: {len(messages)} messages")
        
        return {"success": True, "messages_processed": len(messages)}
        
    except Exception as e:
        logger.exception(f"Error processing Gmail webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhooks/gmail", tags=["Webhooks", "Gmail"])
async def gmail_webhook_verify():
    """
    Gmail webhook verification endpoint.
    
    Used by Google to verify webhook ownership.
    """
    return PlainTextResponse("gmail-webhook-verified")


# =============================================================================
# WHATSAPP WEBHOOK ENDPOINTS
# =============================================================================


@app.post("/webhooks/whatsapp", tags=["Webhooks", "WhatsApp"])
async def whatsapp_webhook(request: Request):
    """
    WhatsApp incoming message webhook.
    
    Receives messages from Twilio when customers send WhatsApp messages.
    """
    if whatsapp_handler is None:
        logger.warning("WhatsApp handler not initialized")
        raise HTTPException(status_code=503, detail="WhatsApp service not available")
    
    try:
        # Get signature from headers
        signature = request.headers.get("X-Twilio-Signature", "")
        
        # Get raw body
        body = await request.body()
        body_str = body.decode("utf-8")
        
        # Process webhook
        message_data = await whatsapp_handler.process_webhook(
            request=request,
            signature=signature,
            body=body_str,
        )
        
        if not message_data:
            raise HTTPException(status_code=400, detail="Failed to process message")
        
        # Publish to Kafka
        if kafka_producer:
            await kafka_producer.publish_ticket({
                **message_data,
                "channel": "whatsapp",
            })
        
        logger.info(f"Processed WhatsApp webhook: {message_data['channel_message_id']}")
        
        # Return empty 200 (Twilio will retry on error)
        return PlainTextResponse("", status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing WhatsApp webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhooks/whatsapp", tags=["Webhooks", "WhatsApp"])
async def whatsapp_webhook_verify(
    mode: str = Query("", alias="hub.mode"),
    verify_token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
):
    """
    WhatsApp webhook verification endpoint.
    
    Used by Meta to verify webhook ownership (WhatsApp Cloud API).
    """
    if whatsapp_handler is None:
        raise HTTPException(status_code=503, detail="WhatsApp service not available")
    
    result = whatsapp_handler.validate_webhook_token(
        verify_token=verify_token,
        mode=mode,
        challenge=challenge,
    )
    
    if result:
        return PlainTextResponse(result)
    else:
        raise HTTPException(status_code=403, detail="Invalid verification token")


@app.post("/webhooks/whatsapp/status", tags=["Webhooks", "WhatsApp"])
async def whatsapp_status_callback(request: Request):
    """
    WhatsApp message status callback.
    
    Receives delivery status updates from Twilio.
    """
    try:
        body = await request.form()
        
        message_sid = body.get("MessageSid", "")
        message_status = body.get("MessageStatus", "")
        
        logger.info(f"WhatsApp message status: {message_sid} -> {message_status}")
        
        # Publish status event to Kafka
        if kafka_producer:
            await kafka_producer.publish_event(
                topic=TOPICS["events"],
                event_type=EventType.MESSAGE_DELIVERED if message_status == "delivered" else EventType.MESSAGE_SENT,
                payload={
                    "channel": "whatsapp",
                    "message_sid": message_sid,
                    "status": message_status,
                },
            )
        
        return {"success": True}
        
    except Exception as e:
        logger.exception(f"Error processing WhatsApp status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# WEB FORM ENDPOINTS (from web_form_handler)
# =============================================================================

# Include the web form router (always include, handler checked at runtime)
# Create a minimal handler for router generation even if full init failed
from production.channels.web_form_handler import WebFormHandler as _WFH
if web_form_handler is None:
    web_form_handler = _WFH(
        kafka_servers=KAFKA_BOOTSTRAP_SERVERS,
        kafka_topic=TOPICS.get("tickets_incoming", "fte.tickets.incoming"),
    )

app.include_router(create_web_form_router(web_form_handler))


# =============================================================================
# CUSTOMER LOOKUP ENDPOINTS
# =============================================================================


@app.get("/customers/{customer_id}", response_model=CustomerLookupResponse, tags=["Customers"])
async def get_customer(
    customer_id: str,
    pool=Depends(get_db_pool_dep),
    _=Depends(verify_api_key),
):
    """
    Get customer by ID.
    
    Returns customer information and summary statistics.
    """
    customer = await get_customer_by_id(pool=pool, customer_id=customer_id)
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get counts (simplified - in production, use proper queries)
    history = await get_customer_history(pool=pool, customer_id=customer_id, limit=1)
    
    return CustomerLookupResponse(
        customer_id=str(customer.get("id")),
        email=customer.get("email"),
        phone=customer.get("phone"),
        name=customer.get("name"),
        created_at=customer.get("created_at", "").isoformat() if customer.get("created_at") else "",
        conversation_count=len(history) if history else 0,
        ticket_count=0,  # TODO: Add proper ticket count query
    )


@app.get("/customers/{customer_id}/history", tags=["Customers"])
async def get_customer_history_endpoint(
    customer_id: str,
    limit: int = Query(50, ge=1, le=200),
    pool=Depends(get_db_pool_dep),
    _=Depends(verify_api_key),
):
    """
    Get customer's conversation history.
    
    Returns all conversations for the customer across all channels.
    """
    history = await get_customer_history(pool=pool, customer_id=customer_id, limit=limit)
    
    return {
        "customer_id": customer_id,
        "conversations": history,
        "count": len(history),
    }


# =============================================================================
# CONVERSATION LOOKUP ENDPOINTS
# =============================================================================


@app.get("/conversations/{conversation_id}", response_model=ConversationLookupResponse, tags=["Conversations"])
async def get_conversation_endpoint(
    conversation_id: str,
    pool=Depends(get_db_pool_dep),
    _=Depends(verify_api_key),
):
    """
    Get conversation by ID.
    
    Returns conversation details and message count.
    """
    conversation = await get_conversation(pool=pool, conversation_id=conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get message count
    messages = await get_conversation_messages(pool=pool, conversation_id=conversation_id, limit=1)
    
    return ConversationLookupResponse(
        conversation_id=str(conversation.get("id")),
        customer_id=str(conversation.get("customer_id")),
        initial_channel=conversation.get("initial_channel"),
        started_at=conversation.get("started_at", "").isoformat() if conversation.get("started_at") else "",
        ended_at=conversation.get("ended_at", "").isoformat() if conversation.get("ended_at") else None,
        status=conversation.get("status"),
        message_count=len(messages) if messages else 0,
        ticket_id=None,  # TODO: Add ticket lookup
    )


@app.get("/conversations/{conversation_id}/messages", tags=["Conversations"])
async def get_conversation_messages_endpoint(
    conversation_id: str,
    limit: int = Query(100, ge=1, le=500),
    pool=Depends(get_db_pool_dep),
    _=Depends(verify_api_key),
):
    """
    Get messages in a conversation.
    
    Returns all messages ordered by creation time.
    """
    messages = await get_conversation_messages(pool=pool, conversation_id=conversation_id, limit=limit)
    
    return {
        "conversation_id": conversation_id,
        "messages": messages,
        "count": len(messages),
    }


# =============================================================================
# TICKET ENDPOINTS
# =============================================================================


@app.get("/tickets/{ticket_id}", tags=["Tickets"])
async def get_ticket_endpoint(
    ticket_id: str,
    pool=Depends(get_db_pool_dep),
    _=Depends(verify_api_key),
):
    """
    Get ticket by ID.
    
    Returns ticket details and status.
    """
    ticket = await get_ticket(pool=pool, ticket_id=ticket_id)
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    return {"ticket": ticket}


@app.get("/tickets", tags=["Tickets"])
async def list_open_tickets(
    customer_id: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    pool=Depends(get_db_pool_dep),
    _=Depends(verify_api_key),
):
    """
    List open tickets.
    
    Optionally filter by customer or channel.
    """
    tickets = await get_open_tickets(
        pool=pool,
        customer_id=customer_id,
        channel=channel,
        limit=limit,
    )
    
    return {
        "tickets": tickets,
        "count": len(tickets),
    }


# =============================================================================
# CHANNEL METRICS ENDPOINTS
# =============================================================================


@app.get("/metrics/channels/{channel}", response_model=ChannelMetricsResponse, tags=["Metrics"])
async def get_channel_metrics(
    channel: str,
    days: int = Query(7, ge=1, le=30),
    pool=Depends(get_db_pool_dep),
    _=Depends(verify_api_key),
):
    """
    Get metrics for a specific channel.
    
    Returns message counts, response times, and resolution rates.
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    
    # Get aggregate metrics (simplified - in production, use proper queries)
    metrics = await get_aggregate_metrics(
        pool=pool,
        metric_name="response_time",
        start_time=start_time,
        end_time=end_time,
        channel=channel,
    )
    
    return ChannelMetricsResponse(
        channel=channel,
        total_messages=0,  # TODO: Add proper message count query
        messages_inbound=0,
        messages_outbound=0,
        avg_response_time_ms=metrics.get("avg", 0) if metrics else 0,
        resolution_rate=0.0,
        escalation_rate=0.0,
        period_start=start_time.isoformat(),
        period_end=end_time.isoformat(),
    )


@app.get("/metrics/summary", tags=["Metrics"])
async def get_metrics_summary(
    days: int = Query(7, ge=1, le=30),
    pool=Depends(get_db_pool_dep),
    _=Depends(verify_api_key),
):
    """
    Get overall metrics summary.
    
    Returns aggregated metrics across all channels.
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    
    return {
        "period": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        },
        "channels": ["email", "whatsapp", "web_form"],
        "total_tickets": 0,  # TODO: Add proper queries
        "total_messages": 0,
        "avg_response_time_ms": 0,
        "resolution_rate": 0.0,
        "escalation_rate": 0.0,
        "customer_satisfaction": 0.0,
    }


# =============================================================================
# EVENT PUBLISHING ENDPOINTS
# =============================================================================


@app.post("/events", tags=["Events"])
async def publish_event(
    event_type: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
    _: str = Depends(verify_api_key),
):
    """
    Publish an event to Kafka.
    
    Used for manual event publishing and testing.
    """
    if kafka_producer is None:
        raise HTTPException(status_code=503, detail="Kafka not available")
    
    try:
        result = await kafka_producer.publish_event(
            topic=TOPICS["events"],
            event_type=EventType(event_type),
            payload=payload,
            correlation_id=correlation_id,
        )
        
        return {
            "success": True,
            "topic": result["topic"],
            "partition": result["partition"],
            "offset": result["offset"],
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error publishing event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ERROR HANDLERS
# =============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "status_code": 500,
        },
    )


# =============================================================================
# MAIN
# =============================================================================


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "production.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

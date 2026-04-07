@echo off
REM =============================================================================
REM Customer Success FTE — Windows Startup Script
REM =============================================================================
REM This script starts the backend server with all required dependencies.
REM
REM Usage:
REM   start.bat              # Start in local mode (development)
REM   start.bat --init-db    # Initialize database first, then start
REM   start.bat --port 9000  # Start on custom port
REM =============================================================================

echo.
echo ========================================
echo  Customer Success FTE — Backend
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check and install missing dependencies
echo [1/3] Checking dependencies...
pip install fastapi uvicorn[standard] asyncpg pydantic email-validator httpx python-dotenv >nul 2>&1

REM Initialize database if requested
if "%1"=="--init-db" (
    echo.
    echo [2/3] Initializing database...
    python init_db.py
    if %errorlevel% neq 0 (
        echo.
        echo WARNING: Database initialization failed. Continuing anyway...
        echo Make sure PostgreSQL is running: docker compose up -d
    )
) else (
    echo [2/3] Skipping database initialization (use --init-db to initialize)
)

REM Start server
echo.
echo [3/3] Starting backend server...
echo.
echo  Server: http://localhost:8000
echo  API Docs: http://localhost:8000/docs
echo  Frontend: Open production/web-form/index.html in browser
echo.
echo  Press Ctrl+C to stop the server
echo.

python run.py %*

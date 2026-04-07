@echo off
REM =============================================================================
REM Vercel Deployment Script for Customer Success FTE
REM =============================================================================
REM This script automates the deployment process to Vercel
REM
REM Usage:
REM   deploy-vercel.bat          - Deploy to preview
REM   deploy-vercel.bat --prod   - Deploy to production
REM =============================================================================

echo.
echo ========================================================================
echo  Customer Success FTE - Vercel Deployment
echo ========================================================================
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed.
    echo.
    echo Please install Node.js from: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

REM Check if Vercel CLI is installed
where vercel >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Vercel CLI is not installed.
    echo.
    echo Installing Vercel CLI...
    npm install -g vercel
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Vercel CLI.
        pause
        exit /b 1
    )
)

echo [INFO] Vercel CLI is installed.
echo.

REM Check if logged in
vercel whoami >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Not logged in to Vercel.
    echo.
    echo Please login to Vercel...
    vercel login
    if %errorlevel% neq 0 (
        echo [ERROR] Login failed.
        pause
        exit /b 1
    )
    echo.
)

REM Install Python dependencies
echo [INFO] Installing Python dependencies...
pip install -r production\requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies may have failed to install.
    echo Continuing with deployment...
    echo.
)

echo.
echo ========================================================================
echo  Starting Deployment...
echo ========================================================================
echo.

REM Deploy to Vercel
if "%1"=="--prod" (
    echo [INFO] Deploying to PRODUCTION...
    vercel --prod
) else (
    echo [INFO] Deploying to PREVIEW...
    vercel
)

if %errorlevel% equ 0 (
    echo.
    echo ========================================================================
    echo  Deployment Successful!
    echo ========================================================================
    echo.
    echo Next Steps:
    echo 1. Configure environment variables in Vercel dashboard
    echo 2. Initialize database: POST https://your-app.vercel.app/api/admin/init-db
    echo 3. Test health endpoint: https://your-app.vercel.app/health
    echo 4. View API docs: https://your-app.vercel.app/api/docs
    echo.
    echo See VERCEL_DEPLOYMENT_GUIDE.md for detailed instructions.
    echo.
) else (
    echo.
    echo ========================================================================
    echo  Deployment Failed!
    echo ========================================================================
    echo.
    echo Please check the error messages above and try again.
    echo.
    echo Common issues:
    echo - Missing environment variables
    echo - Build errors in requirements
    echo - Network connectivity issues
    echo.
    echo See VERCEL_DEPLOYMENT_GUIDE.md for troubleshooting.
    echo.
)

pause

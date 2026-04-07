"""
Vercel Serverless Function Entry Point

This file adapts the FastAPI application to run on Vercel's serverless platform.
Vercel expects a handler function that accepts (environ, start_response) for ASGI.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the FastAPI app from production
from production.api.main import app

# For Vercel serverless, we need to use an ASGI adapter
try:
    from mangum import Mangum
    
    # Mangum adapts ASGI apps (like FastAPI) to work on serverless platforms
    handler = Mangum(app, lifespan="auto")
except ImportError:
    # Fallback: Create a simple WSGI-style handler
    # This will work but without async support
    from fastapi.responses import JSONResponse
    
    def handler(environ, start_response):
        """Fallback handler if mangum is not available."""
        start_response('503 Service Unavailable', [
            ('Content-Type', 'application/json')
        ])
        return [b'{"error": "Mangum not installed. Run: pip install mangum"}']

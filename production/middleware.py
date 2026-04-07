"""
Middleware for Customer Success FTE Backend.

Provides:
- Rate limiting (in-memory for dev, Redis-backed for production)
- Request ID tracking
- Request/response logging
- API key authentication
- Error handling
"""

import time
import uuid
import logging
from typing import Dict, Optional, List
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware


logger = logging.getLogger("backend.middleware")


# =============================================================================
# RATE LIMITER
# =============================================================================


class RateLimiter:
    """
    Sliding window rate limiter.
    
    For production, replace with Redis-backed version.
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, key: str) -> tuple[bool, dict]:
        """
        Check if request is allowed.
        
        Returns:
            (allowed, headers_dict)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old entries
        self._requests[key] = [
            ts for ts in self._requests[key]
            if ts > window_start
        ]
        
        current_count = len(self._requests[key])
        
        headers = {
            "X-RateLimit-Limit": str(self.max_requests),
            "X-RateLimit-Remaining": str(max(0, self.max_requests - current_count)),
            "X-RateLimit-Window": str(self.window_seconds),
        }
        
        if current_count >= self.max_requests:
            retry_after = int(self._requests[key][0] + self.window_seconds - now)
            headers["Retry-After"] = str(max(1, retry_after))
            return False, headers
        
        # Record this request
        self._requests[key].append(now)
        headers["X-RateLimit-Remaining"] = str(max(0, self.max_requests - current_count - 1))
        
        return True, headers
    
    def cleanup(self):
        """Remove expired entries."""
        now = time.time()
        window_start = now - self.window_seconds
        
        for key in list(self._requests.keys()):
            self._requests[key] = [
                ts for ts in self._requests[key]
                if ts > window_start
            ]
            if not self._requests[key]:
                del self._requests[key]


# Global rate limiters
_form_limiter = RateLimiter(max_requests=5, window_seconds=3600)  # 5 per hour per IP
_api_limiter = RateLimiter(max_requests=100, window_seconds=60)   # 100 per minute per key


# =============================================================================
# REQUEST ID MIDDLEWARE
# =============================================================================


async def request_id_middleware(request: Request, call_next):
    """Add unique request ID to every request."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response


# =============================================================================
# RATE LIMIT MIDDLEWARE
# =============================================================================


async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to API endpoints."""
    # Skip rate limiting for health/readiness endpoints
    path = request.url.path
    if path in ["/health", "/ready", "/live", "/api/docs", "/api/openapi.json"]:
        return await call_next(request)
    
    # Get client identifier
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client:
        client_ip = request.client.host
    else:
        client_ip = "unknown"
    
    # Choose limiter based on endpoint
    if path.startswith("/support/submit"):
        allowed, headers = _form_limiter.is_allowed(client_ip)
    else:
        api_key = request.headers.get("Authorization", "")
        allowed, headers = _api_limiter.is_allowed(api_key or client_ip)
    
    if not allowed:
        return Response(
            content='{"success": false, "error": "Rate limit exceeded. Please try again later."}',
            status_code=429,
            headers={**headers, "Content-Type": "application/json"},
        )
    
    response = await call_next(request)
    
    # Add rate limit headers to response
    for key, value in headers.items():
        response.headers[key] = value
    
    return response


# =============================================================================
# REQUEST LOGGING MIDDLEWARE
# =============================================================================


async def request_logging_middleware(request: Request, call_next):
    """Log all requests with timing information."""
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log request
    logger.info(
        f"→ {request.method} {request.url.path} | ID: {request_id}"
    )
    
    try:
        response = await call_next(request)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        log_level = "warning" if response.status_code >= 400 else "debug"
        getattr(logger, log_level)(
            f"← {request.method} {request.url.path} | "
            f"{response.status_code} | "
            f"{duration_ms:.0f}ms | "
            f"ID: {request_id}"
        )
        
        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"✗ {request.method} {request.url.path} | "
            f"ERROR: {e} | "
            f"{duration_ms:.0f}ms | "
            f"ID: {request_id}"
        )
        raise


# =============================================================================
# SECURITY HEADERS MIDDLEWARE
# =============================================================================


async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response


# =============================================================================
# GLOBAL EXCEPTION HANDLER
# =============================================================================


async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger = logging.getLogger("backend.error")
    
    # Log the error
    logger.exception(
        f"Unhandled exception | "
        f"Method: {request.method} | "
        f"Path: {request.url.path} | "
        f"ID: {request_id} | "
        f"Error: {exc}"
    )
    
    from fastapi.responses import JSONResponse
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )

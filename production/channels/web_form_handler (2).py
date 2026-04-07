"""
Web Form Handler for Customer Success FTE.

This module handles support form submissions from the web interface,
including validation, Kafka publishing, and ticket creation.

Features:
- FastAPI router with /support endpoints
- Pydantic models with validation
- Kafka integration for async processing
- Ticket status tracking
- Rate limiting and spam prevention
"""

from fastapi import APIRouter, HTTPException, status, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid
import logging
import hashlib
import time

logger = logging.getLogger(__name__)


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PriorityLevel(str, Enum):
    """Support ticket priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketCategory(str, Enum):
    """Support ticket categories."""
    TECHNICAL = "technical"
    BILLING = "billing"
    ACCOUNT = "account"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    GENERAL = "general"
    OTHER = "other"


class SupportFormSubmission(BaseModel):
    """
    Pydantic model for support form submission with validation.
    
    This model validates all incoming form data to ensure data quality
    and prevent spam/abuse.
    """
    
    # Required fields
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Customer's full name",
        example="John Doe"
    )
    
    email: EmailStr = Field(
        ...,
        description="Customer's email address for follow-up",
        example="john.doe@example.com"
    )
    
    subject: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Brief subject line for the issue",
        example="Unable to access my account"
    )
    
    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Detailed description of the issue",
        example="I've been trying to log in but keep getting an error message..."
    )
    
    # Optional fields
    category: TicketCategory = Field(
        default=TicketCategory.GENERAL,
        description="Category of the support request"
    )
    
    priority: PriorityLevel = Field(
        default=PriorityLevel.MEDIUM,
        description="Requested priority level"
    )
    
    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Optional phone number for urgent contact",
        example="+1-555-123-4567"
    )
    
    company: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional company name",
        example="Acme Corp"
    )
    
    order_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Optional order/reference ID",
        example="ORD-12345"
    )
    
    # Hidden fields for spam prevention
    honeypot: Optional[str] = Field(
        default=None,
        max_length=1,
        description="Honeypot field - should be empty (spam detection)"
    )
    
    # Metadata (auto-populated)
    ip_address: Optional[str] = Field(
        default=None,
        description="Client IP address (auto-populated from request)"
    )
    
    user_agent: Optional[str] = Field(
        default=None,
        description="Client user agent (auto-populated from request)"
    )
    
    @validator('name')
    def validate_name(cls, v):
        """Validate name contains only valid characters."""
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace only")
        # Allow letters, spaces, hyphens, and apostrophes
        if not all(c.isalpha() or c in " '-." for c in v):
            raise ValueError("Name contains invalid characters")
        return v.strip()
    
    @validator('description')
    def validate_description(cls, v):
        """Validate description quality."""
        if not v.strip():
            raise ValueError("Description cannot be empty")
        
        # Check for minimum word count
        word_count = len(v.split())
        if word_count < 3:
            raise ValueError("Description must be at least 3 words")
        
        # Check for excessive capitalization (potential spam)
        if sum(1 for c in v if c.isupper()) / len(v) > 0.7:
            raise ValueError("Description has excessive capitalization")
        
        return v.strip()
    
    @validator('subject')
    def validate_subject(cls, v):
        """Validate subject line."""
        if not v.strip():
            raise ValueError("Subject cannot be empty")
        return v.strip()
    
    @validator('honeypot')
    def validate_honeypot(cls, v):
        """Validate honeypot field is empty (spam detection)."""
        if v:
            raise ValueError("Spam detected")
        return v
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "subject": "Unable to access my account",
                "description": "I've been trying to log in but keep getting an error message saying my credentials are invalid.",
                "category": "technical",
                "priority": "medium",
                "phone": "+1-555-123-4567",
                "company": "Acme Corp",
                "order_id": "ORD-12345"
            }
        }


class SupportFormResponse(BaseModel):
    """Response model for successful form submission."""
    
    success: bool = Field(..., description="Whether submission was successful")
    ticket_id: str = Field(..., description="Unique ticket ID for tracking")
    message: str = Field(..., description="Confirmation message")
    estimated_response_time: str = Field(
        ...,
        description="Estimated time for first response"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "ticket_id": "TKT-2024-001234",
                "message": "Your support request has been submitted successfully.",
                "estimated_response_time": "2-4 hours"
            }
        }


class TicketStatusResponse(BaseModel):
    """Response model for ticket status lookup."""
    
    ticket_id: str = Field(..., description="Ticket ID")
    status: str = Field(..., description="Current ticket status")
    category: str = Field(..., description="Ticket category")
    priority: str = Field(..., description="Ticket priority")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    subject: str = Field(..., description="Ticket subject")
    public_message: Optional[str] = Field(
        None,
        description="Public message/response (if any)"
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    success: bool = False
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


# =============================================================================
# RATE LIMITING
# =============================================================================

class RateLimiter:
    """
    Simple in-memory rate limiter for form submissions.
    
    In production, use Redis or similar for distributed rate limiting.
    """
    
    def __init__(self, max_requests: int = 5, window_seconds: int = 3600):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds (default 1 hour)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed for the given identifier.
        
        Args:
            identifier: Unique identifier (e.g., IP address, email)
            
        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old entries
        if identifier in self.requests:
            self.requests[identifier] = [
                ts for ts in self.requests[identifier]
                if ts > window_start
            ]
        else:
            self.requests[identifier] = []
        
        # Check if limit exceeded
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Record this request
        self.requests[identifier].append(now)
        return True
    
    def get_retry_after(self, identifier: str) -> Optional[int]:
        """
        Get seconds until rate limit resets.
        
        Args:
            identifier: Unique identifier
            
        Returns:
            Seconds to wait, or None if not rate limited
        """
        if identifier not in self.requests:
            return None
        
        oldest = min(self.requests[identifier])
        retry_after = int(oldest + self.window_seconds - time.time())
        return max(0, retry_after)


# =============================================================================
# KAFKA PUBLISHER (Placeholder)
# =============================================================================

class KafkaPublisher:
    """
    Kafka publisher for form submissions.
    
    In production, use aiokafka or confluent-kafka for async publishing.
    """
    
    def __init__(self, bootstrap_servers: List[str], topic: str):
        """
        Initialize Kafka publisher.
        
        Args:
            bootstrap_servers: List of Kafka broker addresses
            topic: Topic to publish to
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
    
    async def connect(self):
        """Establish connection to Kafka cluster."""
        # TODO: Implement with aiokafka
        logger.info(f"Kafka publisher initialized for topic: {self.topic}")
    
    async def publish(self, message: Dict[str, Any]) -> bool:
        """
        Publish message to Kafka.
        
        Args:
            message: Message dictionary to publish
            
        Returns:
            True if published successfully
        """
        # TODO: Implement actual Kafka publishing
        logger.info(f"Publishing to Kafka topic {self.topic}: {message.get('ticket_id')}")
        return True
    
    async def close(self):
        """Close Kafka connection."""
        # TODO: Implement cleanup
        pass


# =============================================================================
# WEB FORM HANDLER CLASS
# =============================================================================

class WebFormHandler:
    """
    Handler for web support form submissions.
    
    Manages form validation, rate limiting, Kafka publishing,
    and ticket status tracking.
    """
    
    def __init__(
        self,
        kafka_servers: List[str],
        kafka_topic: str = "support_tickets",
        rate_limit_requests: int = 5,
        rate_limit_window: int = 3600
    ):
        """
        Initialize web form handler.
        
        Args:
            kafka_servers: Kafka bootstrap servers
            kafka_topic: Kafka topic for ticket submissions
            rate_limit_requests: Max submissions per window
            rate_limit_window: Rate limit window in seconds
        """
        self.kafka_publisher = KafkaPublisher(kafka_servers, kafka_topic)
        self.rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)
        
        # In-memory ticket store (use database in production)
        self.tickets: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self):
        """Initialize handler connections."""
        await self.kafka_publisher.connect()
    
    async def shutdown(self):
        """Shutdown handler connections."""
        await self.kafka_publisher.close()
    
    def _generate_ticket_id(self) -> str:
        """
        Generate a human-readable ticket ID.
        
        Returns:
            Ticket ID in format TKT-YYYY-NNNNNN
        """
        year = datetime.utcnow().year
        unique_id = uuid.uuid4().hex[:6].upper()
        return f"TKT-{year}-{unique_id}"
    
    def _get_client_identifier(self, request: Request) -> str:
        """
        Get unique client identifier for rate limiting.
        
        Uses IP address with X-Forwarded-For support.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client identifier string
        """
        # Check for forwarded IP (behind proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the chain
            ip = forwarded_for.split(',')[0].strip()
        else:
            ip = request.client.host if request.client else 'unknown'
        
        # Hash the IP for privacy
        return hashlib.sha256(ip.encode()).hexdigest()[:16]
    
    async def submit_support_form(
        self,
        submission: SupportFormSubmission,
        request: Request
    ) -> SupportFormResponse:
        """
        Process a support form submission.
        
        Args:
            submission: Validated form submission
            request: FastAPI request object
            
        Returns:
            Submission response with ticket ID
            
        Raises:
            HTTPException: If rate limited or processing fails
        """
        # Get client identifier for rate limiting
        client_id = self._get_client_identifier(request)
        
        # Check rate limit
        if not self.rate_limiter.is_allowed(client_id):
            retry_after = self.rate_limiter.get_retry_after(client_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many submissions. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)}
            )
        
        # Generate ticket ID
        ticket_id = self._generate_ticket_id()
        
        # Enrich submission with metadata
        submission_dict = submission.dict()
        submission_dict['ticket_id'] = ticket_id
        submission_dict['ip_address'] = request.client.host if request.client else None
        submission_dict['user_agent'] = request.headers.get('user-agent')
        submission_dict['submitted_at'] = datetime.utcnow().isoformat()
        
        # Create Kafka message
        kafka_message = {
            'event_type': 'support_ticket_created',
            'ticket_id': ticket_id,
            'channel': 'web_form',
            'customer': {
                'name': submission.name,
                'email': submission.email,
                'phone': submission.phone,
                'company': submission.company
            },
            'ticket': {
                'subject': submission.subject,
                'description': submission.description,
                'category': submission.category,
                'priority': submission.priority,
                'order_id': submission.order_id
            },
            'metadata': {
                'ip_address': submission_dict['ip_address'],
                'user_agent': submission_dict['user_agent'],
                'submitted_at': submission_dict['submitted_at']
            }
        }
        
        # Publish to Kafka
        try:
            await self.kafka_publisher.publish(kafka_message)
        except Exception as e:
            logger.error(f"Failed to publish to Kafka: {e}")
            # Don't fail the request - ticket is still created
        
        # Store ticket locally (in production, this goes to database)
        self.tickets[ticket_id] = {
            **submission_dict,
            'status': 'open',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'public_message': None
        }
        
        # Determine estimated response time based on priority
        eta_map = {
            'critical': '30 minutes',
            'high': '1 hour',
            'medium': '2-4 hours',
            'low': '24 hours'
        }
        estimated_time = eta_map.get(submission.priority, '2-4 hours')
        
        logger.info(f"Support form submitted. Ticket ID: {ticket_id}")
        
        return SupportFormResponse(
            success=True,
            ticket_id=ticket_id,
            message="Your support request has been submitted successfully. We'll respond to your email shortly.",
            estimated_response_time=estimated_time
        )
    
    async def get_ticket_status(
        self,
        ticket_id: str,
        email: Optional[str] = None
    ) -> TicketStatusResponse:
        """
        Get ticket status by ID.
        
        Args:
            ticket_id: Ticket ID to look up
            email: Optional email for verification
            
        Returns:
            Ticket status information
            
        Raises:
            HTTPException: If ticket not found
        """
        ticket = self.tickets.get(ticket_id)
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket {ticket_id} not found"
            )
        
        # In production, verify email matches ticket owner
        if email and email.lower() != ticket.get('email', '').lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email does not match ticket owner"
            )
        
        return TicketStatusResponse(
            ticket_id=ticket_id,
            status=ticket['status'],
            category=ticket['category'],
            priority=ticket['priority'],
            created_at=ticket['created_at'],
            updated_at=ticket.get('updated_at'),
            subject=ticket['subject'],
            public_message=ticket.get('public_message')
        )
    
    async def update_ticket(
        self,
        ticket_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a ticket (for internal use).
        
        Args:
            ticket_id: Ticket ID to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated ticket data
        """
        if ticket_id not in self.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        
        ticket = self.tickets[ticket_id]
        ticket.update(updates)
        ticket['updated_at'] = datetime.utcnow().isoformat()
        
        return ticket


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

def create_web_form_router(handler: WebFormHandler) -> APIRouter:
    """
    Create a FastAPI router for support form endpoints.
    
    Args:
        handler: WebFormHandler instance
        
    Returns:
        Configured APIRouter
    """
    router = APIRouter(prefix="/support", tags=["support"])
    
    @router.post(
        "/submit",
        response_model=SupportFormResponse,
        responses={
            200: {"model": SupportFormResponse, "description": "Submission successful"},
            400: {"model": ErrorResponse, "description": "Validation error"},
            429: {"model": ErrorResponse, "description": "Rate limited"},
            500: {"model": ErrorResponse, "description": "Server error"}
        }
    )
    async def submit_support_form(
        submission: SupportFormSubmission,
        request: Request
    ):
        """
        Submit a support request form.
        
        This endpoint accepts support form submissions, validates them,
        publishes to Kafka for async processing, and returns a ticket ID.
        
        **Rate Limits:**
        - Maximum 5 submissions per hour per IP address
        
        **Response Times:**
        - Critical: 30 minutes
        - High: 1 hour
        - Medium: 2-4 hours
        - Low: 24 hours
        """
        return await handler.submit_support_form(submission, request)
    
    @router.get(
        "/status/{ticket_id}",
        response_model=TicketStatusResponse,
        responses={
            200: {"model": TicketStatusResponse, "description": "Status retrieved"},
            404: {"model": ErrorResponse, "description": "Ticket not found"},
            403: {"model": ErrorResponse, "description": "Access denied"}
        }
    )
    async def get_ticket_status(
        ticket_id: str,
        email: Optional[str] = None
    ):
        """
        Get the status of a support ticket.
        
        Use the ticket ID returned from form submission to check status.
        Optionally provide email for verification.
        """
        return await handler.get_ticket_status(ticket_id, email)
    
    @router.get("/health")
    async def health_check():
        """Check if the support form service is healthy."""
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    
    return router


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

# Global handler instance (use dependency injection in production)
_web_form_handler: Optional[WebFormHandler] = None


def get_web_form_handler() -> WebFormHandler:
    """
    Get the web form handler instance.
    
    Use as FastAPI dependency.
    """
    if _web_form_handler is None:
        raise HTTPException(
            status_code=500,
            detail="Web form handler not initialized"
        )
    return _web_form_handler


async def initialize_web_form_handler(
    kafka_servers: List[str],
    kafka_topic: str = "support_tickets"
) -> WebFormHandler:
    """
    Initialize the global web form handler.
    
    Call this during application startup.
    
    Args:
        kafka_servers: Kafka bootstrap servers
        kafka_topic: Kafka topic for tickets
        
    Returns:
        Initialized handler instance
    """
    global _web_form_handler
    _web_form_handler = WebFormHandler(kafka_servers, kafka_topic)
    await _web_form_handler.initialize()
    return _web_form_handler

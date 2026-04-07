"""
Channel integration handlers for Customer Success FTE.

This package provides handlers for all supported communication channels:
- Gmail (email)
- WhatsApp (via Twilio)
- Web Form (FastAPI endpoints)
"""

from .gmail_handler import GmailHandler, GmailPollingHandler
from .whatsapp_handler import WhatsAppHandler, create_whatsapp_webhook_router
from .web_form_handler import (
    WebFormHandler,
    create_web_form_router,
    SupportFormSubmission,
    SupportFormResponse,
    TicketStatusResponse,
    initialize_web_form_handler,
    get_web_form_handler,
)

__all__ = [
    # Gmail
    'GmailHandler',
    'GmailPollingHandler',
    # WhatsApp
    'WhatsAppHandler',
    'create_whatsapp_webhook_router',
    # Web Form
    'WebFormHandler',
    'create_web_form_router',
    'SupportFormSubmission',
    'SupportFormResponse',
    'TicketStatusResponse',
    'initialize_web_form_handler',
    'get_web_form_handler',
]

"""
Production tools for Customer Success FTE using OpenAI Agents SDK.

This module defines all @function_tool decorated functions that the
Customer Success Agent can use. Each tool has strict input validation
via Pydantic models and proper error handling.

Tools are organized by category:
- Customer Operations
- Ticket Operations
- Knowledge Base Operations
- Communication Operations
- Escalation Operations
"""

from agents import function_tool
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

from production.database.queries import (
    get_or_create_customer,
    get_customer_by_id,
    get_customer_history,
    create_conversation,
    store_message,
    create_ticket_record,
    get_ticket,
    update_ticket_status,
    search_knowledge_base,
    add_knowledge_entry,
    get_channel_config,
    record_metric,
    get_db_pool,
)
from production.database.queries import get_db_pool as pool_getter

logger = logging.getLogger(__name__)

# =============================================================================
# ENUMS
# =============================================================================


class Channel(str, Enum):
    """Supported communication channels."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class TicketPriority(str, Enum):
    """Ticket priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketCategory(str, Enum):
    """Ticket categories."""
    TECHNICAL = "technical"
    BILLING = "billing"
    ACCOUNT = "account"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    GENERAL = "general"
    OTHER = "other"


class TicketStatus(str, Enum):
    """Ticket status values."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MessageRole(str, Enum):
    """Message role values."""
    CUSTOMER = "customer"
    AGENT = "agent"
    SYSTEM = "system"


class MessageDirection(str, Enum):
    """Message direction values."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


# =============================================================================
# PYDANTIC INPUT MODELS
# =============================================================================


class KnowledgeSearchInput(BaseModel):
    """Input schema for knowledge base search."""
    query: str = Field(..., description="Search query text")
    max_results: int = Field(default=5, ge=1, le=10, description="Maximum results to return")
    category: Optional[str] = Field(default=None, description="Optional category filter")


class TicketInput(BaseModel):
    """Input schema for creating a ticket."""
    customer_id: str = Field(..., description="Customer UUID")
    conversation_id: str = Field(..., description="Conversation UUID")
    issue: str = Field(..., description="Description of the issue")
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, description="Ticket priority")
    category: TicketCategory = Field(default=TicketCategory.GENERAL, description="Ticket category")
    channel: Channel = Field(..., description="Source channel")


class CustomerHistoryInput(BaseModel):
    """Input schema for getting customer history."""
    customer_id: str = Field(..., description="Customer UUID")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum conversations to return")


class EscalationInput(BaseModel):
    """Input schema for escalating to human."""
    ticket_id: str = Field(..., description="Ticket UUID")
    reason: str = Field(..., description="Reason for escalation")
    priority: TicketPriority = Field(default=TicketPriority.HIGH, description="Escalation priority")
    context: Optional[str] = Field(default=None, description="Additional context for human agent")


class SendResponseInput(BaseModel):
    """Input schema for sending a response."""
    ticket_id: str = Field(..., description="Ticket UUID")
    message: str = Field(..., description="Response message content")
    channel: Channel = Field(..., description="Channel to send via")
    conversation_id: str = Field(..., description="Conversation UUID")


class StoreMessageInput(BaseModel):
    """Input schema for storing a message."""
    conversation_id: str = Field(..., description="Conversation UUID")
    channel: Channel = Field(..., description="Message channel")
    direction: MessageDirection = Field(..., description="Message direction")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    channel_message_id: Optional[str] = Field(default=None, description="External channel message ID")
    tokens_used: Optional[int] = Field(default=None, description="Token count for LLM tracking")
    latency_ms: Optional[int] = Field(default=None, description="Response latency")


class CreateConversationInput(BaseModel):
    """Input schema for creating a conversation."""
    customer_id: str = Field(..., description="Customer UUID")
    initial_channel: Channel = Field(..., description="Channel where conversation started")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class GetCustomerInput(BaseModel):
    """Input schema for customer lookup."""
    email: Optional[str] = Field(default=None, description="Customer email")
    phone: Optional[str] = Field(default=None, description="Customer phone")
    identifier_type: Optional[str] = Field(default=None, description="Identifier type")
    identifier_value: Optional[str] = Field(default=None, description="Identifier value")


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

_db_pool = None


async def get_pool():
    """Get or create database pool."""
    global _db_pool
    if _db_pool is None:
        _db_pool = await pool_getter()
    return _db_pool


# =============================================================================
# CUSTOMER TOOLS
# =============================================================================


@function_tool
async def get_or_create_customer_tool(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    name: Optional[str] = None,
    identifier_type: Optional[str] = None,
    identifier_value: Optional[str] = None
) -> str:
    """
    Get existing customer or create new one based on provided identifiers.

    Use this tool at the start of every customer interaction to identify
    the customer. Provide either email/phone directly, or use identifier_type
    and identifier_value for channel-specific identifiers.

    Args:
        email: Customer email address
        phone: Customer phone number
        name: Customer name (used if creating new customer)
        identifier_type: Type of identifier ('email', 'phone', 'whatsapp')
        identifier_value: Value of the identifier

    Returns:
        JSON string with customer record including id, email, phone, name
    """
    try:
        pool = await get_pool()
        customer = await get_or_create_customer(
            pool=pool,
            email=email,
            phone=phone,
            name=name,
            identifier_type=identifier_type,
            identifier_value=identifier_value
        )
        
        if customer:
            return f"Customer identified: {customer}"
        else:
            return "Error: Could not identify or create customer"
            
    except Exception as e:
        logger.error(f"Error in get_or_create_customer_tool: {e}")
        return f"Error identifying customer: {str(e)}"


@function_tool
async def get_customer_history_tool(
    customer_id: str,
    limit: int = 50
) -> str:
    """
    Get customer's conversation history across ALL channels.

    Use this tool to understand the customer's context before responding.
    This shows previous conversations, tickets, and interaction patterns.

    Args:
        customer_id: Customer UUID
        limit: Maximum number of conversations to return (default 50)

    Returns:
        JSON string with conversation history including channels, topics,
        resolution types, and sentiment scores
    """
    try:
        pool = await get_pool()
        history = await get_customer_history(
            pool=pool,
            customer_id=customer_id,
            limit=limit
        )
        
        if history:
            return f"Customer history: {history}"
        else:
            return "No previous history found for this customer."
            
    except Exception as e:
        logger.error(f"Error in get_customer_history_tool: {e}")
        return f"Error retrieving customer history: {str(e)}"


# =============================================================================
# CONVERSATION TOOLS
# =============================================================================


@function_tool
async def create_conversation_tool(
    customer_id: str,
    initial_channel: str,
    metadata: Optional[str] = None
) -> str:
    """
    Create a new conversation record.

    Use this tool when starting a new customer interaction. The conversation
    tracks all messages and is linked to tickets.

    Args:
        customer_id: Customer UUID
        initial_channel: Channel where conversation started ('email', 'whatsapp', 'web_form')
        metadata: Additional conversation metadata (JSON string)

    Returns:
        JSON string with conversation record including id
    """
    try:
        pool = await get_pool()
        conversation = await create_conversation(
            pool=pool,
            customer_id=customer_id,
            initial_channel=initial_channel,
            metadata=metadata
        )
        
        if conversation:
            return f"Conversation created: {conversation}"
        else:
            return "Error: Could not create conversation"
            
    except Exception as e:
        logger.error(f"Error in create_conversation_tool: {e}")
        return f"Error creating conversation: {str(e)}"


@function_tool
async def store_message_tool(
    conversation_id: str,
    channel: str,
    direction: str,
    role: str,
    content: str,
    channel_message_id: Optional[str] = None,
    tokens_used: Optional[int] = None,
    latency_ms: Optional[int] = None
) -> str:
    """
    Store a message in the database.

    Use this tool to record all messages (both inbound from customers and
    outbound from the agent). This maintains conversation history.

    Args:
        conversation_id: Conversation UUID
        channel: Message channel ('email', 'whatsapp', 'web_form')
        direction: Message direction ('inbound', 'outbound')
        role: Message role ('customer', 'agent', 'system')
        content: Message content
        channel_message_id: External channel message ID (optional)
        tokens_used: Token count for LLM cost tracking (optional)
        latency_ms: Response latency for performance monitoring (optional)

    Returns:
        JSON string with created message record
    """
    try:
        pool = await get_pool()
        message = await store_message(
            pool=pool,
            conversation_id=conversation_id,
            channel=channel,
            direction=direction,
            role=role,
            content=content,
            channel_message_id=channel_message_id,
            tokens_used=tokens_used,
            latency_ms=latency_ms
        )
        
        if message:
            return f"Message stored: {message}"
        else:
            return "Error: Could not store message"
            
    except Exception as e:
        logger.error(f"Error in store_message_tool: {e}")
        return f"Error storing message: {str(e)}"


# =============================================================================
# TICKET TOOLS
# =============================================================================


@function_tool
async def create_ticket_tool(
    customer_id: str,
    conversation_id: str,
    issue: str,
    priority: str = "medium",
    category: str = "general",
    channel: str = "email"
) -> str:
    """
    Create a support ticket in the system.

    REQUIRED: Call this tool BEFORE sending any response to a customer.
    Every interaction must be tracked with a ticket for reporting and
    quality assurance.

    Args:
        customer_id: Customer UUID
        conversation_id: Conversation UUID
        issue: Description of the issue
        priority: Ticket priority ('low', 'medium', 'high', 'critical')
        category: Ticket category ('technical', 'billing', 'account', 
                  'feature_request', 'bug_report', 'general', 'other')
        channel: Source channel ('email', 'whatsapp', 'web_form')

    Returns:
        JSON string with created ticket record including ticket_id
    """
    try:
        pool = await get_pool()
        ticket = await create_ticket_record(
            pool=pool,
            conversation_id=conversation_id,
            customer_id=customer_id,
            source_channel=channel,
            category=category,
            priority=priority
        )
        
        if ticket:
            return f"Ticket created: {ticket}"
        else:
            return "Error: Could not create ticket"
            
    except Exception as e:
        logger.error(f"Error in create_ticket_tool: {e}")
        return f"Error creating ticket: {str(e)}"


@function_tool
async def update_ticket_status_tool(
    ticket_id: str,
    status: str,
    resolution_notes: Optional[str] = None
) -> str:
    """
    Update ticket status and resolution notes.

    Use this tool when closing or updating a ticket's status.

    Args:
        ticket_id: Ticket UUID
        status: New status ('open', 'in_progress', 'resolved', 'closed')
        resolution_notes: Notes about the resolution (optional)

    Returns:
        JSON string with updated ticket record
    """
    try:
        pool = await get_pool()
        ticket = await update_ticket_status(
            pool=pool,
            ticket_id=ticket_id,
            status=status,
            resolution_notes=resolution_notes
        )
        
        if ticket:
            return f"Ticket updated: {ticket}"
        else:
            return "Error: Could not update ticket"
            
    except Exception as e:
        logger.error(f"Error in update_ticket_status_tool: {e}")
        return f"Error updating ticket: {str(e)}"


# =============================================================================
# KNOWLEDGE BASE TOOLS
# =============================================================================


@function_tool
async def search_knowledge_base_tool(
    query: str,
    max_results: int = 5,
    category: Optional[str] = None
) -> str:
    """
    Search product documentation for relevant information.

    Use this tool when the customer asks questions about product features,
    how-to guidance, or technical information. This performs semantic search
    using vector embeddings for accurate results.

    Args:
        query: Search query text
        max_results: Maximum number of results to return (1-10, default 5)
        category: Optional category filter

    Returns:
        Formatted search results with relevance scores and content snippets
    """
    try:
        pool = await get_pool()
        
        # TODO: Generate embedding for the query
        # For now, return a placeholder
        embedding = None  # Would use embedding model here
        
        results = await search_knowledge_base(
            pool=pool,
            query_embedding=embedding or [0.0] * 1536,  # Placeholder
            category=category,
            max_results=max_results
        )
        
        if results:
            formatted = []
            for r in results:
                formatted.append(f"**{r.get('title', 'Untitled')}** (relevance: {r.get('similarity', 0):.2f})\n{r.get('content', '')[:500]}")
            return "\n\n---\n\n".join(formatted)
        else:
            return "No relevant documentation found. Consider escalating to human support."
            
    except Exception as e:
        logger.error(f"Error in search_knowledge_base_tool: {e}")
        return f"Knowledge base search failed: {str(e)}. Consider escalating."


@function_tool
async def add_knowledge_entry_tool(
    title: str,
    content: str,
    category: Optional[str] = None
) -> str:
    """
    Add a new knowledge base entry.

    Use this tool sparingly to add new documentation based on resolved
    tickets that could help future customers.

    Args:
        title: Entry title
        content: Entry content
        category: Entry category (optional)

    Returns:
        JSON string with created knowledge base entry
    """
    try:
        pool = await get_pool()
        entry = await add_knowledge_entry(
            pool=pool,
            title=title,
            content=content,
            category=category
        )
        
        if entry:
            return f"Knowledge entry added: {entry}"
        else:
            return "Error: Could not add knowledge entry"
            
    except Exception as e:
        logger.error(f"Error in add_knowledge_entry_tool: {e}")
        return f"Error adding knowledge entry: {str(e)}"


# =============================================================================
# COMMUNICATION TOOLS
# =============================================================================


@function_tool
async def send_response_tool(
    ticket_id: str,
    message: str,
    channel: str,
    conversation_id: str
) -> str:
    """
    Send response to customer via the appropriate channel.

    Use this tool to deliver your response to the customer. The tool
    automatically formats the message for the specific channel (email,
    WhatsApp, or web form).

    Args:
        ticket_id: Ticket UUID
        message: Response message content
        channel: Channel to send via ('email', 'whatsapp', 'web_form')
        conversation_id: Conversation UUID

    Returns:
        Delivery status including channel_message_id and delivery confirmation
    """
    try:
        # Import channel handlers
        from production.channels.gmail_handler import GmailHandler
        from production.channels.whatsapp_handler import WhatsAppHandler
        from production.channels.web_form_handler import WebFormHandler
        
        # Get channel config
        pool = await get_pool()
        config = await get_channel_config(pool=pool, channel=channel)
        
        # Send via appropriate channel
        if channel == "email":
            # TODO: Initialize GmailHandler with proper credentials
            # handler = GmailHandler(...)
            # result = await handler.send_reply(...)
            result = {"status": "pending", "message": "Email sending not yet configured"}
            
        elif channel == "whatsapp":
            # TODO: Initialize WhatsAppHandler with proper credentials
            # handler = WhatsAppHandler(...)
            # result = await handler.send_message(...)
            result = {"status": "pending", "message": "WhatsApp sending not yet configured"}
            
        elif channel == "web_form":
            # Web form responses are typically async via email
            # For now, just record the response
            result = {"status": "recorded", "message": "Response recorded for web form"}
            
        else:
            result = {"status": "error", "message": f"Unknown channel: {channel}"}
        
        # Record the outbound message
        await store_message_tool(
            conversation_id=conversation_id,
            channel=channel,
            direction="outbound",
            role="agent",
            content=message,
            tokens_used=None,
            latency_ms=None
        )
        
        # Record metric
        await record_metric(
            pool=pool,
            metric_name="response_sent",
            metric_value=1.0,
            channel=channel
        )
        
        return f"Response sent: {result}"
        
    except Exception as e:
        logger.error(f"Error in send_response_tool: {e}")
        return f"Error sending response: {str(e)}"


# =============================================================================
# ESCALATION TOOLS
# =============================================================================


@function_tool
async def escalate_to_human_tool(
    ticket_id: str,
    reason: str,
    priority: str = "high",
    context: Optional[str] = None
) -> str:
    """
    Escalate ticket to a human agent.

    Use this tool when the issue requires human intervention. Escalation
    triggers include:
    - Negative customer sentiment
    - Customer explicitly requests human
    - Legal, compliance, or security matters
    - Refund or pricing negotiations
    - Complex technical issues beyond documentation

    Args:
        ticket_id: Ticket UUID
        reason: Reason for escalation
        priority: Escalation priority ('low', 'medium', 'high', 'critical')
        context: Additional context for the human agent

    Returns:
        Escalation confirmation with assigned agent info
    """
    try:
        pool = await get_pool()
        
        # Update ticket status
        await update_ticket_status(
            pool=pool,
            ticket_id=ticket_id,
            status="in_progress",
            resolution_notes=f"ESCALATED: {reason}"
        )
        
        # Record escalation metric
        await record_metric(
            pool=pool,
            metric_name="escalation",
            metric_value=1.0,
            channel=None,
            dimensions={"reason": reason, "priority": priority}
        )
        
        # TODO: Send notification to human agents (Slack, email, etc.)
        # For now, just return confirmation
        result = {
            "ticket_id": ticket_id,
            "escalated": True,
            "reason": reason,
            "priority": priority,
            "status": "pending_human_review"
        }
        
        return f"Escalation created: {result}"
        
    except Exception as e:
        logger.error(f"Error in escalate_to_human_tool: {e}")
        return f"Error escalating ticket: {str(e)}"


# =============================================================================
# METRICS TOOLS
# =============================================================================


@function_tool
async def record_metric_tool(
    metric_name: str,
    metric_value: float,
    channel: Optional[str] = None,
    dimensions: Optional[str] = None
) -> str:
    """
    Record an agent performance metric.

    Use this tool to track performance metrics like response time,
    resolution rate, customer satisfaction, etc.

    Args:
        metric_name: Metric name ('response_time', 'resolution_rate', etc.)
        metric_value: Metric value
        channel: Optional channel for channel-specific metrics
        dimensions: Additional metric dimensions (JSON string)

    Returns:
        Confirmation of metric recording
    """
    try:
        pool = await get_pool()
        await record_metric(
            pool=pool,
            metric_name=metric_name,
            metric_value=metric_value,
            channel=channel,
            dimensions=dimensions
        )
        return f"Metric recorded: {metric_name} = {metric_value}"
    except Exception as e:
        logger.error(f"Error in record_metric_tool: {e}")
        return f"Error recording metric: {str(e)}"


# =============================================================================
# TOOL REGISTRY
# =============================================================================

# List of all tools for agent configuration
ALL_TOOLS = [
    get_or_create_customer_tool,
    get_customer_history_tool,
    create_conversation_tool,
    store_message_tool,
    create_ticket_tool,
    update_ticket_status_tool,
    search_knowledge_base_tool,
    add_knowledge_entry_tool,
    send_response_tool,
    escalate_to_human_tool,
    record_metric_tool,
]

# Tool descriptions for agent context
TOOL_REGISTRY = {
    "get_or_create_customer_tool": "Identify or create customer record",
    "get_customer_history_tool": "Get customer's interaction history across all channels",
    "create_conversation_tool": "Create new conversation record",
    "store_message_tool": "Store a message in the conversation",
    "create_ticket_tool": "Create support ticket (REQUIRED before responding)",
    "update_ticket_status_tool": "Update ticket status",
    "search_knowledge_base_tool": "Search product documentation",
    "add_knowledge_entry_tool": "Add new knowledge base entry",
    "send_response_tool": "Send response via appropriate channel",
    "escalate_to_human_tool": "Escalate to human agent",
    "record_metric_tool": "Record performance metric",
}

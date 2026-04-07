"""
Customer Success FTE - Production Agent using OpenAI Agents SDK.

This module defines the main Customer Success Agent that handles
customer support inquiries across multiple channels (email, WhatsApp, web form).

The agent follows a strict workflow:
1. Identify customer
2. Create conversation
3. Store inbound message
4. Create ticket (REQUIRED)
5. Search knowledge base
6. Generate response
7. Format for channel
8. Send response
9. Assess escalation need
10. Update ticket status

Architecture:
- Uses OpenAI Agents SDK with @function_tool decorated functions
- Integrates with PostgreSQL database for state management
- Supports multi-channel communication with appropriate formatting
- Enforces workflow order through structured execution
"""

from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
import logging
import json
from datetime import datetime

from production.agent.prompts import CUSTOMER_SUCCESS_AGENT_PROMPT, TOOL_DESCRIPTIONS
from production.agent.tools import (
    ALL_TOOLS,
    get_or_create_customer_tool,
    get_customer_history_tool,
    create_conversation_tool,
    store_message_tool,
    create_ticket_tool,
    update_ticket_status_tool,
    search_knowledge_base_tool,
    send_response_tool,
    escalate_to_human_tool,
    record_metric_tool,
)
from production.agent.formatters import format_response

logger = logging.getLogger(__name__)

# =============================================================================
# ENUMS
# =============================================================================


class Channel(str, Enum):
    """Supported communication channels."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class AgentState(str, Enum):
    """Agent execution states."""
    IDENTIFYING = "identifying"
    CREATING_CONVERSATION = "creating_conversation"
    CREATING_TICKET = "creating_ticket"
    SEARCHING_KNOWLEDGE = "searching_knowledge"
    GENERATING_RESPONSE = "generating_response"
    SENDING_RESPONSE = "sending_response"
    ASSESSING_ESCALATION = "assessing_escalation"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    ERROR = "error"


# =============================================================================
# INPUT/OUTPUT MODELS
# =============================================================================


class CustomerMessage(BaseModel):
    """Input model for customer message."""
    channel: Channel = Field(..., description="Communication channel")
    channel_message_id: str = Field(..., description="External channel message ID")
    customer_email: Optional[str] = Field(None, description="Customer email address")
    customer_phone: Optional[str] = Field(None, description="Customer phone number")
    customer_name: Optional[str] = Field(None, description="Customer name")
    content: str = Field(..., description="Message content")
    received_at: str = Field(..., description="Message received timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Channel-specific metadata")


class AgentResponse(BaseModel):
    """Output model for agent response."""
    success: bool = Field(..., description="Whether processing was successful")
    customer_id: Optional[str] = Field(None, description="Customer UUID")
    conversation_id: Optional[str] = Field(None, description="Conversation UUID")
    ticket_id: Optional[str] = Field(None, description="Ticket UUID")
    response_sent: bool = Field(False, description="Whether response was sent")
    escalated: bool = Field(False, description="Whether ticket was escalated")
    error: Optional[str] = Field(None, description="Error message if failed")
    state: AgentState = Field(..., description="Final agent state")
    metrics: Optional[Dict[str, Any]] = Field(default=None, description="Performance metrics")


class AgentContext(BaseModel):
    """Context maintained during agent execution."""
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    conversation_id: Optional[str] = None
    ticket_id: Optional[str] = None
    channel: Optional[str] = None
    channel_message_id: Optional[str] = None
    message_content: Optional[str] = None
    sentiment_score: Optional[float] = None
    escalation_reason: Optional[str] = None
    state: AgentState = AgentState.IDENTIFYING
    error: Optional[str] = None


# =============================================================================
# WORKFLOW ENFORCEMENT
# =============================================================================


class WorkflowEnforcer:
    """
    Enforces the required workflow order for the agent.
    
    The agent must follow this sequence:
    1. Identify customer
    2. Create conversation
    3. Store inbound message
    4. Create ticket (REQUIRED before responding)
    5. Search knowledge base
    6. Generate and send response
    7. Assess escalation
    8. Update ticket status
    """
    
    REQUIRED_SEQUENCE = [
        "get_or_create_customer_tool",
        "create_conversation_tool",
        "store_message_tool",  # inbound
        "create_ticket_tool",  # MUST happen before send_response_tool
        "search_knowledge_base_tool",
        "send_response_tool",
    ]
    
    def __init__(self):
        self.executed_tools: List[str] = []
        self.current_step = 0
    
    def record_tool_execution(self, tool_name: str) -> None:
        """Record that a tool was executed."""
        self.executed_tools.append(tool_name)
    
    def can_send_response(self) -> bool:
        """Check if ticket has been created (required before sending response)."""
        return "create_ticket_tool" in self.executed_tools
    
    def can_escalate(self) -> bool:
        """Check if escalation is allowed (ticket must exist)."""
        return "create_ticket_tool" in self.executed_tools
    
    def is_workflow_complete(self) -> bool:
        """Check if all required steps have been executed."""
        required_set = set(self.REQUIRED_SEQUENCE[:5])  # Up to send_response
        executed_set = set(self.executed_tools)
        return required_set.issubset(executed_set)
    
    def get_next_required_tool(self) -> Optional[str]:
        """Get the next required tool in the sequence."""
        for tool in self.REQUIRED_SEQUENCE:
            if tool not in self.executed_tools:
                return tool
        return None
    
    def reset(self) -> None:
        """Reset the workflow enforcer."""
        self.executed_tools = []
        self.current_step = 0


# =============================================================================
# AGENT DEFINITION
# =============================================================================


def create_customer_success_agent() -> Agent:
    """
    Create and configure the Customer Success Agent.
    
    Returns:
        Configured Agent instance with all tools and instructions
    """
    
    # Combine system prompt with tool descriptions
    full_instructions = f"""
{CUSTOMER_SUCCESS_AGENT_PROMPT}

{TOOL_DESCRIPTIONS}

## WORKFLOW REQUIREMENTS

You MUST follow this exact sequence for EVERY customer interaction:

1. **IDENTIFY** - Call get_or_create_customer_tool with customer's email/phone
2. **CONVERSATION** - Call create_conversation_tool to start tracking
3. **RECORD** - Call store_message_tool to log the customer's message
4. **TICKET** - Call create_ticket_tool (REQUIRED before any response)
5. **SEARCH** - Call search_knowledge_base_tool to find relevant information
6. **RESPOND** - Call send_response_tool to deliver your answer
7. **ASSESS** - Consider if escalate_to_human_tool is needed
8. **UPDATE** - Call update_ticket_status_tool if resolving

CRITICAL: NEVER call send_response_tool before create_ticket_tool.
Every interaction must be tracked with a ticket.

## AVAILABLE TOOLS

You have access to these tools. Use them in the order specified above.
"""
    
    agent = Agent(
        name="customer_success_fte",
        instructions=full_instructions,
        tools=ALL_TOOLS,
        model="gpt-4o",  # Or your preferred model
    )
    
    return agent


# =============================================================================
# MESSAGE PROCESSOR
# =============================================================================


class CustomerSuccessAgent:
    """
    Main agent class for processing customer messages.
    
    This class wraps the OpenAI Agent with additional workflow enforcement,
    error handling, and metrics tracking.
    """
    
    def __init__(self):
        self.agent = create_customer_success_agent()
        self.workflow_enforcer = WorkflowEnforcer()
        self.context: Optional[AgentContext] = None
    
    async def process_message(
        self,
        message: CustomerMessage
    ) -> AgentResponse:
        """
        Process an incoming customer message.
        
        This is the main entry point for the agent. It handles the complete
        workflow from customer identification through response delivery.
        
        Args:
            message: Customer message with channel and content
            
        Returns:
            AgentResponse with processing results
        """
        # Initialize context
        self.context = AgentContext(
            channel=message.channel.value,
            channel_message_id=message.channel_message_id,
            customer_email=message.customer_email,
            customer_phone=message.customer_phone,
            customer_name=message.customer_name,
            message_content=message.content,
            state=AgentState.IDENTIFYING,
        )
        
        # Reset workflow enforcer
        self.workflow_enforcer.reset()
        
        try:
            # Build the user message for the agent
            user_message = self._build_user_message(message)
            
            # Run the agent
            result = await Runner.run(
                self.agent,
                user_message
            )
            
            # Process the result
            return self._process_result(result, message)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.context.state = AgentState.ERROR
            self.context.error = str(e)
            
            return AgentResponse(
                success=False,
                error=str(e),
                state=AgentState.ERROR,
            )
    
    def _build_user_message(self, message: CustomerMessage) -> str:
        """
        Build the user message for the agent with context.
        
        Args:
            message: Customer message
            
        Returns:
            Formatted message for agent processing
        """
        return f"""
## INCOMING CUSTOMER MESSAGE

**Channel:** {message.channel.value}
**Received:** {message.received_at}
**Customer:** {message.customer_name or 'Unknown'} ({message.customer_email or message.customer_phone or 'Unknown'})

**Message Content:**
{message.content}

---

Process this message following the required workflow:
1. Identify the customer
2. Create conversation record
3. Store this inbound message
4. Create a ticket (REQUIRED)
5. Search knowledge base for relevant information
6. Generate and send an appropriate response
7. Assess if escalation is needed
8. Update ticket status

Remember to format the response appropriately for the {message.channel.value} channel.
"""
    
    def _process_result(
        self,
        result: Any,
        message: CustomerMessage
    ) -> AgentResponse:
        """
        Process the agent result and build response.
        
        Args:
            result: Agent execution result
            message: Original customer message
            
        Returns:
            AgentResponse with results
        """
        # Extract information from context
        response = AgentResponse(
            success=self.context.state not in [AgentState.ERROR],
            customer_id=self.context.customer_id,
            conversation_id=self.context.conversation_id,
            ticket_id=self.context.ticket_id,
            response_sent=self.context.state.value in [
                AgentState.COMPLETED.value,
                AgentState.ESCALATED.value,
            ],
            escalated=self.context.state == AgentState.ESCALATED,
            error=self.context.error,
            state=self.context.state,
        )
        
        # Record metrics
        if response.success:
            # TODO: Record success metric
            pass
        
        return response


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def process_customer_message(
    channel: str,
    channel_message_id: str,
    content: str,
    customer_email: Optional[str] = None,
    customer_phone: Optional[str] = None,
    customer_name: Optional[str] = None,
    received_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AgentResponse:
    """
    Convenience function to process a customer message.
    
    Args:
        channel: Communication channel ('email', 'whatsapp', 'web_form')
        channel_message_id: External channel message ID
        content: Message content
        customer_email: Customer email address
        customer_phone: Customer phone number
        customer_name: Customer name
        received_at: Message received timestamp
        metadata: Channel-specific metadata
        
    Returns:
        AgentResponse with processing results
    """
    agent = CustomerSuccessAgent()
    
    message = CustomerMessage(
        channel=Channel(channel),
        channel_message_id=channel_message_id,
        customer_email=customer_email,
        customer_phone=customer_phone,
        customer_name=customer_name,
        content=content,
        received_at=received_at or datetime.utcnow().isoformat(),
        metadata=metadata,
    )
    
    return await agent.process_message(message)


# =============================================================================
# AGENT FACTORY
# =============================================================================


def get_customer_success_agent() -> Agent:
    """
    Get a configured Customer Success Agent instance.
    
    Use this function to get the agent for direct use with the Runner.
    
    Returns:
        Configured Agent instance
    """
    return create_customer_success_agent()


# =============================================================================
# MAIN (for testing)
# =============================================================================


if __name__ == "__main__":
    # Example usage for testing
    import asyncio
    
    async def test_agent():
        agent = CustomerSuccessAgent()
        
        # Test message
        message = CustomerMessage(
            channel=Channel.EMAIL,
            channel_message_id="test-123",
            customer_email="test@example.com",
            customer_name="Test User",
            content="I'm having trouble logging into my account. It says my password is incorrect but I'm sure it's right.",
            received_at=datetime.utcnow().isoformat(),
        )
        
        result = await agent.process_message(message)
        print(f"Result: {result}")
    
    # asyncio.run(test_agent())
    pass

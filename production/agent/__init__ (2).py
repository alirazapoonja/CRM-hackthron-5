"""
Customer Success FTE Agent package.

This package contains the production-ready Customer Success Agent
implementation using OpenAI Agents SDK.

Components:
- prompts: System prompts and instructions
- tools: @function_tool decorated functions
- formatters: Channel-aware response formatting
- customer_success_agent: Main agent definition and processor
"""

from production.agent.prompts import (
    CUSTOMER_SUCCESS_AGENT_PROMPT,
    ESCALATION_PROMPT,
    EMAIL_RESPONSE_PROMPT,
    WHATSAPP_RESPONSE_PROMPT,
    WEB_FORM_RESPONSE_PROMPT,
    TOOL_DESCRIPTIONS,
)

from production.agent.tools import (
    # Tools
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
    # Registry
    ALL_TOOLS,
    TOOL_REGISTRY,
    # Enums
    Channel,
    TicketPriority,
    TicketCategory,
    TicketStatus,
    MessageRole,
    MessageDirection,
)

from production.agent.formatters import (
    format_response,
    format_for_email,
    format_for_whatsapp,
    format_for_web_form,
    split_message,
    adapt_tone,
    format_error_response,
)

from production.agent.customer_success_agent import (
    CustomerSuccessAgent,
    process_customer_message,
    get_customer_success_agent,
    create_customer_success_agent,
    CustomerMessage,
    AgentResponse,
    AgentState,
    WorkflowEnforcer,
)

__all__ = [
    # Prompts
    "CUSTOMER_SUCCESS_AGENT_PROMPT",
    "ESCALATION_PROMPT",
    "EMAIL_RESPONSE_PROMPT",
    "WHATSAPP_RESPONSE_PROMPT",
    "WEB_FORM_RESPONSE_PROMPT",
    "TOOL_DESCRIPTIONS",
    # Tools
    "get_or_create_customer_tool",
    "get_customer_history_tool",
    "create_conversation_tool",
    "store_message_tool",
    "create_ticket_tool",
    "update_ticket_status_tool",
    "search_knowledge_base_tool",
    "add_knowledge_entry_tool",
    "send_response_tool",
    "escalate_to_human_tool",
    "record_metric_tool",
    "ALL_TOOLS",
    "TOOL_REGISTRY",
    # Tool Enums
    "Channel",
    "TicketPriority",
    "TicketCategory",
    "TicketStatus",
    "MessageRole",
    "MessageDirection",
    # Formatters
    "format_response",
    "format_for_email",
    "format_for_whatsapp",
    "format_for_web_form",
    "split_message",
    "adapt_tone",
    "format_error_response",
    # Agent
    "CustomerSuccessAgent",
    "process_customer_message",
    "get_customer_success_agent",
    "create_customer_success_agent",
    "CustomerMessage",
    "AgentResponse",
    "AgentState",
    "WorkflowEnforcer",
]

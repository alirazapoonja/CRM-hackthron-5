"""
TaskFlow Pro Customer Success FTE - MCP Server
Exercise 1.4: Build the MCP Server

Model Context Protocol (MCP) server exposing the agent's capabilities as tools.
This allows the agent to interact with external systems in a standardized way.

Tools exposed:
1. search_knowledge_base(query) → relevant docs
2. create_ticket(customer_id, issue, priority, channel) → ticket_id
3. get_customer_history(customer_id) → past interactions across ALL channels
4. escalate_to_human(ticket_id, reason) → escalation_id
5. send_response(ticket_id, message, channel) → delivery_status
"""

import asyncio
import uuid
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging

# Try to import MCP, provide fallback for prototype
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from mcp.server.stdio import stdio_server
    # Check if Server has the expected API
    test_server = Server("test")
    if not hasattr(test_server, 'tool'):
        raise AttributeError("Server doesn't have tool method - different MCP version")
    MCP_AVAILABLE = True
    print("MCP library available - running in full MCP mode")
except (ImportError, AttributeError) as e:
    MCP_AVAILABLE = False
    print(f"MCP not available - running in prototype mode ({e})")
    print("Install with: pip install mcp")
    
    # Mock MCP classes for prototype
    class Server:
        """Mock MCP Server for prototype."""
        
        def __init__(self, name: str):
            self.name = name
            self.tools: Dict[str, callable] = {}
            self._running = False
        
        def tool(self, name: str = None):
            """Decorator to register a tool."""
            def decorator(func):
                tool_name = name or func.__name__
                self.tools[tool_name] = func
                # Also make it accessible as a method
                setattr(self, tool_name, func)
                print(f"  Registered tool: {tool_name}")
                return func
            return decorator
        
        async def run(self):
            """Run the server (mock implementation)."""
            print(f"MCP Server '{self.name}' running in prototype mode")
            print(f"Available tools: {list(self.tools.keys())}")
            self._running = True
            
            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)
        
        def list_tools(self) -> List[Dict]:
            """List all registered tools."""
            return [
                {
                    'name': name,
                    'description': func.__doc__ or 'No description',
                    'function': func
                }
                for name, func in self.tools.items()
            ]
    
    class TextContent:
        """Mock TextContent for prototype."""
        def __init__(self, text: str):
            self.text = text
            self.type = "text"


class Channel(str, Enum):
    """Supported communication channels."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


# =============================================================================
# LOGGING SETUP
# =============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# IN-MEMORY DATA STORE
# =============================================================================

class DataStore:
    """
    In-memory data store for MCP server prototype.
    
    This stores customers, tickets, conversations, and messages.
    In production, this will be replaced with PostgreSQL.
    """
    
    def __init__(self):
        self.customers: Dict[str, dict] = {}
        self.tickets: Dict[str, dict] = {}
        self.conversations: Dict[str, dict] = {}
        self.messages: Dict[str, dict] = {}
        self.escalations: Dict[str, dict] = {}
        self.knowledge_base: List[dict] = []
        
        # Indexes
        self.customer_email_index: Dict[str, str] = {}
        self.customer_phone_index: Dict[str, str] = {}
        
        # Initialize knowledge base
        self._init_knowledge_base()
    
    def _init_knowledge_base(self):
        """Initialize knowledge base with sample articles."""
        self.knowledge_base = [
            {
                'id': 'kb_001',
                'title': 'Creating Recurring Tasks',
                'keywords': ['recurring', 'repeat', 'repeating', 'frequency', 'daily', 'weekly', 'monthly'],
                'content': """To create a recurring task:
1. Open or create the task you want to repeat
2. Click the due date field
3. Select "Repeat"
4. Choose frequency: Daily, Weekly, Monthly, Yearly, or Custom
5. Set end condition: Never, After X occurrences, or On specific date

Note: Custom recurrence (like bi-weekly) is available on Pro and higher plans."""
            },
            {
                'id': 'kb_002',
                'title': 'Gantt Chart Availability',
                'keywords': ['gantt', 'chart', 'timeline', 'view'],
                'content': """Gantt charts are available on Pro and Enterprise plans only.

To access Gantt view:
1. Open your project
2. Click the view selector (top right)
3. Choose "Gantt"

If you don't see the Gantt option:
- Verify you're on Pro or Enterprise plan (check Settings → Billing)
- Ensure you have project admin permissions
- Try refreshing the page"""
            },
            {
                'id': 'kb_003',
                'title': 'Password Reset',
                'keywords': ['password', 'reset', 'login', 'forgot', 'access'],
                'content': """To reset your password:
1. Go to the login page
2. Click "Forgot Password?"
3. Enter your email address
4. Check your email for a reset link
5. Click the link and create a new password

The reset link expires after 24 hours. If you don't receive the email, check your spam folder."""
            },
            {
                'id': 'kb_004',
                'title': 'File Upload Limits',
                'keywords': ['file', 'upload', 'size', 'limit', 'attachment'],
                'content': """File upload limits by plan:
- Free: 100MB per file
- Pro: 2GB per file
- Business: 5GB per file
- Enterprise: 5GB per file

Blocked file types: .exe, .bat (security restrictions)

If upload fails:
1. Check file size against your plan limit
2. Verify file type is allowed
3. Try a different browser
4. Check your internet connection"""
            },
            {
                'id': 'kb_005',
                'title': 'Slack Integration Setup',
                'keywords': ['slack', 'integration', 'notification', 'connect'],
                'content': """To connect Slack:
1. Go to Settings → Integrations
2. Find Slack and click "Connect"
3. Authorize TaskFlow Pro in Slack
4. Choose which projects to sync
5. Configure notification preferences

To receive notifications in a specific channel:
1. After connecting, go to Slack notification settings
2. Choose "Custom channel"
3. Select the channel (e.g., #project-updates)
4. Filter by project if needed"""
            },
            {
                'id': 'kb_006',
                'title': 'Export Your Data',
                'keywords': ['export', 'download', 'data', 'csv', 'json', 'backup'],
                'content': """To export your data:
1. Go to Settings → Export
2. Choose format: JSON or CSV
3. Select what to export: Tasks, Projects, or All
4. Click "Request Export"

For large workspaces, exports are emailed within 24 hours.
For small exports, download starts immediately."""
            },
            {
                'id': 'kb_007',
                'title': 'Adding Team Members',
                'keywords': ['invite', 'member', 'team', 'add', 'guest'],
                'content': """To invite team members:
1. Go to Project Settings → Members
2. Click "Invite Members"
3. Enter email addresses (separate multiple with commas)
4. Choose role: Member (full access) or Guest (limited access)
5. Click "Send Invites"

Guest users can be added to multiple projects.
Guest permissions: View assigned tasks, add comments, upload files.
Guests cannot: Create projects, see billing, manage members."""
            },
            {
                'id': 'kb_008',
                'title': 'GitHub Integration',
                'keywords': ['github', 'integration', 'commit', 'pull request', 'sync'],
                'content': """To connect GitHub:
1. Go to Settings → Integrations
2. Find GitHub and click "Connect"
3. Authorize access to your repositories
4. Link specific repos to projects

Features:
- Attach GitHub issues to TaskFlow tasks
- See commit history in task details
- Auto-complete tasks when PRs are merged

If sync stops working:
1. Go to Settings → Integrations → GitHub
2. Click "Reconnect"
3. Verify repository permissions
4. Check GitHub API status"""
            }
        ]
    
    # -------------------------------------------------------------------------
    # Customer Operations
    # -------------------------------------------------------------------------
    
    def create_customer(self, email: str = None, phone: str = None, name: str = None) -> str:
        """Create or get existing customer."""
        # Check if customer already exists
        if email and email.lower() in self.customer_email_index:
            return self.customer_email_index[email.lower()]
        if phone and phone in self.customer_phone_index:
            return self.customer_phone_index[phone]
        
        # Create new customer
        customer_id = str(uuid.uuid4())
        self.customers[customer_id] = {
            'id': customer_id,
            'email': email,
            'phone': phone,
            'name': name,
            'created_at': datetime.utcnow().isoformat(),
            'plan_type': 'free',
            'total_interactions': 0,
            'total_tickets': 0
        }
        
        # Add to indexes
        if email:
            self.customer_email_index[email.lower()] = customer_id
        if phone:
            self.customer_phone_index[phone] = customer_id
        
        logger.info(f"Created customer: {customer_id} ({email or phone})")
        return customer_id
    
    def get_customer(self, customer_id: str) -> Optional[dict]:
        """Get customer by ID."""
        return self.customers.get(customer_id)
    
    def get_customer_by_email(self, email: str) -> Optional[dict]:
        """Get customer by email."""
        customer_id = self.customer_email_index.get(email.lower())
        if customer_id:
            return self.customers[customer_id]
        return None
    
    def get_customer_by_phone(self, phone: str) -> Optional[dict]:
        """Get customer by phone."""
        customer_id = self.customer_phone_index.get(phone)
        if customer_id:
            return self.customers[customer_id]
        return None
    
    # -------------------------------------------------------------------------
    # Ticket Operations
    # -------------------------------------------------------------------------
    
    def create_ticket(self, customer_id: str, issue: str, priority: str, 
                      channel: str, category: str = None) -> str:
        """Create a new support ticket."""
        ticket_id = str(uuid.uuid4())
        
        # Get customer info
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        self.tickets[ticket_id] = {
            'id': ticket_id,
            'customer_id': customer_id,
            'issue': issue,
            'priority': priority,
            'channel': channel,
            'category': category,
            'status': 'open',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'resolved_at': None,
            'escalated': False,
            'escalation_reason': None,
            'assigned_to': None,
            'messages': []
        }
        
        # Update customer stats
        customer['total_tickets'] += 1
        
        logger.info(f"Created ticket: {ticket_id} for customer {customer_id}")
        return ticket_id
    
    def get_ticket(self, ticket_id: str) -> Optional[dict]:
        """Get ticket by ID."""
        return self.tickets.get(ticket_id)
    
    def update_ticket(self, ticket_id: str, updates: dict):
        """Update ticket fields."""
        if ticket_id in self.tickets:
            self.tickets[ticket_id].update(updates)
            self.tickets[ticket_id]['updated_at'] = datetime.utcnow().isoformat()
    
    def add_message_to_ticket(self, ticket_id: str, content: str, role: str, 
                               channel: str, direction: str = 'inbound') -> str:
        """Add message to ticket."""
        message_id = str(uuid.uuid4())
        message = {
            'id': message_id,
            'ticket_id': ticket_id,
            'content': content,
            'role': role,
            'channel': channel,
            'direction': direction,
            'created_at': datetime.utcnow().isoformat()
        }
        
        self.messages[message_id] = message
        
        # Add to ticket's message list
        if ticket_id in self.tickets:
            self.tickets[ticket_id]['messages'].append(message_id)
        
        return message_id
    
    def get_ticket_messages(self, ticket_id: str) -> List[dict]:
        """Get all messages for a ticket."""
        if ticket_id not in self.tickets:
            return []
        
        message_ids = self.tickets[ticket_id].get('messages', [])
        return [self.messages[mid] for mid in message_ids if mid in self.messages]
    
    # -------------------------------------------------------------------------
    # Escalation Operations
    # -------------------------------------------------------------------------
    
    def create_escalation(self, ticket_id: str, reason: str, urgency: str = 'normal') -> str:
        """Create escalation record."""
        escalation_id = str(uuid.uuid4())
        
        self.escalations[escalation_id] = {
            'id': escalation_id,
            'ticket_id': ticket_id,
            'reason': reason,
            'urgency': urgency,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'assigned_to': None,
            'resolved_at': None
        }
        
        # Update ticket
        if ticket_id in self.tickets:
            self.tickets[ticket_id]['escalated'] = True
            self.tickets[ticket_id]['escalation_reason'] = reason
            self.tickets[ticket_id]['status'] = 'escalated'
        
        logger.info(f"Created escalation: {escalation_id} for ticket {ticket_id}")
        return escalation_id
    
    # -------------------------------------------------------------------------
    # Knowledge Base Operations
    # -------------------------------------------------------------------------
    
    def search_knowledge_base(self, query: str, max_results: int = 5) -> List[dict]:
        """Search knowledge base by keywords."""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored_results = []
        for article in self.knowledge_base:
            # Count keyword matches
            matches = sum(1 for keyword in article['keywords'] 
                         if any(kw in query_lower for kw in keyword.split()))
            
            # Also check title match
            if any(word in article['title'].lower() for word in query_words):
                matches += 2
            
            if matches > 0:
                scored_results.append({
                    **article,
                    'relevance_score': matches
                })
        
        # Sort by relevance and return top results
        scored_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return scored_results[:max_results]
    
    # -------------------------------------------------------------------------
    # Customer History Operations
    # -------------------------------------------------------------------------
    
    def get_customer_history(self, customer_id: str) -> List[dict]:
        """Get customer's ticket history."""
        tickets = [t for t in self.tickets.values() if t['customer_id'] == customer_id]
        return sorted(tickets, key=lambda t: t['created_at'], reverse=True)


# Global data store instance
store = DataStore()


# =============================================================================
# MCP SERVER DEFINITION
# =============================================================================

if MCP_AVAILABLE:
    server = Server("taskflow-customer-success-fte")
else:
    server = Server("taskflow-customer-success-fte")


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

@server.tool("search_knowledge_base")
async def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """
    Search product documentation for relevant information.
    
    Use this when the customer asks questions about product features,
    how to use something, or needs technical information.
    
    Args:
        query: The search query from the customer
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        Formatted search results with relevance scores
    """
    logger.info(f"Searching knowledge base for: {query}")
    
    results = store.search_knowledge_base(query, max_results)
    
    if not results:
        return "No relevant documentation found. Consider escalating to human support."
    
    formatted = []
    for r in results:
        formatted.append(f"**{r['title']}** (relevance: {r['relevance_score']})\n{r['content']}")
    
    return "\n\n---\n\n".join(formatted)


@server.tool("create_ticket")
async def create_ticket(
    customer_id: str, 
    issue: str, 
    priority: str = "medium",
    channel: Channel = Channel.WEB_FORM,
    category: str = None
) -> str:
    """
    Create a support ticket for tracking customer interactions.
    
    ALWAYS create a ticket at the start of every conversation.
    Include the source channel for proper tracking.
    
    Args:
        customer_id: Customer identifier (email or UUID)
        issue: Brief description of the issue
        priority: Priority level (low, medium, high, urgent)
        channel: Source channel (email, whatsapp, web_form)
        category: Issue category (technical, billing, how_to, etc.)
    
    Returns:
        Ticket ID for future reference
    """
    logger.info(f"Creating ticket for customer {customer_id} via {channel}")
    
    try:
        # Check if customer_id is an email (lookup or create customer)
        if '@' in customer_id:
            customer = store.get_customer_by_email(customer_id)
            if not customer:
                customer_id = store.create_customer(email=customer_id)
            else:
                customer_id = customer['id']
        
        ticket_id = store.create_ticket(
            customer_id=customer_id,
            issue=issue,
            priority=priority,
            channel=channel.value if isinstance(channel, Channel) else channel,
            category=category
        )
        
        return f"Ticket created: {ticket_id}"
        
    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        return f"Error creating ticket: {str(e)}"


@server.tool("get_customer_history")
async def get_customer_history(customer_id: str) -> str:
    """
    Get customer's complete interaction history across ALL channels.
    
    Use this to understand context from previous conversations,
    even if they happened on a different channel.
    
    Args:
        customer_id: Customer identifier (UUID or email)
    
    Returns:
        Formatted customer history with all interactions
    """
    logger.info(f"Getting history for customer {customer_id}")
    
    try:
        # Lookup customer by email if needed
        if '@' in customer_id:
            customer = store.get_customer_by_email(customer_id)
            if not customer:
                return f"No customer found with email: {customer_id}"
            customer_id = customer['id']
        
        customer = store.get_customer(customer_id)
        if not customer:
            return f"No customer found with ID: {customer_id}"
        
        history = store.get_customer_history(customer_id)
        
        if not history:
            return f"Customer {customer.get('name', customer_id)} has no previous interactions."
        
        formatted = [f"Customer: {customer.get('name', 'Unknown')} ({customer.get('email', 'N/A')})"]
        formatted.append(f"Plan: {customer.get('plan_type', 'Unknown')}")
        formatted.append(f"Total tickets: {len(history)}\n")
        
        for ticket in history[:5]:  # Last 5 tickets
            messages = store.get_ticket_messages(ticket['id'])
            formatted.append(f"📋 Ticket: {ticket['id'][:8]}...")
            formatted.append(f"   Status: {ticket['status']}")
            formatted.append(f"   Channel: {ticket['channel']}")
            formatted.append(f"   Issue: {ticket['issue'][:50]}...")
            formatted.append(f"   Created: {ticket['created_at'][:10]}")
            formatted.append(f"   Messages: {len(messages)}")
            formatted.append("")
        
        return "\n".join(formatted)
        
    except Exception as e:
        logger.error(f"Error getting customer history: {e}")
        return f"Error retrieving customer history: {str(e)}"


@server.tool("escalate_to_human")
async def escalate_to_human(
    ticket_id: str, 
    reason: str,
    urgency: str = "normal"
) -> str:
    """
    Escalate a ticket to human support.
    
    Use this when:
    - Customer asks about pricing or refunds
    - Customer sentiment is negative or angry
    - You cannot find relevant information
    - Customer explicitly requests human help
    - Security or legal issues are mentioned
    
    Args:
        ticket_id: The ticket to escalate
        reason: Reason for escalation (pricing_inquiry, refund_request, 
                security_incident, angry_customer, technical_bug, etc.)
        urgency: Urgency level (normal, high, critical)
    
    Returns:
        Escalation confirmation with reference ID
    """
    logger.info(f"Escalating ticket {ticket_id} for reason: {reason}")
    
    try:
        ticket = store.get_ticket(ticket_id)
        if not ticket:
            return f"Error: Ticket {ticket_id} not found."
        
        escalation_id = store.create_escalation(ticket_id, reason, urgency)
        
        # Map urgency to response time
        response_times = {
            'critical': '1 hour',
            'high': '4 hours',
            'normal': '24 hours'
        }
        response_time = response_times.get(urgency, '24 hours')
        
        return f"""Escalation created successfully!

Reference: ESC-{escalation_id[:8].upper()}
Ticket: {ticket_id[:8]}...
Reason: {reason}
Urgency: {urgency}
Expected response time: {response_time}

A human agent will review and reach out to the customer."""
        
    except Exception as e:
        logger.error(f"Error creating escalation: {e}")
        return f"Error creating escalation: {str(e)}"


@server.tool("send_response")
async def send_response(
    ticket_id: str, 
    message: str, 
    channel: Channel
) -> str:
    """
    Send response to customer via their preferred channel.
    
    The response will be automatically formatted for the channel:
    - Email: Formal with greeting and signature
    - WhatsApp: Concise and conversational
    - Web Form: Semi-formal
    
    Args:
        ticket_id: The ticket to respond to
        message: The response message content
        channel: Channel to send via (email, whatsapp, web_form)
    
    Returns:
        Delivery status confirmation
    """
    logger.info(f"Sending response via {channel} for ticket {ticket_id}")
    
    try:
        ticket = store.get_ticket(ticket_id)
        if not ticket:
            return f"Error: Ticket {ticket_id} not found."
        
        # Format message based on channel
        if channel == Channel.EMAIL:
            customer = store.get_customer(ticket['customer_id'])
            name = customer.get('name', 'there').split()[0] if customer.get('name') else 'there'
            
            formatted = f"""Dear {name},

Thank you for reaching out to TaskFlow Support!

{message}

If you have any further questions, please don't hesitate to reply to this email.

Best regards,
TaskFlow Support Team
📧 support@taskflowpro.com
📚 https://help.taskflowpro.com"""
        
        elif channel == Channel.WHATSAPP:
            # Keep it short for WhatsApp
            if len(message) > 280:
                message = message[:277] + "..."
            formatted = f"{message}\n\n📱 Reply for more help or type 'human' for live support."
        
        else:  # WEB_FORM
            formatted = f"""{message}

---
📖 Need more help? Reply to this message or visit our support portal.

Thanks,
TaskFlow Support"""
        
        # Store the response
        store.add_message_to_ticket(
            ticket_id, 
            formatted, 
            role='agent', 
            channel=channel.value if isinstance(channel, Channel) else channel,
            direction='outbound'
        )
        
        # Update ticket status
        store.update_ticket(ticket_id, {'status': 'pending'})
        
        return f"Response sent via {channel.value if isinstance(channel, Channel) else channel}: delivered"
        
    except Exception as e:
        logger.error(f"Error sending response: {e}")
        return f"Error sending response: {str(e)}"


# =============================================================================
# ADDITIONAL HELPER TOOLS
# =============================================================================

@server.tool("analyze_sentiment")
async def analyze_sentiment(text: str) -> str:
    """
    Analyze the sentiment of customer message.
    
    Args:
        text: The customer message text
    
    Returns:
        Sentiment score (0.0-1.0) and classification
    """
    # Simple keyword-based sentiment
    positive_words = {'love', 'great', 'awesome', 'thanks', 'helpful', 'amazing'}
    negative_words = {'hate', 'terrible', 'awful', 'frustrated', 'angry', 'broken'}
    anger_signals = {'!!!', 'ridiculous', 'unacceptable', 'NOW', 'URGENT'}
    
    text_lower = text.lower()
    
    positive_count = sum(1 for w in positive_words if w in text_lower)
    negative_count = sum(1 for w in negative_words if w in text_lower)
    anger_count = sum(1 for s in anger_signals if s in text)
    
    if positive_count + negative_count == 0:
        score = 0.5
    else:
        score = 0.5 + (positive_count - negative_count) / (2 * (positive_count + negative_count))
    
    # Reduce for anger signals
    score = max(0.0, score - (anger_count * 0.1))
    
    if score >= 0.7:
        classification = "positive"
    elif score >= 0.4:
        classification = "neutral"
    elif score >= 0.3:
        classification = "frustrated"
    else:
        classification = "angry"
    
    return f"Sentiment score: {score:.2f} ({classification})"


@server.tool("get_ticket_status")
async def get_ticket_status(ticket_id: str) -> str:
    """
    Get current status of a ticket.
    
    Args:
        ticket_id: The ticket ID to check
    
    Returns:
        Ticket status and details
    """
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        return f"Error: Ticket {ticket_id} not found."
    
    messages = store.get_ticket_messages(ticket_id)
    
    return f"""Ticket: {ticket_id[:8]}...
Status: {ticket['status']}
Priority: {ticket['priority']}
Channel: {ticket['channel']}
Issue: {ticket['issue']}
Created: {ticket['created_at']}
Messages: {len(messages)}"""


# =============================================================================
# DEMO AND TESTING
# =============================================================================

async def run_demo():
    """Run a demo of the MCP server tools."""
    print("\n" + "="*70)
    print("MCP SERVER - TOOL DEMO")
    print("="*70)
    print(f"MCP Available: {MCP_AVAILABLE}")
    print(f"Registered Tools: {list(server.tools.keys())}")
    
    # Demo 1: Search knowledge base
    print("\n\n" + "-"*70)
    print("1. SEARCH KNOWLEDGE BASE")
    print("-"*70)
    result = await search_knowledge_base("How do I create recurring tasks?")
    print(result[:500] + "..." if len(result) > 500 else result)
    
    # Demo 2: Create customer and ticket
    print("\n\n" + "-"*70)
    print("2. CREATE TICKET")
    print("-"*70)
    ticket_result = await create_ticket(
        customer_id="sarah@example.com",
        issue="Help with recurring tasks setup",
        priority="medium",
        channel=Channel.EMAIL,
        category="how_to"
    )
    print(ticket_result)
    
    # Extract ticket ID for subsequent calls
    ticket_id = ticket_result.split(": ")[1] if ": " in ticket_result else None
    
    # Demo 3: Get customer history
    print("\n\n" + "-"*70)
    print("3. GET CUSTOMER HISTORY")
    print("-"*70)
    history_result = await get_customer_history("sarah@example.com")
    print(history_result)
    
    # Demo 4: Send response
    print("\n\n" + "-"*70)
    print("4. SEND RESPONSE")
    print("-"*70)
    if ticket_id:
        response_result = await send_response(
            ticket_id=ticket_id,
            message="To create recurring tasks, go to the task, click due date, and select Repeat.",
            channel=Channel.EMAIL
        )
        print(response_result)
    
    # Demo 5: Escalate to human
    print("\n\n" + "-"*70)
    print("5. ESCALATE TO HUMAN")
    print("-"*70)
    # Create a pricing ticket first
    pricing_ticket = await create_ticket(
        customer_id="procurement@company.com",
        issue="Enterprise pricing inquiry for 500 users",
        priority="high",
        channel=Channel.EMAIL,
        category="pricing"
    )
    print(f"Pricing ticket: {pricing_ticket}")
    pricing_ticket_id = pricing_ticket.split(": ")[1] if ": " in pricing_ticket else None
    
    if pricing_ticket_id:
        escalation_result = await escalate_to_human(
            ticket_id=pricing_ticket_id,
            reason="pricing_inquiry",
            urgency="high"
        )
        print(escalation_result)
    
    # Demo 6: Analyze sentiment
    print("\n\n" + "-"*70)
    print("6. ANALYZE SENTIMENT")
    print("-"*70)
    sentiment_result = await analyze_sentiment("This is ridiculous!!! Fix this NOW!!!")
    print(sentiment_result)
    
    # Demo 7: Get ticket status
    print("\n\n" + "-"*70)
    print("7. GET TICKET STATUS")
    print("-"*70)
    if ticket_id:
        status_result = await get_ticket_status(ticket_id)
        print(status_result)
    
    # Demo 8: Cross-channel conversation
    print("\n\n" + "="*70)
    print("8. CROSS-CHANNEL CONVERSATION DEMO")
    print("="*70)
    
    # Customer contacts via web form
    web_ticket = await create_ticket(
        customer_id="mike@company.com",
        issue="Can't see Gantt chart option",
        priority="medium",
        channel=Channel.WEB_FORM
    )
    print(f"\nWeb form ticket: {web_ticket}")
    
    # Same customer follows up via email (should recognize customer)
    email_ticket = await create_ticket(
        customer_id="mike@company.com",
        issue="Still can't find Gantt chart - need urgent help",
        priority="high",
        channel=Channel.EMAIL
    )
    print(f"Email ticket (same customer): {email_ticket}")
    
    # Get history to show cross-channel tracking
    history = await get_customer_history("mike@company.com")
    print(f"\nCustomer history shows both tickets:")
    print(history)
    
    print("\n\n" + "="*70)
    print("MCP SERVER DEMO COMPLETE")
    print("="*70)
    print("\nTools demonstrated:")
    print("  ✅ search_knowledge_base")
    print("  ✅ create_ticket")
    print("  ✅ get_customer_history")
    print("  ✅ escalate_to_human")
    print("  ✅ send_response")
    print("  ✅ analyze_sentiment")
    print("  ✅ get_ticket_status")
    print("\nFeatures shown:")
    print("  ✅ Knowledge base search with relevance scoring")
    print("  ✅ Customer creation and identification")
    print("  ✅ Cross-channel ticket tracking")
    print("  ✅ Escalation with urgency levels")
    print("  ✅ Channel-aware response formatting")
    print("  ✅ Sentiment analysis with anger detection")


def run_server():
    """Run the MCP server."""
    print("\n" + "="*70)
    print("TASKFLOW CUSTOMER SUCCESS FTE - MCP SERVER")
    print("="*70)
    
    if MCP_AVAILABLE:
        print("\nStarting MCP server with stdio transport...")
        print("Press Ctrl+C to stop")
        
        async def run_with_stdio():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options()
                )
        
        asyncio.run(run_with_stdio())
    else:
        print("\nRunning in prototype mode (MCP library not installed)")
        print("To run in full MCP mode, install with: pip install mcp")
        print("\nStarting demo...")
        asyncio.run(run_demo())


if __name__ == "__main__":
    run_server()

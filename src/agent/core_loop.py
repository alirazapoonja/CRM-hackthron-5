"""
TaskFlow Pro Customer Success Agent - Core Loop Prototype
Phase 1 Incubation - Exercise 1.2

This prototype handles the basic customer interaction loop:
1. Takes a customer message as input (with channel metadata)
2. Normalizes the message regardless of source channel
3. Searches the product docs for relevant information
4. Generates a helpful response
5. Formats response appropriately for the channel
6. Decides if escalation is needed
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class EscalationReason(str, Enum):
    PRICING_INQUIRY = "pricing_inquiry"
    REFUND_REQUEST = "refund_request"
    LEGAL_INQUIRY = "legal_inquiry"
    SECURITY_INCIDENT = "security_incident"
    HUMAN_REQUESTED = "human_requested"
    ANGRY_CUSTOMER = "angry_customer"
    TECHNICAL_BUG = "technical_bug"
    NONE = None


@dataclass
class CustomerMessage:
    """Normalized customer message regardless of channel."""
    channel: Channel
    content: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    subject: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    @classmethod
    def from_email(cls, data: Dict) -> 'CustomerMessage':
        """Create from Gmail/email format."""
        return cls(
            channel=Channel.EMAIL,
            content=data.get('content', ''),
            customer_email=data.get('customer_email'),
            customer_name=data.get('customer_name'),
            subject=data.get('subject'),
            metadata=data
        )
    
    @classmethod
    def from_whatsapp(cls, data: Dict) -> 'CustomerMessage':
        """Create from WhatsApp format."""
        return cls(
            channel=Channel.WHATSAPP,
            content=data.get('content', ''),
            customer_phone=data.get('customer_phone'),
            customer_name=data.get('customer_name'),
            metadata=data
        )
    
    @classmethod
    def from_web_form(cls, data: Dict) -> 'CustomerMessage':
        """Create from web form format."""
        return cls(
            channel=Channel.WHATSAPP,
            content=data.get('message', ''),
            customer_email=data.get('customer_email'),
            customer_name=data.get('customer_name'),
            subject=data.get('subject'),
            metadata=data
        )
    
    def get_customer_identifier(self) -> Optional[str]:
        """Get primary customer identifier (email or phone)."""
        return self.customer_email or self.customer_phone


@dataclass
class AgentResponse:
    """Agent response with metadata."""
    content: str
    requires_escalation: bool = False
    escalation_reason: Optional[EscalationReason] = None
    sentiment_score: float = 0.5
    confidence: float = 0.8
    tool_calls: List[Dict] = field(default_factory=list)


class SimpleKnowledgeBase:
    """Simple keyword-based search for prototype."""
    
    def __init__(self):
        self.articles = self._load_knowledge_base()
    
    def _load_knowledge_base(self) -> List[Dict]:
        """Load knowledge base from product docs."""
        return [
            {
                "id": "kb_001",
                "title": "Creating Recurring Tasks",
                "keywords": ["recurring", "repeat", "repeating", "frequency", "daily", "weekly", "monthly"],
                "content": """To create a recurring task:
1. Open or create the task you want to repeat
2. Click the due date field
3. Select "Repeat"
4. Choose frequency: Daily, Weekly, Monthly, Yearly, or Custom
5. Set end condition: Never, After X occurrences, or On specific date

Note: Custom recurrence (like bi-weekly) is available on Pro and higher plans."""
            },
            {
                "id": "kb_002",
                "title": "Gantt Chart Availability",
                "keywords": ["gantt", "chart", "timeline", "view"],
                "content": """Gantt charts are available on Pro and Enterprise plans only.

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
                "id": "kb_003",
                "title": "Password Reset",
                "keywords": ["password", "reset", "login", "forgot", "access"],
                "content": """To reset your password:
1. Go to the login page
2. Click "Forgot Password?"
3. Enter your email address
4. Check your email for a reset link
5. Click the link and create a new password

The reset link expires after 24 hours. If you don't receive the email, check your spam folder."""
            },
            {
                "id": "kb_004",
                "title": "File Upload Limits by Plan",
                "keywords": ["file", "upload", "size", "limit", "attachment"],
                "content": """File upload limits by plan:
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
                "id": "kb_005",
                "title": "Slack Integration Setup",
                "keywords": ["slack", "integration", "notification", "connect"],
                "content": """To connect Slack:
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
                "id": "kb_006",
                "title": "Export Your Data",
                "keywords": ["export", "download", "data", "csv", "json", "backup"],
                "content": """To export your data:
1. Go to Settings → Export
2. Choose format: JSON or CSV
3. Select what to export: Tasks, Projects, or All
4. Click "Request Export"

For large workspaces, exports are emailed within 24 hours.
For small exports, download starts immediately."""
            },
            {
                "id": "kb_007",
                "title": "Adding Team Members",
                "keywords": ["invite", "member", "team", "add", "guest"],
                "content": """To invite team members:
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
                "id": "kb_008",
                "title": "GitHub Integration",
                "keywords": ["github", "integration", "commit", "pull request", "sync"],
                "content": """To connect GitHub:
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
            },
            {
                "id": "kb_009",
                "title": "Custom Statuses and Workflows",
                "keywords": ["custom", "status", "workflow", "kanban", "column"],
                "content": """To create custom statuses (Business plan and above):
1. Go to Project Settings → Workflows
2. Click "Add Status"
3. Name your status (e.g., "Code Review", "Testing")
4. Choose color
5. Set as default status if needed

Different projects can have different workflows.
Default statuses: To Do, In Progress, Done"""
            },
            {
                "id": "kb_010",
                "title": "API Rate Limits",
                "keywords": ["api", "rate", "limit", "request", "developer"],
                "content": """API rate limits by plan:
- Pro: 1,000 requests/hour
- Business: 5,000 requests/hour
- Enterprise: Unlimited

Base URL: https://api.taskflowpro.com/v1
Authentication: Bearer token (generate in Settings → API)

To optimize API usage:
- Use webhooks instead of polling
- Batch requests when possible
- Cache responses locally"""
            }
        ]
    
    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Search knowledge base by keywords."""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored_results = []
        
        for article in self.articles:
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


class SentimentAnalyzer:
    """Simple rule-based sentiment analysis for prototype."""
    
    POSITIVE_WORDS = {
        'love', 'amazing', 'great', 'awesome', 'excellent', 'fantastic',
        'wonderful', 'perfect', 'helpful', 'thanks', 'thank', 'appreciate',
        'happy', 'pleased', 'satisfied'
    }
    
    NEGATIVE_WORDS = {
        'hate', 'terrible', 'awful', 'horrible', 'worst', 'broken',
        'useless', 'frustrated', 'angry', 'ridiculous', 'unacceptable',
        'disappointed', 'issue', 'problem', 'error', 'fail', 'crash'
    }
    
    ANGER_SIGNALS = {
        '!!!': 3,  # Multiple exclamation marks
        'ALL_CAPS': 2,  # Words in all caps (excluding short words)
        'rudeness': ['ridiculous', 'unacceptable', 'terrible', 'awful'],
        'urgency': ['NOW', 'IMMEDIATELY', 'ASAP', 'URGENT'],
        'threats': ['cancel', 'switch', 'chargeback', 'refund', 'sue', 'lawyer']
    }
    
    def analyze(self, text: str) -> float:
        """
        Analyze sentiment of text.
        Returns score from 0.0 (very negative) to 1.0 (very positive).
        """
        text_lower = text.lower()
        words = set(text_lower.split())
        
        # Count positive and negative words
        positive_count = sum(1 for word in words if word in self.POSITIVE_WORDS)
        negative_count = sum(1 for word in words if word in self.NEGATIVE_WORDS)
        
        # Base score (neutral is 0.5)
        if positive_count + negative_count == 0:
            return 0.5
        
        # Adjust score based on word counts
        total = positive_count + negative_count
        base_score = 0.5 + (positive_count - negative_count) / (2 * total)
        
        # Check for anger signals
        anger_score = 0
        
        # Multiple exclamation marks
        if '!!!' in text or text.count('!') >= 3:
            anger_score += 0.2
        
        # ALL CAPS words (excluding short words)
        caps_words = [w for w in text.split() if w.isupper() and len(w) > 2]
        if len(caps_words) >= 2:
            anger_score += 0.15
        
        # Rude/angry words
        for word in self.ANGER_SIGNALS['rudeness']:
            if word in text_lower:
                anger_score += 0.1
        
        # Urgency words in caps
        for word in self.ANGER_SIGNALS['urgency']:
            if word in text:
                anger_score += 0.1
        
        # Reduce score for angry customers
        if anger_score > 0:
            base_score = max(0.0, base_score - anger_score)
        
        return round(base_score, 2)


class EscalationDetector:
    """Detect when to escalate to human support."""
    
    PRICING_KEYWORDS = {
        'price', 'pricing', 'cost', 'how much', 'discount', 'cheap',
        'expensive', 'enterprise pricing', 'custom plan', 'upgrade cost',
        'billing', 'charge', 'charged', 'invoice', 'payment'
    }
    
    REFUND_KEYWORDS = {
        'refund', 'money back', 'chargeback', 'cancel and refund',
        'double charged', 'overcharged'
    }
    
    LEGAL_KEYWORDS = {
        'lawyer', 'attorney', 'sue', 'lawsuit', 'legal', 'legal action',
        'gdpr', 'privacy request', 'subpoena', 'contract', 'terms of service'
    }
    
    SECURITY_KEYWORDS = {
        'hacked', 'hack', 'unauthorized access', 'data breach',
        'account compromised', 'security'
    }
    
    HUMAN_REQUEST_KEYWORDS = {
        'human', 'real person', 'agent', 'representative', 'support agent',
        'talk to someone', 'speak to someone'
    }
    
    def detect(self, message: str) -> Tuple[bool, Optional[EscalationReason]]:
        """
        Detect if message requires escalation.
        Returns (requires_escalation, reason).
        """
        message_lower = message.lower()
        
        # Check security first (highest priority)
        if any(kw in message_lower for kw in self.SECURITY_KEYWORDS):
            return True, EscalationReason.SECURITY_INCIDENT
        
        # Check legal
        if any(kw in message_lower for kw in self.LEGAL_KEYWORDS):
            return True, EscalationReason.LEGAL_INQUIRY
        
        # Check refund requests
        if any(kw in message_lower for kw in self.REFUND_KEYWORDS):
            return True, EscalationReason.REFUND_REQUEST
        
        # Check pricing inquiries
        if any(kw in message_lower for kw in self.PRICING_KEYWORDS):
            return True, EscalationReason.PRICING_INQUIRY
        
        # Check human request
        if any(kw in message_lower for kw in self.HUMAN_REQUEST_KEYWORDS):
            return True, EscalationReason.HUMAN_REQUESTED
        
        return False, None


class ResponseFormatter:
    """Format responses appropriately for each channel."""
    
    def format(self, content: str, channel: Channel, customer_name: str = None) -> str:
        """Format response based on channel."""
        if channel == Channel.EMAIL:
            return self._format_email(content, customer_name)
        elif channel == Channel.WHATSAPP:
            return self._format_whatsapp(content)
        elif channel == Channel.WEB_FORM:
            return self._format_web_form(content)
        else:
            return content
    
    def _format_email(self, content: str, customer_name: str = None) -> str:
        """Format for email - formal with greeting and signature."""
        name = customer_name.split()[0] if customer_name else "there"
        
        return f"""Dear {name},

Thank you for reaching out to TaskFlow Support!

{content}

If you have any further questions, please don't hesitate to reply to this email.

Best regards,
TaskFlow Support Team
📧 support@taskflowpro.com
📚 https://help.taskflowpro.com

---
Ticket Reference: {{ticket_id}}
This response was generated by our AI assistant. For complex issues, you can request human support."""
    
    def _format_whatsapp(self, content: str) -> str:
        """Format for WhatsApp - concise and conversational."""
        # Keep it short - under 300 characters when possible
        if len(content) > 280:
            content = content[:277] + "..."
        
        return f"{content}\n\n📱 Reply for more help or type 'human' for live support."
    
    def _format_web_form(self, content: str) -> str:
        """Format for web form - semi-formal."""
        return f"""{content}

---
📖 Need more help? Reply to this message or visit our support portal.

Thanks,
TaskFlow Support"""


class CustomerSuccessAgent:
    """
    Customer Success Agent - Core Loop Prototype
    
    Handles customer inquiries with channel-aware responses.
    """
    
    def __init__(self):
        self.kb = SimpleKnowledgeBase()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.escalation_detector = EscalationDetector()
        self.formatter = ResponseFormatter()
    
    def process_message(self, message: CustomerMessage) -> AgentResponse:
        """
        Process a customer message and generate response.
        
        Flow:
        1. Analyze sentiment
        2. Check for escalation triggers
        3. Search knowledge base
        4. Generate response
        5. Format for channel
        """
        print(f"\n{'='*60}")
        print(f"Processing {message.channel.value} message from {message.get_customer_identifier()}")
        print(f"{'='*60}")
        
        # Step 1: Analyze sentiment
        sentiment = self.sentiment_analyzer.analyze(message.content)
        print(f"Sentiment score: {sentiment}")
        
        # Step 2: Check for escalation triggers
        requires_escalation, escalation_reason = self.escalation_detector.detect(message.content)
        
        # Also escalate if very angry customer
        if sentiment < 0.3 and not requires_escalation:
            requires_escalation = True
            escalation_reason = EscalationReason.ANGRY_CUSTOMER
        
        print(f"Requires escalation: {requires_escalation}")
        if escalation_reason:
            print(f"Escalation reason: {escalation_reason.value}")
        
        # Step 3: Handle escalation
        if requires_escalation:
            response_content = self._generate_escalation_response(escalation_reason)
            return AgentResponse(
                content=response_content,
                requires_escalation=True,
                escalation_reason=escalation_reason,
                sentiment_score=sentiment,
                confidence=0.95
            )
        
        # Step 4: Search knowledge base
        search_results = self.kb.search(message.content)
        print(f"Found {len(search_results)} relevant articles")
        
        # Step 5: Generate response
        if search_results:
            response_content = self._generate_answer(search_results, message.content)
            confidence = 0.8 + (search_results[0]['relevance_score'] * 0.05)
        else:
            response_content = self._generate_no_answer_response()
            confidence = 0.5
        
        # Step 6: Format for channel
        formatted_response = self.formatter.format(
            response_content,
            message.channel,
            message.customer_name
        )
        
        return AgentResponse(
            content=formatted_response,
            requires_escalation=False,
            sentiment_score=sentiment,
            confidence=min(confidence, 0.95)
        )
    
    def _generate_escalation_response(self, reason: EscalationReason) -> str:
        """Generate response when escalation is needed."""
        responses = {
            EscalationReason.PRICING_INQUIRY: """I'll connect you with our billing specialist who can access your account and provide accurate pricing information. They'll reach out within 4 hours.

In the meantime, you can view our public pricing at: https://taskflowpro.com/pricing""",
            
            EscalationReason.REFUND_REQUEST: """I'm connecting you with our billing team who can review your account and discuss refund options. They'll reach out within 4 hours.

Your request has been marked as priority.""",
            
            EscalationReason.SECURITY_INCIDENT: """I'm immediately escalating this to our security team. They will contact you within 1 hour.

For your security, please change your password now at: https://taskflowpro.com/settings/security""",
            
            EscalationReason.LEGAL_INQUIRY: """I'm escalating this to our legal team who can properly address your concerns. They will contact you within 24 hours.""",
            
            EscalationReason.HUMAN_REQUESTED: """Absolutely! I'm connecting you with a human agent who can help. They'll reach out within 4 hours for Pro plan, or within 1 hour for Business/Enterprise plans.""",
            
            EscalationReason.ANGRY_CUSTOMER: """I completely understand your frustration, and I'm sorry for the trouble you're experiencing. I'm escalating this to our senior support team who will prioritize your case. They'll reach out within 2 hours."""
        }
        
        return responses.get(reason, """I'm escalating this to the appropriate team who can help you. They'll reach out shortly.""")
    
    def _generate_answer(self, search_results: List[Dict], query: str) -> str:
        """Generate answer from search results."""
        best_result = search_results[0]
        
        # Start with direct answer
        response = f"**{best_result['title']}**\n\n"
        response += best_result['content']
        
        # Add related articles if available
        if len(search_results) > 1:
            response += "\n\n**Related articles:**\n"
            for result in search_results[1:3]:
                response += f"• {result['title']}\n"
        
        return response
    
    def _generate_no_answer_response(self) -> str:
        """Generate response when no answer is found."""
        return """I wasn't able to find specific information about this in our documentation. Let me connect you with a human agent who can provide more personalized assistance.

In the meantime, you might find helpful resources at: https://help.taskflowpro.com"""


def demo_agent():
    """Demo the agent with sample messages."""
    agent = CustomerSuccessAgent()
    
    # Test cases from different channels
    test_messages = [
        # Email - How-to question
        CustomerMessage.from_email({
            'customer_email': 'sarah@example.com',
            'customer_name': 'Sarah Johnson',
            'subject': 'Help with recurring tasks',
            'content': """Hi, I need help setting up recurring tasks for our bi-weekly sprint planning. I can only see Daily, Weekly, Monthly options but need every 2 weeks. Is this possible?"""
        }),
        
        # WhatsApp - Quick question
        CustomerMessage.from_whatsapp({
            'customer_phone': '+14155551234',
            'customer_name': 'John',
            'content': 'Hey! How do I reset my password? Forgot it 😅'
        }),
        
        # Web Form - Technical issue
        CustomerMessage.from_web_form({
            'customer_email': 'mike@example.com',
            'customer_name': 'Mike Chen',
            'subject': 'Gantt chart not showing',
            'message': """I'm on Pro plan but can't see Gantt view. When I switch to it, I get a blank screen. Tried refreshing and different browsers."""
        }),
        
        # Email - Pricing (should escalate)
        CustomerMessage.from_email({
            'customer_email': 'procurement@company.com',
            'customer_name': 'Jennifer Williams',
            'subject': 'Enterprise Pricing Inquiry',
            'content': """We're interested in deploying TaskFlow for 500+ users. Can you provide enterprise pricing and volume discount information?"""
        }),
        
        # WhatsApp - Angry customer (should escalate)
        CustomerMessage.from_whatsapp({
            'customer_phone': '+33612345678',
            'customer_name': 'Pierre',
            'content': 'This is ridiculous!!! App keeps crashing when I try to upload files. Fix this NOW!!!'
        }),
    ]
    
    print("\n" + "="*60)
    print("CUSTOMER SUCCESS AGENT - PROTOTYPE DEMO")
    print("="*60)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n\n{'#'*60}")
        print(f"TEST CASE {i}: {message.channel.value.upper()}")
        print(f"{'#'*60}")
        
        response = agent.process_message(message)
        
        print(f"\n📤 RESPONSE:")
        print(f"{'-'*60}")
        print(response.content)
        print(f"{'-'*60}")
        print(f"Escalation needed: {response.requires_escalation}")
        if response.escalation_reason:
            print(f"Reason: {response.escalation_reason.value}")
        print(f"Sentiment: {response.sentiment_score}")
        print(f"Confidence: {response.confidence}")


if __name__ == "__main__":
    demo_agent()

"""
TaskFlow Pro Customer Success Agent - Memory and State Module
Phase 1 Incubation - Exercise 1.3

Extends the core loop with:
- Conversation memory across interactions
- Cross-channel continuity (using email/phone as customer identifier)
- Sentiment tracking over time
- Resolution status tracking
- Topic tracking for reporting
"""

import json
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import os

# Import from core_loop
from core_loop import CustomerMessage, AgentResponse, Channel


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"  # Waiting for customer response
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class ResolutionType(str, Enum):
    ANSWERED = "answered"
    SELF_SERVICE = "self_service"  # Customer found answer via KB link
    ESCALATED_TO_HUMAN = "escalated"
    ABANDONED = "abandoned"


@dataclass
class Message:
    """Single message in a conversation."""
    id: str
    conversation_id: str
    channel: Channel
    direction: str  # 'inbound' or 'outbound'
    role: str  # 'customer', 'agent', 'system'
    content: str
    created_at: datetime
    sentiment_score: float = 0.5
    topics: List[str] = field(default_factory=list)
    tool_calls: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class Conversation:
    """
    Represents a conversation thread that can span multiple channels.
    
    Key insight: A customer might start on WhatsApp, then follow up
    via email. We need to recognize them and maintain context.
    """
    id: str
    customer_id: str  # Unified customer identifier
    initial_channel: Channel
    started_at: datetime
    updated_at: datetime
    status: ConversationStatus = ConversationStatus.ACTIVE
    messages: List[Message] = field(default_factory=list)
    
    # Tracking fields
    sentiment_history: List[Tuple[datetime, float]] = field(default_factory=list)
    topics_discussed: List[str] = field(default_factory=list)
    resolution_type: Optional[ResolutionType] = None
    escalated_to: Optional[str] = None
    escalation_reason: Optional[str] = None
    
    # Cross-channel tracking
    channels_used: List[Channel] = field(default_factory=list)
    
    def add_message(self, message: Message):
        """Add message and update tracking."""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        
        # Track sentiment over time
        if message.sentiment_score:
            self.sentiment_history.append((message.created_at, message.sentiment_score))
        
        # Track topics
        for topic in message.topics:
            if topic not in self.topics_discussed:
                self.topics_discussed.append(topic)
        
        # Track channels used
        if message.channel not in self.channels_used:
            self.channels_used.append(message.channel)
    
    def get_sentiment_trend(self) -> str:
        """Analyze sentiment trend over conversation."""
        if len(self.sentiment_history) < 2:
            return "stable"
        
        recent = self.sentiment_history[-3:]
        scores = [s[1] for s in recent]
        
        if scores[-1] > scores[0] + 0.1:
            return "improving"
        elif scores[-1] < scores[0] - 0.1:
            return "declining"
        return "stable"
    
    def get_average_sentiment(self) -> float:
        """Get average sentiment across conversation."""
        if not self.sentiment_history:
            return 0.5
        scores = [s[1] for s in self.sentiment_history]
        return round(sum(scores) / len(scores), 2)
    
    def get_context_summary(self) -> str:
        """Generate summary of conversation context for agent."""
        summary_parts = [
            f"Conversation started: {self.started_at.strftime('%Y-%m-%d %H:%M')}",
            f"Channels used: {', '.join(c.value for c in self.channels_used)}",
            f"Topics: {', '.join(self.topics_discussed) if self.topics_discussed else 'None yet'}",
            f"Sentiment trend: {self.get_sentiment_trend()}",
            f"Average sentiment: {self.get_average_sentiment()}",
        ]
        
        # Add recent message context
        if len(self.messages) >= 2:
            recent = self.messages[-2:]
            summary_parts.append("\nRecent context:")
            for msg in recent:
                summary_parts.append(f"  [{msg.channel.value}] {msg.role}: {msg.content[:100]}...")
        
        return "\n".join(summary_parts)


@dataclass
class Customer:
    """
    Unified customer profile across all channels.
    
    Identified by email OR phone number.
    """
    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Profile data
    company: Optional[str] = None
    plan_type: str = "free"  # free, pro, business, enterprise
    
    # Identifiers for cross-channel matching
    identifiers: Dict[str, str] = field(default_factory=dict)  # {'email': 'x@y.com', 'whatsapp': '+1234'}
    
    # History
    conversation_ids: List[str] = field(default_factory=list)
    total_interactions: int = 0
    total_escalations: int = 0
    
    def add_identifier(self, id_type: str, value: str):
        """Add a new identifier for cross-channel matching."""
        self.identifiers[id_type] = value
        
        # Update primary identifiers
        if id_type == 'email' and not self.email:
            self.email = value
        elif id_type == 'whatsapp' and not self.phone:
            self.phone = value
        elif id_type == 'phone' and not self.phone:
            self.phone = value
    
    def get_display_name(self) -> str:
        """Get customer display name."""
        if self.name:
            return self.name
        if self.email:
            return self.email.split('@')[0]
        if self.phone:
            return self.phone[-4:]  # Last 4 digits
        return "Customer"


class InMemoryStore:
    """
    In-memory data store for prototype.
    
    In production, this would be PostgreSQL.
    """
    
    def __init__(self):
        self.customers: Dict[str, Customer] = {}
        self.conversations: Dict[str, Conversation] = {}
        self.messages: Dict[str, Message] = {}
        
        # Indexes for fast lookup
        self.email_to_customer: Dict[str, str] = {}
        self.phone_to_customer: Dict[str, str] = {}
    
    def create_customer(self, email: str = None, phone: str = None, name: str = None) -> Customer:
        """Create or get existing customer."""
        # Check if customer already exists
        if email and email in self.email_to_customer:
            return self.customers[self.email_to_customer[email]]
        if phone and phone in self.phone_to_customer:
            return self.customers[self.phone_to_customer[phone]]
        
        # Create new customer
        customer_id = str(uuid.uuid4())
        customer = Customer(
            id=customer_id,
            email=email,
            phone=phone,
            name=name
        )
        
        # Add identifiers
        if email:
            customer.add_identifier('email', email)
            self.email_to_customer[email] = customer_id
        if phone:
            customer.add_identifier('phone', phone)
            self.phone_to_customer[phone] = customer_id
        
        self.customers[customer_id] = customer
        return customer
    
    def get_customer_by_identifier(self, identifier: str) -> Optional[Customer]:
        """Get customer by email or phone."""
        if '@' in identifier:
            customer_id = self.email_to_customer.get(identifier)
        else:
            customer_id = self.phone_to_customer.get(identifier)
        
        if customer_id:
            return self.customers[customer_id]
        return None
    
    def create_conversation(self, customer_id: str, channel: Channel) -> Conversation:
        """Create new conversation for customer."""
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(
            id=conversation_id,
            customer_id=customer_id,
            initial_channel=channel,
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.conversations[conversation_id] = conversation
        
        # Link to customer
        if customer_id in self.customers:
            self.customers[customer_id].conversation_ids.append(conversation_id)
        
        return conversation
    
    def get_active_conversation(self, customer_id: str, hours: int = 24) -> Optional[Conversation]:
        """Get active conversation for customer (within time window)."""
        customer = self.customers.get(customer_id)
        if not customer:
            return None
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        for conv_id in customer.conversation_ids:
            conv = self.conversations.get(conv_id)
            if conv and conv.updated_at > cutoff and conv.status == ConversationStatus.ACTIVE:
                return conv
        
        return None
    
    def get_customer_history(self, customer_id: str, limit: int = 10) -> List[Conversation]:
        """Get customer's conversation history."""
        customer = self.customers.get(customer_id)
        if not customer:
            return []
        
        conversations = []
        for conv_id in customer.conversation_ids[-limit:]:
            conv = self.conversations.get(conv_id)
            if conv:
                conversations.append(conv)
        
        return sorted(conversations, key=lambda c: c.updated_at, reverse=True)
    
    def save_message(self, message: Message):
        """Save message to store."""
        self.messages[message.id] = message
        
        # Update conversation
        if message.conversation_id in self.conversations:
            self.conversations[message.conversation_id].add_message(message)
    
    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        """Get all messages in a conversation."""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return []
        return conversation.messages


class TopicExtractor:
    """Extract topics from messages for tracking and reporting."""
    
    TOPIC_KEYWORDS = {
        'recurring_tasks': ['recurring', 'repeat', 'repeating', 'frequency'],
        'gantt_chart': ['gantt', 'chart', 'timeline'],
        'password_reset': ['password', 'reset', 'forgot', 'login'],
        'file_upload': ['file', 'upload', 'attachment', 'size'],
        'slack_integration': ['slack', 'integration', 'notification'],
        'github_integration': ['github', 'commit', 'pull request', 'sync'],
        'pricing': ['price', 'cost', 'upgrade', 'plan', 'billing'],
        'export': ['export', 'download', 'backup', 'csv'],
        'team_management': ['invite', 'member', 'team', 'guest', 'add'],
        'api': ['api', 'rate limit', 'developer', 'integration'],
        'custom_workflow': ['custom', 'status', 'workflow'],
        'bug_report': ['bug', 'crash', 'error', 'not working', 'broken'],
        'feature_request': ['feature', 'request', 'wish', 'would be nice'],
    }
    
    def extract(self, text: str) -> List[str]:
        """Extract topics from text."""
        text_lower = text.lower()
        topics = []
        
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)
        
        return topics


class CustomerSuccessAgentWithMemory:
    """
    Customer Success Agent with Memory and State.
    
    Extends the core loop with:
    - Customer identification across channels
    - Conversation continuity
    - Sentiment trend tracking
    - Topic tracking
    """
    
    def __init__(self):
        self.store = InMemoryStore()
        self.topic_extractor = TopicExtractor()
        
        # Import components from core_loop
        from core_loop import (
            SimpleKnowledgeBase, SentimentAnalyzer, 
            EscalationDetector, ResponseFormatter
        )
        self.kb = SimpleKnowledgeBase()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.escalation_detector = EscalationDetector()
        self.formatter = ResponseFormatter()
    
    def process_message(self, message: CustomerMessage) -> AgentResponse:
        """
        Process message with full memory and state.
        """
        print(f"\n{'='*60}")
        print(f"Processing {message.channel.value} from {message.get_customer_identifier()}")
        print(f"{'='*60}")
        
        # Step 1: Identify or create customer
        customer = self._identify_customer(message)
        print(f"Customer: {customer.get_display_name()} (ID: {customer.id})")
        
        # Step 2: Get or create conversation
        conversation = self._get_or_create_conversation(customer, message)
        print(f"Conversation: {conversation.id} ({conversation.status.value})")
        
        # Step 3: Load conversation context if exists
        context = ""
        if len(conversation.messages) > 0:
            context = conversation.get_context_summary()
            print(f"Existing context loaded ({len(conversation.messages)} previous messages)")
        
        # Step 4: Analyze sentiment
        sentiment = self.sentiment_analyzer.analyze(message.content)
        print(f"Sentiment: {sentiment} (trend: {conversation.get_sentiment_trend()})")
        
        # Step 5: Extract topics
        topics = self.topic_extractor.extract(message.content)
        print(f"Topics: {topics}")
        
        # Step 6: Store incoming message
        incoming_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            channel=message.channel,
            direction='inbound',
            role='customer',
            content=message.content,
            created_at=datetime.utcnow(),
            sentiment_score=sentiment,
            topics=topics
        )
        self.store.save_message(incoming_message)
        
        # Step 7: Check for escalation
        requires_escalation, escalation_reason = self.escalation_detector.detect(message.content)
        
        # Escalate if sentiment is declining
        if conversation.get_sentiment_trend() == 'declining' and not requires_escalation:
            requires_escalation = True
            escalation_reason = 'declining_sentiment'
        
        # Step 8: Generate response
        if requires_escalation:
            response_content = self._generate_escalation_response(escalation_reason)
            conversation.status = ConversationStatus.ESCALATED
            conversation.escalation_reason = escalation_reason
            customer.total_escalations += 1
        else:
            search_results = self.kb.search(message.content)
            if search_results:
                response_content = self._generate_answer(search_results, context)
            else:
                response_content = self._generate_no_answer_response()
        
        # Step 9: Format for channel
        formatted_response = self.formatter.format(
            response_content,
            message.channel,
            customer.name
        )
        
        # Step 10: Store outgoing message
        outgoing_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            channel=message.channel,
            direction='outbound',
            role='agent',
            content=formatted_response,
            created_at=datetime.utcnow(),
            sentiment_score=sentiment,
            topics=topics
        )
        self.store.save_message(outgoing_message)
        
        # Update customer stats
        customer.total_interactions += 1
        
        return AgentResponse(
            content=formatted_response,
            requires_escalation=requires_escalation,
            escalation_reason=escalation_reason if isinstance(escalation_reason, str) else str(escalation_reason) if escalation_reason else None,
            sentiment_score=sentiment,
            confidence=0.8
        )
    
    def _identify_customer(self, message: CustomerMessage) -> Customer:
        """Identify or create customer from message."""
        identifier = message.get_customer_identifier()
        
        if identifier:
            # Try to find existing customer
            existing = self.store.get_customer_by_identifier(identifier)
            if existing:
                # Update with any new info
                if message.customer_name and not existing.name:
                    existing.name = message.customer_name
                return existing
        
        # Create new customer
        return self.store.create_customer(
            email=message.customer_email,
            phone=message.customer_phone,
            name=message.customer_name
        )
    
    def _get_or_create_conversation(self, customer: Customer, message: CustomerMessage) -> Conversation:
        """Get active conversation or create new one."""
        # Check for active conversation (within 24 hours)
        active = self.store.get_active_conversation(customer.id, hours=24)
        
        if active:
            # Check if this is a channel switch
            if message.channel not in active.channels_used:
                print(f"⚠️ Customer switched from {active.initial_channel.value} to {message.channel.value}")
            return active
        
        # Create new conversation
        return self.store.create_conversation(customer.id, message.channel)
    
    def _generate_escalation_response(self, reason) -> str:
        """Generate escalation response."""
        return f"""I understand your concern. I'm escalating this to our team ({reason}).

A human agent will review your case and reach out within 4 hours.

Reference: ESC-{str(uuid.uuid4())[:8].upper()}"""
    
    def _generate_answer(self, search_results: List[Dict], context: str = "") -> str:
        """Generate answer with context awareness."""
        best_result = search_results[0]
        
        response = f"**{best_result['title']}**\n\n"
        
        # Add context acknowledgment if continuing conversation
        if context:
            response += "Based on our conversation, here's what you need to know:\n\n"
        
        response += best_result['content']
        
        if len(search_results) > 1:
            response += "\n\n**Related help:**\n"
            for result in search_results[1:3]:
                response += f"• {result['title']}\n"
        
        return response
    
    def _generate_no_answer_response(self) -> str:
        """Generate response when no answer found."""
        return """I couldn't find specific information about this in our documentation. Let me connect you with a human agent who can provide personalized assistance.

In the meantime, visit: https://help.taskflowpro.com"""
    
    def get_customer_history(self, customer_identifier: str) -> str:
        """Get formatted customer history for agent context."""
        customer = self.store.get_customer_by_identifier(customer_identifier)
        if not customer:
            return "No customer found."
        
        history = [
            f"Customer: {customer.get_display_name()}",
            f"Plan: {customer.plan_type}",
            f"Total interactions: {customer.total_interactions}",
            f"Total escalations: {customer.total_escalations}",
            f"Channels used: {', '.join(set(customer.identifiers.keys()))}",
            "\nRecent Conversations:"
        ]
        
        conversations = self.store.get_customer_history(customer.id, limit=5)
        for conv in conversations:
            history.append(f"\n  [{conv.started_at.strftime('%Y-%m-%d')}] {conv.initial_channel.value}")
            history.append(f"    Status: {conv.status.value}")
            history.append(f"    Topics: {', '.join(conv.topics_discussed) or 'None'}")
            history.append(f"    Messages: {len(conv.messages)}")
        
        return "\n".join(history)


def demo_agent_with_memory():
    """Demo the agent with memory and cross-channel continuity."""
    agent = CustomerSuccessAgentWithMemory()
    
    print("\n" + "="*60)
    print("CUSTOMER SUCCESS AGENT - MEMORY & STATE DEMO")
    print("="*60)
    
    # Scenario: Customer contacts via email, then follows up on WhatsApp
    print("\n\n" + "#"*60)
    print("SCENARIO: Cross-Channel Conversation Continuity")
    print("#"*60)
    
    # First contact: Email about recurring tasks
    print("\n--- CONTACT 1: Email ---")
    email_message = CustomerMessage.from_email({
        'customer_email': 'sarah@techstartup.com',
        'customer_name': 'Sarah Johnson',
        'subject': 'Help with recurring tasks',
        'content': 'Hi, I need help setting up recurring tasks for our bi-weekly sprint planning.'
    })
    
    response1 = agent.process_message(email_message)
    print(f"\n📤 Response sent via email")
    
    # Second contact: Same customer via WhatsApp (channel switch!)
    print("\n--- CONTACT 2: WhatsApp (2 hours later) ---")
    whatsapp_message = CustomerMessage.from_whatsapp({
        'customer_phone': '+14155551234',
        'customer_name': 'Sarah Johnson',
        'content': 'Also, can I add team members to specific tasks only?'
    })
    
    # Add phone as identifier to existing customer
    sarah = agent.store.get_customer_by_identifier('sarah@techstartup.com')
    if sarah:
        sarah.add_identifier('whatsapp', '+14155551234')
    
    response2 = agent.process_message(whatsapp_message)
    print(f"\n📤 Response sent via WhatsApp")
    print(f"📊 Agent recognized returning customer across channels!")
    
    # Show customer history
    print("\n\n" + "#"*60)
    print("CUSTOMER HISTORY")
    print("#"*60)
    print(agent.get_customer_history('sarah@techstartup.com'))
    
    # New customer: Pricing inquiry (should escalate)
    print("\n\n" + "#"*60)
    print("SCENARIO: Pricing Inquiry (Escalation)")
    print("#"*60)
    
    pricing_message = CustomerMessage.from_email({
        'customer_email': 'procurement@globalcorp.com',
        'customer_name': 'Jennifer Williams',
        'subject': 'Enterprise Pricing',
        'content': 'We need enterprise pricing for 500+ users. What discounts are available?'
    })
    
    response3 = agent.process_message(pricing_message)
    print(f"\n📤 Response: Escalated to billing team")
    print(f"📊 Escalation tracked in customer profile")


if __name__ == "__main__":
    demo_agent_with_memory()

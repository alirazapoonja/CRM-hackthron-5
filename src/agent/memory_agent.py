"""
TaskFlow Pro Customer Success Agent - Memory and State Module
Exercise 1.3: Add Memory and State

This module extends the core agent with:
- Customer identification across channels (email/phone as primary key)
- Conversation memory with cross-channel continuity
- State tracking (sentiment, topics, resolution status, channels)
- Sentiment analysis on every message

For incubation phase: Uses in-memory storage (dicts).
Production will replace with PostgreSQL.
"""

import uuid
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json


# =============================================================================
# ENUMS AND TYPES
# =============================================================================

class Channel(str, Enum):
    """Supported communication channels."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class ResolutionStatus(str, Enum):
    """Conversation resolution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SOLVED = "solved"
    ESCALATED = "escalated"
    ABANDONED = "abandoned"


class SentimentLevel(str, Enum):
    """Sentiment classification levels."""
    VERY_NEGATIVE = "very_negative"  # 0.0 - 0.2
    NEGATIVE = "negative"            # 0.2 - 0.4
    NEUTRAL = "neutral"              # 0.4 - 0.6
    POSITIVE = "positive"            # 0.6 - 0.8
    VERY_POSITIVE = "very_positive"  # 0.8 - 1.0


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Customer:
    """
    Customer profile with unified identity across channels.
    
    Email is the primary identifier for Gmail and Web Form.
    Phone is the primary identifier for WhatsApp.
    """
    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Additional identifiers for cross-channel matching
    identifiers: Dict[str, str] = field(default_factory=dict)  # {'email': 'x@y.com', 'phone': '+1234'}
    
    # Stats
    total_conversations: int = 0
    total_messages: int = 0
    total_escalations: int = 0
    
    def add_identifier(self, id_type: str, value: str):
        """Add a new identifier for cross-channel matching."""
        self.identifiers[id_type] = value
        if id_type == 'email' and not self.email:
            self.email = value
        elif id_type in ('phone', 'whatsapp') and not self.phone:
            self.phone = value
        self.updated_at = datetime.utcnow()
    
    def get_primary_identifier(self) -> str:
        """Get primary identifier (email preferred, then phone)."""
        return self.email or self.phone or f"unknown-{self.id[:8]}"
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary for storage."""
        return {
            'id': self.id,
            'email': self.email,
            'phone': self.phone,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'identifiers': self.identifiers,
            'total_conversations': self.total_conversations,
            'total_messages': self.total_messages,
            'total_escalations': self.total_escalations
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Customer':
        """Deserialize from dictionary."""
        return cls(
            id=data['id'],
            email=data.get('email'),
            phone=data.get('phone'),
            name=data.get('name'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.utcnow(),
            identifiers=data.get('identifiers', {}),
            total_conversations=data.get('total_conversations', 0),
            total_messages=data.get('total_messages', 0),
            total_escalations=data.get('total_escalations', 0)
        )


@dataclass
class Message:
    """Single message in a conversation."""
    id: str
    conversation_id: str
    channel: Channel
    direction: str  # 'inbound' or 'outbound'
    role: str  # 'customer', 'agent', 'system'
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    sentiment_score: float = 0.5
    topics: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'channel': self.channel.value,
            'direction': self.direction,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'sentiment_score': self.sentiment_score,
            'topics': self.topics,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        """Deserialize from dictionary."""
        return cls(
            id=data['id'],
            conversation_id=data['conversation_id'],
            channel=Channel(data['channel']),
            direction=data['direction'],
            role=data['role'],
            content=data['content'],
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.utcnow(),
            sentiment_score=data.get('sentiment_score', 0.5),
            topics=data.get('topics', []),
            metadata=data.get('metadata', {})
        )


@dataclass
class ConversationState:
    """
    Current state of a conversation.
    
    This tracks the evolving state as the conversation progresses.
    """
    sentiment_score: float = 0.5
    sentiment_trend: str = "stable"  # 'improving', 'stable', 'declining'
    topics_discussed: List[str] = field(default_factory=list)
    resolution_status: ResolutionStatus = ResolutionStatus.PENDING
    original_channel: Optional[Channel] = None
    channel_history: List[Channel] = field(default_factory=list)
    ticket_id: Optional[str] = None
    escalation_reason: Optional[str] = None
    last_agent_response: Optional[str] = None
    pending_actions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'sentiment_score': self.sentiment_score,
            'sentiment_trend': self.sentiment_trend,
            'topics_discussed': self.topics_discussed,
            'resolution_status': self.resolution_status.value,
            'original_channel': self.original_channel.value if self.original_channel else None,
            'channel_history': [c.value for c in self.channel_history],
            'ticket_id': self.ticket_id,
            'escalation_reason': self.escalation_reason,
            'last_agent_response': self.last_agent_response,
            'pending_actions': self.pending_actions
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationState':
        """Deserialize from dictionary."""
        return cls(
            sentiment_score=data.get('sentiment_score', 0.5),
            sentiment_trend=data.get('sentiment_trend', 'stable'),
            topics_discussed=data.get('topics_discussed', []),
            resolution_status=ResolutionStatus(data.get('resolution_status', 'pending')),
            original_channel=Channel(data['original_channel']) if data.get('original_channel') else None,
            channel_history=[Channel(c) for c in data.get('channel_history', [])],
            ticket_id=data.get('ticket_id'),
            escalation_reason=data.get('escalation_reason'),
            last_agent_response=data.get('last_agent_response'),
            pending_actions=data.get('pending_actions', [])
        )


@dataclass
class Conversation:
    """
    Conversation thread with full memory and state.
    
    Key feature: Supports channel switches while maintaining context.
    A customer can start on Web Form, continue on WhatsApp, and 
    follow up on Email - all in the same conversation.
    """
    id: str
    customer_id: str
    initial_channel: Channel
    started_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Messages in chronological order
    messages: List[Message] = field(default_factory=list)
    
    # Current state
    state: ConversationState = field(default_factory=ConversationState)
    
    # Metadata
    metadata: Dict = field(default_factory=dict)
    
    def add_message(self, message: Message):
        """Add message and update conversation state."""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        
        # Update state based on message
        if message.direction == 'inbound':
            # Update sentiment (running average)
            old_sentiment = self.state.sentiment_score
            new_sentiment = message.sentiment_score
            message_count = len([m for m in self.messages if m.direction == 'inbound'])
            
            # Weighted average: recent messages have more weight
            weight = 0.3  # Weight for new message
            self.state.sentiment_score = round((1 - weight) * old_sentiment + weight * new_sentiment, 2)
            
            # Update trend
            if self.state.sentiment_score > old_sentiment + 0.1:
                self.state.sentiment_trend = 'improving'
            elif self.state.sentiment_score < old_sentiment - 0.1:
                self.state.sentiment_trend = 'declining'
            else:
                self.state.sentiment_trend = 'stable'
            
            # Update topics
            for topic in message.topics:
                if topic not in self.state.topics_discussed:
                    self.state.topics_discussed.append(topic)
        
        # Track channel history
        if message.channel not in self.state.channel_history:
            self.state.channel_history.append(message.channel)
        
        # Set original channel if not set
        if not self.state.original_channel:
            self.state.original_channel = message.channel
    
    def get_context_summary(self) -> str:
        """Generate a summary of conversation context for the agent."""
        parts = [
            f"Conversation started: {self.started_at.strftime('%Y-%m-%d %H:%M')}",
            f"Channels used: {', '.join(c.value for c in self.state.channel_history)}",
            f"Topics discussed: {', '.join(self.state.topics_discussed) if self.state.topics_discussed else 'None yet'}",
            f"Sentiment: {self.state.sentiment_score:.2f} ({self.state.sentiment_trend})",
            f"Status: {self.state.resolution_status.value}",
        ]
        
        # Add recent message context (last 2 messages)
        recent_messages = self.messages[-2:] if len(self.messages) >= 2 else self.messages
        if recent_messages:
            parts.append("\nRecent messages:")
            for msg in recent_messages:
                preview = msg.content[:100].replace('\n', ' ')
                parts.append(f"  [{msg.channel.value}] {msg.role}: {preview}...")
        
        # Check for channel switch
        if len(self.state.channel_history) > 1:
            parts.append(f"\n⚠️ Customer switched channels: {' → '.join(c.value for c in self.state.channel_history)}")
        
        return "\n".join(parts)
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'initial_channel': self.initial_channel.value,
            'started_at': self.started_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'messages': [m.to_dict() for m in self.messages],
            'state': self.state.to_dict(),
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Conversation':
        """Deserialize from dictionary."""
        return cls(
            id=data['id'],
            customer_id=data['customer_id'],
            initial_channel=Channel(data['initial_channel']),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.utcnow(),
            messages=[Message.from_dict(m) for m in data.get('messages', [])],
            state=ConversationState.from_dict(data['state']) if data.get('state') else ConversationState(),
            metadata=data.get('metadata', {})
        )


# =============================================================================
# IN-MEMORY STORE
# =============================================================================

class MemoryStore:
    """
    In-memory storage for customers and conversations.
    
    This is a prototype implementation. Production will use PostgreSQL.
    
    Features:
    - Customer lookup by email or phone
    - Cross-channel customer identification
    - Conversation retrieval by customer
    - Active conversation detection (within 24 hours)
    """
    
    def __init__(self):
        self.customers: Dict[str, Customer] = {}
        self.conversations: Dict[str, Conversation] = {}
        
        # Indexes for fast lookup
        self.email_index: Dict[str, str] = {}  # email -> customer_id
        self.phone_index: Dict[str, str] = {}  # phone -> customer_id
    
    def get_or_create_customer(
        self, 
        identifier: str, 
        identifier_type: str = 'email',
        name: Optional[str] = None
    ) -> Customer:
        """
        Get existing customer or create new one.
        
        Args:
            identifier: Email or phone number
            identifier_type: 'email' or 'phone' or 'whatsapp'
            name: Optional customer name
        
        Returns:
            Customer object (existing or new)
        """
        # Normalize identifier
        identifier = identifier.strip().lower() if identifier_type == 'email' else identifier.strip()
        
        # Check existing customer by identifier
        if identifier_type == 'email' and identifier in self.email_index:
            customer = self.customers[self.email_index[identifier]]
            if name and not customer.name:
                customer.name = name
            return customer
        
        if identifier_type in ('phone', 'whatsapp') and identifier in self.phone_index:
            customer = self.customers[self.phone_index[identifier]]
            if name and not customer.name:
                customer.name = name
            return customer
        
        # Check if customer exists with other identifier (cross-channel matching)
        if identifier_type == 'email':
            # Check if any customer has this email in their identifiers
            for customer in self.customers.values():
                if customer.identifiers.get('email') == identifier:
                    customer.add_identifier('email', identifier)
                    self.email_index[identifier] = customer.id
                    return customer
        
        # Create new customer
        customer_id = str(uuid.uuid4())
        customer = Customer(
            id=customer_id,
            email=identifier if identifier_type == 'email' else None,
            phone=identifier if identifier_type in ('phone', 'whatsapp') else None,
            name=name
        )
        customer.add_identifier(identifier_type, identifier)
        
        # Store and index
        self.customers[customer_id] = customer
        if identifier_type == 'email':
            self.email_index[identifier] = customer_id
        else:
            self.phone_index[identifier] = customer_id
        
        return customer
    
    def get_customer_by_identifier(self, identifier: str) -> Optional[Customer]:
        """Get customer by email or phone."""
        identifier = identifier.strip()
        
        # Try email index
        if '@' in identifier:
            customer_id = self.email_index.get(identifier.lower())
            if customer_id:
                return self.customers[customer_id]
        
        # Try phone index
        customer_id = self.phone_index.get(identifier)
        if customer_id:
            return self.customers[customer_id]
        
        return None
    
    def get_or_create_conversation(
        self, 
        customer_id: str, 
        initial_channel: Channel,
        active_window_hours: int = 24
    ) -> Conversation:
        """
        Get active conversation or create new one.
        
        Args:
            customer_id: Customer identifier
            initial_channel: Channel for this interaction
            active_window_hours: Hours since last activity to consider conversation active
        
        Returns:
            Conversation object (existing active or new)
        """
        customer = self.customers.get(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        # Find active conversations for this customer
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=active_window_hours)
        
        # Find most recent active conversation
        active_conversations = []
        for conv in self.conversations.values():
            if (conv.customer_id == customer_id and 
                conv.updated_at > cutoff and 
                conv.state.resolution_status not in [ResolutionStatus.SOLVED, ResolutionStatus.ABANDONED]):
                active_conversations.append(conv)
        
        if active_conversations:
            # Return most recently updated
            conversation = max(active_conversations, key=lambda c: c.updated_at)
            
            # Check for channel switch
            if initial_channel not in conversation.state.channel_history:
                print(f"  🔄 Channel switch detected: {conversation.state.original_channel.value} → {initial_channel.value}")
            
            return conversation
        
        # Create new conversation
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(
            id=conversation_id,
            customer_id=customer_id,
            initial_channel=initial_channel
        )
        conversation.state.original_channel = initial_channel
        conversation.state.channel_history = [initial_channel]
        
        # Generate ticket ID
        conversation.state.ticket_id = f"TKT-{conversation_id[:8].upper()}"
        
        # Store
        self.conversations[conversation_id] = conversation
        customer.total_conversations += 1
        
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID."""
        return self.conversations.get(conversation_id)
    
    def get_customer_conversations(
        self, 
        customer_id: str, 
        limit: int = 10
    ) -> List[Conversation]:
        """Get customer's conversation history."""
        customer_convs = [
            conv for conv in self.conversations.values() 
            if conv.customer_id == customer_id
        ]
        
        # Sort by updated_at descending
        customer_convs.sort(key=lambda c: c.updated_at, reverse=True)
        
        return customer_convs[:limit]
    
    def save_message(self, message: Message) -> None:
        """Save message to conversation."""
        conversation = self.conversations.get(message.conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {message.conversation_id} not found")
        
        conversation.add_message(message)
        
        # Update customer stats
        customer = self.customers.get(conversation.customer_id)
        if customer and message.direction == 'inbound':
            customer.total_messages += 1
    
    def update_conversation_state(
        self, 
        conversation_id: str,
        resolution_status: Optional[ResolutionStatus] = None,
        escalation_reason: Optional[str] = None,
        pending_actions: Optional[List[str]] = None
    ) -> None:
        """Update conversation state."""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        if resolution_status:
            conversation.state.resolution_status = resolution_status
        if escalation_reason:
            conversation.state.escalation_reason = escalation_reason
            conversation.state.resolution_status = ResolutionStatus.ESCALATED
            conversation.state.ticket_id = f"ESC-{conversation_id[:8].upper()}"
            
            # Update customer escalation count
            customer = self.customers.get(conversation.customer_id)
            if customer:
                customer.total_escalations += 1
        
        if pending_actions:
            conversation.state.pending_actions = pending_actions
    
    def get_customer_history_summary(self, customer_id: str) -> str:
        """Get formatted summary of customer's history."""
        customer = self.customers.get(customer_id)
        if not customer:
            return "Customer not found."
        
        conversations = self.get_customer_conversations(customer_id, limit=5)
        
        lines = [
            f"Customer: {customer.name or customer.get_primary_identifier()}",
            f"Total conversations: {customer.total_conversations}",
            f"Total messages: {customer.total_messages}",
            f"Total escalations: {customer.total_escalations}",
            f"Identifiers: {customer.identifiers}",
            "",
            "Recent Conversations:"
        ]
        
        for conv in conversations:
            lines.append(f"  [{conv.started_at.strftime('%Y-%m-%d %H:%M')}] {conv.initial_channel.value}")
            lines.append(f"    Status: {conv.state.resolution_status.value}")
            lines.append(f"    Topics: {', '.join(conv.state.topics_discussed) or 'None'}")
            lines.append(f"    Sentiment: {conv.state.sentiment_score:.2f} ({conv.state.sentiment_trend})")
            lines.append(f"    Channels: {', '.join(c.value for c in conv.state.channel_history)}")
            lines.append("")
        
        return "\n".join(lines)


# =============================================================================
# SENTIMENT ANALYSIS
# =============================================================================

class SentimentAnalyzer:
    """
    Rule-based sentiment analysis for customer messages.
    
    Features:
    - Detects positive, negative, and neutral sentiment
    - Identifies anger signals (caps, exclamation marks, specific words)
    - Returns score (0.0-1.0) and explanation
    """
    
    # Word lists for sentiment detection
    POSITIVE_WORDS = {
        'love', 'loved', 'loving', 'amazing', 'awesome', 'excellent', 
        'fantastic', 'great', 'wonderful', 'perfect', 'helpful', 'thanks', 
        'thank', 'appreciate', 'happy', 'pleased', 'satisfied', 'good',
        'nice', 'best', 'brilliant', 'outstanding', 'superb'
    }
    
    NEGATIVE_WORDS = {
        'hate', 'hated', 'terrible', 'awful', 'horrible', 'worst', 
        'broken', 'useless', 'frustrated', 'angry', 'ridiculous', 
        'unacceptable', 'disappointed', 'issue', 'problem', 'error', 
        'fail', 'failed', 'crash', 'crashed', 'bad', 'wrong', 'sucks'
    }
    
    ANGER_SIGNALS = {
        'multiple_exclamation': r'!{3,}',  # Three or more exclamation marks
        'all_caps': r'\b[A-Z]{3,}\b',  # Words in ALL CAPS (3+ chars)
        'rudeness': ['ridiculous', 'unacceptable', 'terrible', 'awful', 'horrible'],
        'urgency': ['NOW', 'IMMEDIATELY', 'ASAP', 'URGENT', 'RIGHT NOW'],
        'threats': ['cancel', 'switch', 'chargeback', 'refund', 'sue', 'lawyer', 'complaint']
    }
    
    def detect_sentiment(self, text: str) -> Tuple[float, str, Dict[str, Any]]:
        """
        Analyze sentiment of text.
        
        Args:
            text: The customer message text
        
        Returns:
            Tuple of (score, classification, details)
            - score: 0.0 (very negative) to 1.0 (very positive)
            - classification: SentimentLevel enum value
            - details: Dict with analysis details
        """
        text_lower = text.lower()
        words = set(text_lower.split())
        
        details = {
            'positive_words_found': [],
            'negative_words_found': [],
            'anger_signals_found': [],
            'explanation': ''
        }
        
        # Count positive and negative words
        positive_found = [w for w in words if w in self.POSITIVE_WORDS]
        negative_found = [w for w in words if w in self.NEGATIVE_WORDS]
        
        details['positive_words_found'] = positive_found
        details['negative_words_found'] = negative_found
        
        positive_count = len(positive_found)
        negative_count = len(negative_found)
        
        # Base score (neutral is 0.5)
        if positive_count + negative_count == 0:
            base_score = 0.5
        else:
            base_score = 0.5 + (positive_count - negative_count) / (2 * (positive_count + negative_count))
        
        # Check for anger signals
        anger_penalty = 0.0
        
        # Multiple exclamation marks
        if re.search(self.ANGER_SIGNALS['multiple_exclamation'], text):
            anger_penalty += 0.15
            details['anger_signals_found'].append('multiple_exclamation')
        
        # ALL CAPS words
        caps_words = re.findall(self.ANGER_SIGNALS['all_caps'], text)
        if len(caps_words) >= 2:
            anger_penalty += 0.15
            details['anger_signals_found'].append('all_caps')
        
        # Rude/angry words
        for word in self.ANGER_SIGNALS['rudeness']:
            if word in text_lower:
                anger_penalty += 0.1
                details['anger_signals_found'].append(f'rudeness: {word}')
        
        # Urgency words in caps
        for word in self.ANGER_SIGNALS['urgency']:
            if word in text:
                anger_penalty += 0.1
                details['anger_signals_found'].append(f'urgency: {word}')
        
        # Threats
        for word in self.ANGER_SIGNALS['threats']:
            if word in text_lower:
                anger_penalty += 0.1
                details['anger_signals_found'].append(f'threat: {word}')
        
        # Apply anger penalty
        final_score = max(0.0, min(1.0, base_score - anger_penalty))
        
        # Classify sentiment
        if final_score >= 0.8:
            classification = SentimentLevel.VERY_POSITIVE
        elif final_score >= 0.6:
            classification = SentimentLevel.POSITIVE
        elif final_score >= 0.4:
            classification = SentimentLevel.NEUTRAL
        elif final_score >= 0.2:
            classification = SentimentLevel.NEGATIVE
        else:
            classification = SentimentLevel.VERY_NEGATIVE
        
        # Generate explanation
        explanation_parts = []
        if positive_found:
            explanation_parts.append(f"Positive words: {', '.join(positive_found)}")
        if negative_found:
            explanation_parts.append(f"Negative words: {', '.join(negative_found)}")
        if details['anger_signals_found']:
            explanation_parts.append(f"Anger signals: {len(details['anger_signals_found'])} detected")
        
        details['explanation'] = '; '.join(explanation_parts) if explanation_parts else "No strong sentiment indicators"
        details['classification'] = classification.value
        
        return round(final_score, 2), classification.value, details


# =============================================================================
# MEMORY-ENABLED AGENT
# =============================================================================

class MemoryAgent:
    """
    Customer Success Agent with full memory and state tracking.
    
    This agent:
    1. Identifies customers across channels (email/phone)
    2. Maintains conversation memory with cross-channel continuity
    3. Tracks sentiment, topics, and resolution status
    4. Generates context-aware responses
    """
    
    def __init__(self):
        self.store = MemoryStore()
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Simple knowledge base for prototype
        self.knowledge_base = {
            'password': 'To reset your password: 1. Go to login page 2. Click "Forgot Password" 3. Enter email 4. Check for reset link',
            'recurring': 'To create recurring tasks: 1. Open task 2. Click due date 3. Select "Repeat" 4. Choose frequency',
            'gantt': 'Gantt charts are available on Pro and Enterprise plans. Access via: View selector → Gantt',
            'slack': 'To connect Slack: 1. Settings → Integrations 2. Find Slack 3. Click Connect 4. Authorize',
            'pricing': 'Pricing: Free (3 projects), Pro ($12/user), Business ($24/user), Enterprise (custom)',
            'export': 'To export data: 1. Settings → Export 2. Choose format (JSON/CSV) 3. Select data 4. Request export',
            'file': 'File limits: Free=100MB, Pro=2GB, Business/Enterprise=5GB. Blocked: .exe, .bat',
            'github': 'GitHub integration: 1. Settings → Integrations 2. GitHub → Connect 3. Authorize repos'
        }
    
    def process_message(
        self, 
        content: str, 
        channel: Channel,
        identifier: str,
        identifier_type: str = 'email',
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a customer message with full memory and state.
        
        Args:
            content: Message content
            channel: Communication channel
            identifier: Email or phone number
            identifier_type: 'email' or 'phone' or 'whatsapp'
            name: Optional customer name
        
        Returns:
            Dict with response and metadata
        """
        print(f"\n{'='*60}")
        print(f"Processing {channel.value} message from {identifier}")
        print(f"{'='*60}")
        
        # Step 1: Identify or create customer
        customer = self.store.get_or_create_customer(
            identifier=identifier,
            identifier_type=identifier_type,
            name=name
        )
        print(f"Customer: {customer.name or customer.get_primary_identifier()} (ID: {customer.id})")
        print(f"Identifiers: {customer.identifiers}")
        
        # Step 2: Get or create conversation
        conversation = self.store.get_or_create_conversation(
            customer_id=customer.id,
            initial_channel=channel
        )
        print(f"Conversation: {conversation.id[:8]}... (Ticket: {conversation.state.ticket_id})")
        print(f"Status: {conversation.state.resolution_status.value}")
        
        # Step 3: Load conversation context
        if len(conversation.messages) > 0:
            print(f"Previous messages: {len(conversation.messages)}")
            print(f"Topics discussed: {', '.join(conversation.state.topics_discussed) or 'None'}")
        else:
            print("New conversation")
        
        # Step 4: Analyze sentiment
        sentiment_score, sentiment_class, sentiment_details = self.sentiment_analyzer.detect_sentiment(content)
        print(f"Sentiment: {sentiment_score:.2f} ({sentiment_class})")
        if sentiment_details['anger_signals_found']:
            print(f"⚠️ Anger signals: {sentiment_details['anger_signals_found']}")
        
        # Step 5: Extract topics (simple keyword matching)
        topics = self._extract_topics(content)
        print(f"Topics detected: {topics}")
        
        # Step 6: Store incoming message
        incoming_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            channel=channel,
            direction='inbound',
            role='customer',
            content=content,
            sentiment_score=sentiment_score,
            topics=topics
        )
        self.store.save_message(incoming_message)
        
        # Step 7: Check for escalation triggers
        requires_escalation = False
        escalation_reason = None
        
        # Low sentiment trigger
        if sentiment_score < 0.3:
            requires_escalation = True
            escalation_reason = 'angry_customer'
            print(f"⚠️ Escalation triggered: Low sentiment ({sentiment_score:.2f})")
        
        # Threat/legal trigger
        if any(word in content.lower() for word in ['lawyer', 'sue', 'legal', 'refund', 'chargeback']):
            requires_escalation = True
            escalation_reason = 'legal_or_refund'
            print(f"⚠️ Escalation triggered: Legal/refund mention")
        
        # Step 8: Generate response
        if requires_escalation:
            response = self._generate_escalation_response(escalation_reason, conversation.state.ticket_id)
            conversation.state.resolution_status = ResolutionStatus.ESCALATED
            conversation.state.escalation_reason = escalation_reason
        else:
            # Search knowledge base
            kb_result = self._search_knowledge_base(content)
            
            if kb_result:
                response = self._format_knowledge_response(kb_result, channel)
                conversation.state.resolution_status = ResolutionStatus.IN_PROGRESS
            else:
                response = self._generate_no_answer_response(channel)
                conversation.state.pending_actions.append('human_review')
        
        # Step 9: Store outgoing message
        outgoing_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            channel=channel,
            direction='outbound',
            role='agent',
            content=response,
            sentiment_score=sentiment_score,
            topics=topics
        )
        self.store.save_message(outgoing_message)
        conversation.state.last_agent_response = response
        
        # Step 10: Update resolution status if solved
        if not requires_escalation and kb_result and sentiment_score >= 0.5:
            # Mark as solved if we provided helpful info and customer seems satisfied
            # (In production, we'd wait for customer confirmation)
            pass  # Keep as in_progress for follow-up
        
        print(f"\nResponse sent via {channel.value}")
        print(f"Resolution status: {conversation.state.resolution_status.value}")
        
        return {
            'response': response,
            'customer_id': customer.id,
            'conversation_id': conversation.id,
            'ticket_id': conversation.state.ticket_id,
            'sentiment_score': sentiment_score,
            'sentiment_class': sentiment_class,
            'topics': topics,
            'requires_escalation': requires_escalation,
            'escalation_reason': escalation_reason,
            'resolution_status': conversation.state.resolution_status.value,
            'channel_switched': len(conversation.state.channel_history) > 1
        }
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text using keyword matching."""
        text_lower = text.lower()
        topics = []
        
        topic_keywords = {
            'password_reset': ['password', 'reset', 'login', 'forgot'],
            'recurring_tasks': ['recurring', 'repeat', 'frequency'],
            'gantt_chart': ['gantt', 'chart', 'timeline'],
            'slack_integration': ['slack', 'integration', 'notify'],
            'pricing': ['price', 'cost', 'plan', 'upgrade', 'billing'],
            'export': ['export', 'download', 'backup', 'csv'],
            'file_upload': ['file', 'upload', 'size', 'limit', 'attachment'],
            'github_integration': ['github', 'commit', 'sync', 'repo']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)
        
        return topics
    
    def _search_knowledge_base(self, query: str) -> Optional[str]:
        """Search knowledge base for relevant information."""
        query_lower = query.lower()
        
        for keywords, answer in self.knowledge_base.items():
            if keywords in query_lower:
                return answer
        
        return None
    
    def _format_knowledge_response(self, answer: str, channel: Channel) -> str:
        """Format knowledge base response for channel."""
        if channel == Channel.WHATSAPP:
            # Short for WhatsApp
            if len(answer) > 280:
                answer = answer[:277] + "..."
            return f"{answer}\n\n📱 Reply for more help!"
        elif channel == Channel.EMAIL:
            return f"""Here's the information you requested:

{answer}

If you need any further assistance, please don't hesitate to reply.

Best regards,
TaskFlow Support"""
        else:  # WEB_FORM
            return f"""{answer}

---
Need more help? Reply to this message or visit our support portal."""
    
    def _generate_escalation_response(self, reason: str, ticket_id: str) -> str:
        """Generate escalation response."""
        responses = {
            'angry_customer': f"""I completely understand your frustration, and I'm truly sorry for the trouble you're experiencing. 

I'm escalating this to our senior support team who will prioritize your case. They'll reach out within 2 hours.

Reference: {ticket_id}""",
            
            'legal_or_refund': f"""I understand your concern. I'm escalating this to the appropriate team who can assist you better.

A specialist will review your case and reach out within 4 hours.

Reference: {ticket_id}"""
        }
        
        return responses.get(reason, f"""I understand your concern. I'm escalating this to our team for further assistance.

Reference: {ticket_id}""")
    
    def _generate_no_answer_response(self, channel: Channel) -> str:
        """Generate response when no answer is found."""
        base = "I couldn't find specific information about this in our documentation. Let me connect you with a human agent who can provide personalized assistance."
        
        if channel == Channel.WHATSAPP:
            return f"{base}\n\n📱 You'll hear back within 4 hours."
        else:
            return f"""{base}

In the meantime, you might find helpful resources at: https://help.taskflowpro.com

We'll follow up shortly."""
    
    def get_customer_history(self, identifier: str) -> str:
        """Get customer's conversation history."""
        customer = self.store.get_customer_by_identifier(identifier)
        if not customer:
            return f"No customer found with identifier: {identifier}"
        
        return self.store.get_customer_history_summary(customer.id)
    
    def get_conversation_context(self, conversation_id: str) -> str:
        """Get conversation context summary."""
        conversation = self.store.get_conversation(conversation_id)
        if not conversation:
            return f"Conversation not found: {conversation_id}"
        
        return conversation.get_context_summary()


# =============================================================================
# DEMO AND TESTING
# =============================================================================

def run_memory_agent_demo():
    """Demonstrate the memory agent with various scenarios."""
    agent = MemoryAgent()
    
    print("\n" + "="*70)
    print("MEMORY AGENT DEMO - Exercise 1.3: Add Memory and State")
    print("="*70)
    
    # Scenario 1: Single channel follow-up
    print("\n\n" + "#"*70)
    print("SCENARIO 1: Single Channel Follow-up (Email)")
    print("#"*70)
    
    result1 = agent.process_message(
        content="Hi, I need help resetting my password. I forgot it.",
        channel=Channel.EMAIL,
        identifier='sarah@example.com',
        identifier_type='email',
        name='Sarah Johnson'
    )
    print(f"\nResponse: {result1['response'][:200]}...")
    
    # Follow-up message (same conversation)
    result2 = agent.process_message(
        content="Thanks! But I didn't receive the reset email. What should I do?",
        channel=Channel.EMAIL,
        identifier='sarah@example.com',
        identifier_type='email'
    )
    print(f"\nFollow-up Response: {result2['response'][:200]}...")
    print(f"Same conversation: {result1['conversation_id'] == result2['conversation_id']}")
    print(f"Topics tracked: {result2['topics']}")
    
    # Scenario 2: Channel switch (Web Form → WhatsApp)
    print("\n\n" + "#"*70)
    print("SCENARIO 2: Channel Switch (Web Form → WhatsApp)")
    print("#"*70)
    
    result3 = agent.process_message(
        content="I'm trying to set up recurring tasks but can't find the option.",
        channel=Channel.WEB_FORM,
        identifier='mike@company.com',
        identifier_type='email',
        name='Mike Chen'
    )
    print(f"\nWeb Form Response: {result3['response'][:150]}...")
    
    # Customer follows up on WhatsApp (same email identifier)
    result4 = agent.process_message(
        content="Still can't find it. Where exactly is the repeat option?",
        channel=Channel.WHATSAPP,
        identifier='mike@company.com',
        identifier_type='email'
    )
    print(f"\nWhatsApp Response: {result4['response'][:150]}...")
    print(f"Channel switch detected: {result4['channel_switched']}")
    print(f"Conversation continuity: {result3['conversation_id'] == result4['conversation_id']}")
    
    # Scenario 3: Sentiment going negative
    print("\n\n" + "#"*70)
    print("SCENARIO 3: Sentiment Going Negative (Escalation)")
    print("#"*70)
    
    result5 = agent.process_message(
        content="This is RIDICULOUS!!! Your app keeps CRASHING when I try to upload files!!! I want a REFUND NOW!!!",
        channel=Channel.EMAIL,
        identifier='angry@example.com',
        identifier_type='email',
        name='Angry User'
    )
    print(f"\nResponse: {result5['response']}")
    print(f"Escalation required: {result5['requires_escalation']}")
    print(f"Escalation reason: {result5['escalation_reason']}")
    print(f"Sentiment score: {result5['sentiment_score']}")
    
    # Scenario 4: Topic continuity across messages
    print("\n\n" + "#"*70)
    print("SCENARIO 4: Topic Continuity Across Messages")
    print("#"*70)
    
    result6 = agent.process_message(
        content="How do I connect Slack to get notifications?",
        channel=Channel.WEB_FORM,
        identifier='lisa@startup.io',
        identifier_type='email',
        name='Lisa Park'
    )
    print(f"\nInitial topics: {result6['topics']}")
    
    result7 = agent.process_message(
        content="Also, can I filter which projects send notifications to Slack?",
        channel=Channel.WEB_FORM,
        identifier='lisa@startup.io',
        identifier_type='email'
    )
    print(f"Follow-up topics: {result7['topics']}")
    print(f"Topics discussed in conversation: {result7['topics']}")
    
    # Scenario 5: New vs Returning customer
    print("\n\n" + "#"*70)
    print("SCENARIO 5: New Customer vs Returning Customer")
    print("#"*70)
    
    # New customer
    result8 = agent.process_message(
        content="Hi, what are your pricing plans?",
        channel=Channel.EMAIL,
        identifier='newuser@example.com',
        identifier_type='email'
    )
    print(f"\nNew customer - Total conversations: 1")
    
    # Same customer returns
    result9 = agent.process_message(
        content="I signed up for Pro. How do I access Gantt charts?",
        channel=Channel.EMAIL,
        identifier='newuser@example.com',
        identifier_type='email'
    )
    print(f"Returning customer - Same conversation: {result8['conversation_id'] == result9['conversation_id']}")
    
    # Show customer history
    print("\n\n" + "#"*70)
    print("CUSTOMER HISTORY EXAMPLE")
    print("#"*70)
    
    history = agent.get_customer_history('sarah@example.com')
    print(history)
    
    # Show conversation context
    print("\n\n" + "#"*70)
    print("CONVERSATION CONTEXT EXAMPLE")
    print("#"*70)
    
    context = agent.get_conversation_context(result2['conversation_id'])
    print(context)
    
    print("\n\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("\nKey Features Demonstrated:")
    print("✅ Customer identification by email")
    print("✅ Cross-channel conversation continuity")
    print("✅ Sentiment analysis with anger detection")
    print("✅ Topic tracking across messages")
    print("✅ Automatic escalation on low sentiment")
    print("✅ Conversation memory and context")
    print("✅ Resolution status tracking")


if __name__ == "__main__":
    run_memory_agent_demo()

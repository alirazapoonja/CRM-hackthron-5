# Exercise 1.3: Add Memory and State - Implementation Summary

**Date:** March 2025  
**Status:** ✅ COMPLETE

---

## Files Created

| File | Lines | Description |
|------|-------|-------------|
| `src/agent/memory_agent.py` | ~850 | Complete memory and state tracking system |

---

## Implementation Overview

### Data Classes

#### 1. Customer
```python
@dataclass
class Customer:
    id: str                    # UUID
    email: Optional[str]       # Primary identifier (Gmail, Web Form)
    phone: Optional[str]       # Primary identifier (WhatsApp)
    name: Optional[str]
    identifiers: Dict[str, str]  # Cross-channel mapping
    total_conversations: int
    total_messages: int
    total_escalations: int
```

**Key Features:**
- Email as primary identifier for Gmail and Web Form
- Phone as primary identifier for WhatsApp
- `identifiers` dict for cross-channel matching
- Automatic stats tracking

#### 2. Message
```python
@dataclass
class Message:
    id: str
    conversation_id: str
    channel: Channel           # email, whatsapp, web_form
    direction: str             # inbound/outbound
    role: str                  # customer/agent/system
    content: str
    sentiment_score: float     # 0.0-1.0
    topics: List[str]          # Detected topics
```

#### 3. ConversationState
```python
@dataclass
class ConversationState:
    sentiment_score: float          # Running average
    sentiment_trend: str            # improving/stable/declining
    topics_discussed: List[str]     # All topics covered
    resolution_status: ResolutionStatus
    original_channel: Channel       # First channel used
    channel_history: List[Channel]  # All channels used
    ticket_id: str                  # TKT-XXXXXXXX
    escalation_reason: Optional[str]
```

#### 4. Conversation
```python
@dataclass
class Conversation:
    id: str
    customer_id: str
    initial_channel: Channel
    messages: List[Message]      # Full history
    state: ConversationState     # Current state
    started_at: datetime
    updated_at: datetime
```

**Key Feature:** Maintains full message history with state tracking across channel switches.

---

## Core Components

### 1. MemoryStore (In-Memory Database)

```python
class MemoryStore:
    customers: Dict[str, Customer]
    conversations: Dict[str, Conversation]
    email_index: Dict[str, str]    # email → customer_id
    phone_index: Dict[str, str]    # phone → customer_id
```

**Key Methods:**
- `get_or_create_customer(identifier, identifier_type, name)` - Find or create customer
- `get_or_create_conversation(customer_id, initial_channel)` - Get active or create new
- `save_message(message)` - Add message to conversation
- `update_conversation_state(conversation_id, ...)` - Update resolution status
- `get_customer_history_summary(customer_id)` - Formatted history

### 2. SentimentAnalyzer

```python
class SentimentAnalyzer:
    POSITIVE_WORDS = {...}    # 25+ words
    NEGATIVE_WORDS = {...}    # 25+ words
    ANGER_SIGNALS = {
        'multiple_exclamation': r'!{3,}',
        'all_caps': r'\b[A-Z]{3,}\b',
        'rudeness': [...],
        'urgency': [...],
        'threats': [...]
    }
```

**Key Method:**
```python
def detect_sentiment(text: str) -> Tuple[float, str, Dict]:
    # Returns: (score, classification, details)
    # Score: 0.0 (very negative) to 1.0 (very positive)
```

**Sentiment Levels:**
| Score Range | Classification |
|-------------|---------------|
| 0.8 - 1.0 | VERY_POSITIVE |
| 0.6 - 0.8 | POSITIVE |
| 0.4 - 0.6 | NEUTRAL |
| 0.2 - 0.4 | NEGATIVE |
| 0.0 - 0.2 | VERY_NEGATIVE |

**Anger Detection:**
- Multiple exclamation marks (!!!)
- ALL CAPS words (3+ chars)
- Rude words (ridiculous, unacceptable)
- Urgency words (NOW, IMMEDIATELY)
- Threats (cancel, refund, sue, lawyer)

### 3. MemoryAgent

```python
class MemoryAgent:
    store: MemoryStore
    sentiment_analyzer: SentimentAnalyzer
    knowledge_base: Dict[str, str]  # Simple KB for prototype
```

**Processing Flow:**
```
1. Identify/create customer (by email/phone)
2. Get/create conversation (with 24h active window)
3. Load conversation context
4. Analyze sentiment of new message
5. Extract topics
6. Store incoming message
7. Check escalation triggers
8. Generate response (KB search or escalation)
9. Store outgoing message
10. Update resolution status
```

---

## Test Scenarios - All Passing ✅

### Scenario 1: Single Channel Follow-up
**Test:** Customer sends multiple messages via same channel

**Result:**
```
✅ Same conversation ID maintained
✅ Previous messages loaded (2 messages)
✅ Topics tracked: ['password_reset']
✅ Sentiment averaged across messages
```

**Sample Output:**
```
Customer: Sarah Johnson
Conversation: b419946c... (Ticket: TKT-B419946C)
Previous messages: 2
Topics discussed: password_reset
```

---

### Scenario 2: Channel Switch (Web Form → WhatsApp)
**Test:** Customer starts on Web Form, follows up on WhatsApp

**Result:**
```
✅ Customer identified by same email
✅ Channel switch detected: web_form → whatsapp
✅ Same conversation maintained
✅ Conversation continuity preserved
```

**Sample Output:**
```
🔄 Channel switch detected: web_form → whatsapp
Channel switch detected: True
Conversation continuity: True
```

---

### Scenario 3: Sentiment Going Negative (Escalation)
**Test:** Angry customer with multiple anger signals

**Input:**
```
"This is RIDICULOUS!!! Your app keeps CRASHING when I try to upload files!!! 
I want a REFUND NOW!!!"
```

**Result:**
```
✅ Sentiment score: 0.00 (very_negative)
✅ Anger signals detected: 5 signals
   - multiple_exclamation
   - all_caps
   - rudeness: ridiculous
   - urgency: NOW
   - threat: refund
✅ Escalation triggered automatically
✅ Resolution status: escalated
```

---

### Scenario 4: Topic Continuity Across Messages
**Test:** Customer asks follow-up about same topic

**Result:**
```
✅ Topics tracked across messages
✅ Initial topics: ['slack_integration']
✅ Follow-up topics: ['slack_integration']
✅ Topics discussed in conversation: ['slack_integration']
```

---

### Scenario 5: New vs Returning Customer
**Test:** Customer returns with new question

**Result:**
```
✅ New customer: Created with ID
✅ Returning customer: Same ID recognized
✅ Same conversation maintained (within 24h window)
✅ Previous topics visible: ['pricing']
✅ New topic added: ['gantt_chart']
```

---

## Cross-Channel Memory - How It Works

### Customer Identification Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    CUSTOMER IDENTIFICATION                       │
│                                                                  │
│  Incoming Message                                                │
│       │                                                          │
│       ▼                                                          │
│  Extract Identifier (email or phone)                             │
│       │                                                          │
│       ▼                                                          │
│  Check email_index OR phone_index                                │
│       │                                                          │
│   ┌──┴──┐                                                        │
│   │     │                                                        │
│   ▼     ▼                                                        │
│ Found  Not Found                                                  │
│   │     │                                                        │
│   │     ▼                                                        │
│   │  Create New Customer                                         │
│   │  - Generate UUID                                             │
│   │  - Add to index                                              │
│   │                                                              │
│   ▼                                                              │
│ Return Customer                                                  │
│                                                                  │
│  Cross-Channel Matching:                                         │
│  - If customer exists with email, add phone identifier           │
│  - If customer exists with phone, add email identifier           │
│  - All identifiers linked to single customer profile             │
└─────────────────────────────────────────────────────────────────┘
```

### Conversation Continuity Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                   CONVERSATION CONTINUITY                        │
│                                                                  │
│  Customer Identified                                             │
│       │                                                          │
│       ▼                                                          │
│  Find Active Conversations (within 24h)                          │
│       │                                                          │
│   ┌──┴──┐                                                        │
│   │     │                                                        │
│   ▼     ▼                                                        │
│ Found  None Found                                                 │
│   │     │                                                        │
│   │     ▼                                                        │
│   │  Create New Conversation                                     │
│   │  - Generate ticket ID                                        │
│   │  - Set initial_channel                                       │
│   │                                                              │
│   ▼                                                              │
│ Check for Channel Switch                                         │
│   │                                                              │
│   ▼                                                              │
│ If new channel: Log in channel_history                           │
│   │                                                              │
│   ▼                                                              │
│ Return Conversation (with full history)                          │
│                                                                  │
│  Example Channel History:                                        │
│  [web_form] → [whatsapp] → [email]                               │
│  All messages from all channels in single thread                 │
└─────────────────────────────────────────────────────────────────┘
```

### State Tracking

```python
# State is updated on every message:

# 1. Sentiment (weighted average)
new_sentiment = (0.7 * old_sentiment) + (0.3 * current_message_sentiment)

# 2. Trend detection
if new_sentiment > old_sentiment + 0.1:
    trend = 'improving'
elif new_sentiment < old_sentiment - 0.1:
    trend = 'declining'
else:
    trend = 'stable'

# 3. Topics (accumulative)
for topic in message.topics:
    if topic not in state.topics_discussed:
        state.topics_discussed.append(topic)

# 4. Channels (accumulative)
if message.channel not in state.channel_history:
    state.channel_history.append(message.channel)

# 5. Resolution status
if sentiment < 0.3 OR legal/refund mentioned:
    status = 'escalated'
elif kb_answer_provided:
    status = 'in_progress'
else:
    status = 'pending'
```

---

## Edge Cases Discovered

| Edge Case | Handling Strategy |
|-----------|------------------|
| **Customer uses different email** | Create separate customer profile (can be merged manually) |
| **Customer switches phone number** | Create separate profile (WhatsApp ID changes) |
| **Multiple conversations within 24h** | Return most recently active conversation |
| **Conversation older than 24h** | Create new conversation (previous preserved in history) |
| **Sentiment fluctuates wildly** | Use weighted average (70% old, 30% new) |
| **No topics detected** | Empty topics list (no special handling needed) |
| **Customer sends empty message** | Still processed, sentiment neutral (0.5) |
| **Channel switch mid-escalation** | Escalation preserved, new channel added to history |

---

## Serialization/Deserialization

All data classes support JSON serialization for future database migration:

```python
# Serialize
customer_dict = customer.to_dict()
conversation_dict = conversation.to_dict()

# Deserialize
customer = Customer.from_dict(customer_dict)
conversation = Conversation.from_dict(conversation_dict)
```

**Storage Format Example:**
```json
{
  "id": "aeaa5761-2d6b-467e-85f4-3a5acc629b41",
  "email": "sarah@example.com",
  "phone": null,
  "name": "Sarah Johnson",
  "created_at": "2025-03-15T09:23:00",
  "identifiers": {"email": "sarah@example.com"},
  "total_conversations": 1,
  "total_messages": 2,
  "total_escalations": 0
}
```

---

## Performance Characteristics

| Operation | Time Complexity | Notes |
|-----------|-----------------|-------|
| Customer lookup (email) | O(1) | Hash index |
| Customer lookup (phone) | O(1) | Hash index |
| Get active conversation | O(n) | Linear scan of customer's conversations |
| Add message | O(1) | Append to list |
| Get conversation history | O(1) | Direct dict access |
| Sentiment analysis | O(w) | w = number of words in message |

**Scalability Note:** In-memory storage is suitable for prototype. Production will use PostgreSQL with proper indexes.

---

## Key Features Demonstrated

| Feature | Status | Evidence |
|---------|--------|----------|
| ✅ Customer identification by email | Working | Scenario 1, 2, 4, 5 |
| ✅ Cross-channel continuity | Working | Scenario 2 (web_form → whatsapp) |
| ✅ Sentiment analysis | Working | Scenario 3 (0.00 score detected) |
| ✅ Anger signal detection | Working | 5 signals detected in Scenario 3 |
| ✅ Topic tracking | Working | Scenarios 1, 4 |
| ✅ Automatic escalation | Working | Scenario 3 (escalated status) |
| ✅ Conversation memory | Working | All scenarios show context loaded |
| ✅ Resolution status tracking | Working | pending → in_progress → escalated |
| ✅ Channel history | Working | Scenario 2 shows channel switch |
| ✅ Customer history summary | Working | Demo output shows full history |

---

## Migration Path to Production

### Current (In-Memory)
```python
class MemoryStore:
    customers: Dict[str, Customer]
    conversations: Dict[str, Conversation]
```

### Production (PostgreSQL)
```python
class PostgresStore:
    async def get_customer(self, customer_id: UUID) -> Customer
    async def save_customer(self, customer: Customer) -> None
    async def get_conversation(self, conv_id: UUID) -> Conversation
    async def save_conversation(self, conv: Conversation) -> None
```

**Migration Steps:**
1. Replace `MemoryStore` with `PostgresStore`
2. Use existing `to_dict()` / `from_dict()` methods
3. Map dataclass fields to database columns
4. Use existing schema from Exercise 2.1

---

**Exercise 1.3 Sign-off:** ✅ COMPLETE

*All requirements from the hackathon document have been implemented and tested. Cross-channel memory, sentiment tracking, topic tracking, and resolution status are fully functional.*

# Agent Skills Manifest

**Project:** TaskFlow Pro Customer Success FTE  
**Phase:** Incubation - Exercise 1.5  
**Version:** 1.0  
**Date:** March 2025  

---

## Overview

This document defines the core skills that the Customer Success FTE possesses. Each skill is a reusable capability that the agent can invoke based on context and need.

Skills are organized by category and include:
- **Purpose:** When and why to use the skill
- **Inputs:** What information the skill requires
- **Outputs:** What the skill produces
- **Implementation:** How the skill works (prototype → production)
- **Related MCP Tools:** Connection to MCP server tools

---

## Skill Categories

1. **Knowledge & Information** - Retrieving and processing information
2. **Communication** - Interacting with customers
3. **Decision Making** - Making judgments and recommendations
4. **Customer Management** - Understanding and tracking customers

---

## 1. Knowledge Retrieval Skill

### Skill Name
`knowledge_retrieval`

### Description
Search and retrieve relevant information from the product knowledge base when customers ask questions about features, how-to guidance, or technical information.

### When to Use
- Customer asks "How do I...?" questions
- Customer needs feature information
- Customer reports an issue that may have documentation
- Agent needs to verify product capabilities before responding

### Inputs
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| query | string | Yes | The search query (customer's question) | "How do I reset my password?" |
| max_results | int | No | Maximum results to return (default: 5) | 3 |
| category | string | No | Filter by category (technical, billing, how_to) | "how_to" |

### Outputs
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| results | array | List of relevant articles with content | `[{title, content, relevance_score}]` |
| relevance_scores | array | Confidence score for each result (0-1) | `[0.95, 0.75, 0.60]` |
| best_match | object | The most relevant article | `{title: "Password Reset", ...}` |
| no_results_message | string | Friendly message if nothing found | "No relevant documentation found." |

### Implementation Notes

**Prototype (Exercise 1.2 & 1.4):**
- Keyword-based search in `src/agent/core_loop.py`
- Simple relevance scoring (keyword matches + title bonus)
- Returns formatted text with relevance scores

**Production (Target):**
- Vector embeddings with pgvector (PostgreSQL)
- Semantic search capabilities
- Category filtering
- Personalized results based on customer plan

### Related MCP Tools
- `search_knowledge_base(query, max_results)` - Direct implementation

### Example Usage
```
Customer: "How do I set up recurring tasks?"

Skill Call: knowledge_retrieval(
    query="recurring tasks setup repeat frequency",
    max_results=3
)

Result: {
    "results": [
        {
            "title": "Creating Recurring Tasks",
            "content": "To create a recurring task: 1. Open...",
            "relevance_score": 0.95
        }
    ],
    "best_match": {...}
}
```

---

## 2. Sentiment Analysis Skill

### Skill Name
`sentiment_analysis`

### Description
Analyze the emotional tone and sentiment of customer messages to determine appropriate response style and escalation needs.

### When to Use
- **Every incoming customer message** (mandatory)
- Before generating response (to adjust tone)
- To detect declining satisfaction during conversation
- To identify escalation triggers (angry customers)

### Inputs
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| text | string | Yes | The customer message text | "This is RIDICULOUS!!!" |
| conversation_context | array | No | Previous messages for trend analysis | `[{content, sentiment}]` |

### Outputs
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| sentiment_score | float | Score from 0.0 (very negative) to 1.0 (very positive) | 0.20 |
| classification | string | Category: positive, neutral, frustrated, angry | "angry" |
| anger_signals | array | Detected anger indicators | `["multiple_exclamation", "all_caps"]` |
| trend | string | Sentiment trend: improving, stable, declining | "declining" |
| confidence | float | Confidence in analysis (0-1) | 0.92 |
| recommended_action | string | Suggested response approach | "escalate_immediately" |

### Sentiment Thresholds
| Score Range | Classification | Action |
|-------------|---------------|--------|
| 0.7 - 1.0 | positive | Friendly, enthusiastic response |
| 0.4 - 0.7 | neutral | Standard helpful response |
| 0.3 - 0.4 | frustrated | Show empathy, prioritize resolution |
| 0.0 - 0.3 | angry | Escalate OR high empathy + fast resolution |

### Implementation Notes

**Prototype (Exercise 1.3):**
- Rule-based sentiment detection in `src/agent/memory_agent.py`
- Positive/negative word lists (25+ words each)
- Anger signal detection (caps, exclamation marks, specific words)
- Weighted average for trend calculation

**Production (Target):**
- ML-based sentiment model
- Context-aware analysis
- Multi-language support
- Integration with conversation memory

### Related MCP Tools
- `analyze_sentiment(text)` - Direct implementation

### Example Usage
```
Customer: "This is RIDICULOUS!!! Your app keeps CRASHING!!!"

Skill Call: sentiment_analysis(
    text="This is RIDICULOUS!!! Your app keeps CRASHING!!!",
    conversation_context=[...]
)

Result: {
    "sentiment_score": 0.00,
    "classification": "angry",
    "anger_signals": [
        "multiple_exclamation",
        "all_caps",
        "rudeness: ridiculous",
        "urgency: NOW"
    ],
    "trend": "declining",
    "confidence": 0.95,
    "recommended_action": "escalate_immediately"
}
```

---

## 3. Escalation Decision Skill

### Skill Name
`escalation_decision`

### Description
Determine when a customer issue requires human intervention based on content analysis, sentiment, and business rules.

### When to Use
- After analyzing customer message
- Before sending final response
- When sentiment is declining
- When customer explicitly requests human

### Inputs
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| message_content | string | Yes | Customer's message | "I want a refund" |
| sentiment_score | float | Yes | Current sentiment | 0.25 |
| conversation_history | array | No | Previous interactions | `[{role, content}]` |
| customer_plan | string | No | Customer's subscription plan | "pro" |
| topics_discussed | array | No | Topics covered so far | `["billing", "refund"]` |

### Outputs
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| should_escalate | boolean | True if escalation needed | true |
| reason | string | Escalation reason code | "refund_request" |
| priority | string | normal, high, critical | "high" |
| suggested_response | string | Message to customer before handoff | "I'm connecting you..." |
| confidence | float | Confidence in decision (0-1) | 0.98 |

### Escalation Reasons
| Reason Code | Trigger | Priority | Response Time |
|-------------|---------|----------|---------------|
| pricing_inquiry | Pricing, discount, cost questions | P3 | 4 hours |
| refund_request | Refund, chargeback, money back | P2 | 4 hours |
| security_incident | Hacked, unauthorized access | P1 | 1 hour |
| legal_inquiry | Lawyer, lawsuit, legal action | P1 | 1 hour |
| human_requested | Customer asks for human | P3 | 4 hours |
| angry_customer | Sentiment < 0.3 | P2 | 2 hours |
| technical_bug | Bug report with no workaround | P3 | 24 hours |
| no_answer | Cannot find info after 2 searches | P3 | 24 hours |

### Implementation Notes

**Prototype (Exercise 1.2 & 1.4):**
- Keyword-based trigger detection in `src/agent/core_loop.py`
- Sentiment threshold check (< 0.3)
- MCP tool: `escalate_to_human(ticket_id, reason, urgency)`

**Production (Target):**
- Rule engine with configurable triggers
- ML-based escalation prediction
- Integration with human agent queue
- SLA tracking

### Related MCP Tools
- `escalate_to_human(ticket_id, reason, urgency)` - Executes escalation

### Example Usage
```
Customer: "I was charged twice! I want my money back!"

Skill Call: escalation_decision(
    message_content="I was charged twice! I want my money back!",
    sentiment_score=0.35,
    topics_discussed=["billing", "refund"]
)

Result: {
    "should_escalate": true,
    "reason": "refund_request",
    "priority": "high",
    "suggested_response": "I'm connecting you with our billing team...",
    "confidence": 0.98
}
```

---

## 4. Channel Adaptation Skill

### Skill Name
`channel_adaptation`

### Description
Adapt response format, tone, and length based on the communication channel (Email, WhatsApp, Web Form).

### When to Use
- **Before sending any response** (mandatory)
- When formatting agent output
- When adjusting tone for channel norms

### Inputs
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| response_content | string | Yes | The raw response message | "To reset password..." |
| channel | string | Yes | Target channel (email, whatsapp, web_form) | "whatsapp" |
| customer_name | string | No | For personalization | "John" |
| ticket_id | string | No | For reference inclusion | "TKT-12345" |
| conversation_context | string | No | Previous context | "Continuing discussion..." |

### Outputs
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| formatted_response | string | Channel-appropriate response | "Hey! To reset..." |
| character_count | int | Length of formatted response | 145 |
| within_limits | boolean | Whether response fits channel limits | true |
| formatting_applied | array | List of formatting rules applied | `["truncation", "emoji", "signature"]` |

### Channel Specifications
| Channel | Tone | Max Length | Structure | Emoji |
|---------|------|------------|-----------|-------|
| Email | Formal, warm | 500 words | Greeting → Answer → Steps → Sign-off | None |
| WhatsApp | Casual, concise | 300 chars preferred | Direct answer → Offer help | 1-2 max |
| Web Form | Semi-formal | 300 words | Thanks → Answer → Link → Close | Occasional |

### Implementation Notes

**Prototype (Exercise 1.2 & 1.4):**
- Template-based formatting in `src/agent/core_loop.py`
- Channel-specific response templates
- MCP tool: `send_response(ticket_id, message, channel)`

**Production (Target):**
- Dynamic formatting based on channel config
- A/B testing for response effectiveness
- Localization support
- Rich media support (images, buttons)

### Related MCP Tools
- `send_response(ticket_id, message, channel)` - Includes channel formatting

### Example Usage
```
Raw Response: "To reset password, go to settings and click reset password link."

Skill Call: channel_adaptation(
    response_content="To reset password, go to settings and click reset password link.",
    channel="whatsapp",
    customer_name="John"
)

Result: {
    "formatted_response": "Hey! To reset password: Settings → Security → Reset Password. Check your email for the link! Need anything else? 😊",
    "character_count": 145,
    "within_limits": true,
    "formatting_applied": ["casual_tone", "emoji", "whatsapp_signature"]
}
```

---

## 5. Customer Identification Skill

### Skill Name
`customer_identification`

### Description
Identify and unify customer identity across multiple channels using email, phone, and name matching.

### When to Use
- **On every incoming message** (mandatory)
- Before accessing customer history
- When customer contacts from new channel
- When merging duplicate profiles

### Inputs
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| email | string | No | Customer email address | "sarah@example.com" |
| phone | string | No | Customer phone number | "+14155551234" |
| name | string | No | Customer name | "Sarah Johnson" |
| channel | string | Yes | Source channel | "whatsapp" |
| channel_message_id | string | No | External message ID | "gmail_msg_12345" |

### Outputs
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| customer_id | string | Unified customer UUID | "cust-12345-uuid" |
| is_returning | boolean | Whether customer is recognized | true |
| matched_identifiers | array | Which identifiers matched | `["email"]` |
| confidence | float | Match confidence score | 0.95 |
| customer_profile | object | Full customer data | `{email, phone, plan, ...}` |
| cross_channel_history | boolean | Has history on other channels | true |

### Matching Logic
| Match Type | Confidence | Action |
|------------|------------|--------|
| Exact email match | 0.95 | Return existing customer |
| Exact phone match | 0.95 | Return existing customer |
| Email + name match | 0.98 | Very high confidence |
| Phone + name match | 0.98 | Very high confidence |
| Name only match | 0.50 | Low confidence - needs verification |
| No match | 0.00 | Create new customer |

### Implementation Notes

**Prototype (Exercise 1.3):**
- In-memory store with email/phone indexes in `src/agent/memory_agent.py`
- Cross-channel identifier tracking
- 24-hour conversation window for continuity

**Production (Target):**
- PostgreSQL with customer_identifiers table
- Fuzzy matching for name variations
- Duplicate detection and merging
- GDPR compliance (right to be forgotten)

### Related MCP Tools
- `create_ticket(customer_id, ...)` - Uses identified customer
- `get_customer_history(customer_id)` - Retrieves cross-channel history

### Example Usage
```
Incoming WhatsApp: {
    "phone": "+14155551234",
    "name": "Sarah Johnson"
}

Skill Call: customer_identification(
    phone="+14155551234",
    name="Sarah Johnson",
    channel="whatsapp"
)

Result: {
    "customer_id": "aeaa5761-2d6b-467e-85f4-3a5acc629b41",
    "is_returning": true,
    "matched_identifiers": ["email"],
    "confidence": 0.85,
    "customer_profile": {
        "email": "sarah@example.com",
        "phone": "+14155551234",
        "name": "Sarah Johnson",
        "plan": "pro"
    },
    "cross_channel_history": true
}
```

---

## 6. Conversation Memory Skill (Bonus)

### Skill Name
`conversation_memory`

### Description
Maintain context across multiple messages and interactions, enabling coherent multi-turn conversations.

### When to Use
- Before responding to any message
- When customer references previous discussion
- When continuing a conversation thread
- When customer switches channels mid-conversation

### Inputs
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| customer_id | string | Yes | Customer identifier | "cust-12345" |
| conversation_id | string | No | Specific conversation thread | "conv-67890" |
| time_window_hours | int | No | How far back to look (default: 24) | 24 |

### Outputs
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| conversation_context | string | Summary of recent conversation | "Customer asked about..." |
| topics_discussed | array | Topics covered so far | `["password_reset"]` |
| pending_issues | array | Unresolved items | `["waiting_for_email"]` |
| sentiment_trend | string | How sentiment has evolved | "stable" |
| channel_history | array | Channels used in conversation | `["email", "whatsapp"]` |
| message_count | int | Number of messages in thread | 4 |

### Implementation Notes

**Prototype (Exercise 1.3):**
- Conversation class with message history in `src/agent/memory_agent.py`
- State tracking (sentiment, topics, resolution status)
- 24-hour active window

**Production (Target):**
- PostgreSQL conversations and messages tables
- Vector-based context retrieval
- Long-term memory (beyond 24 hours)
- Context summarization for long conversations

### Related MCP Tools
- `get_customer_history(customer_id)` - Retrieves full history

### Example Usage
```
Customer (follow-up): "Also, can I add team members to specific tasks?"

Skill Call: conversation_memory(
    customer_id="aeaa5761-2d6b-467e-85f4-3a5acc629b41",
    time_window_hours=24
)

Result: {
    "conversation_context": "Customer asked about recurring tasks 2 hours ago via email",
    "topics_discussed": ["recurring_tasks"],
    "pending_issues": ["didn't_receive_reset_email"],
    "sentiment_trend": "stable",
    "channel_history": ["email", "whatsapp"],
    "message_count": 3
}
```

---

## 7. Topic Extraction Skill (Bonus)

### Skill Name
`topic_extraction`

### Description
Extract and categorize topics from customer messages for routing, reporting, and knowledge base analytics.

### When to Use
- On every incoming message
- For conversation categorization
- For analytics and reporting
- For routing to specialized agents

### Inputs
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| message_content | string | Yes | Customer message text | "How do I connect Slack?" |
| subject | string | No | Email/form subject line | "Slack integration help" |

### Outputs
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| topics | array | List of identified topics | `["slack_integration"]` |
| primary_topic | string | Main topic category | "slack_integration" |
| confidence | float | Topic classification confidence | 0.92 |
| requires_routing | boolean | Whether specialist routing needed | false |

### Topic Categories
- `password_reset` - Login and access issues
- `recurring_tasks` - Task automation
- `gantt_chart` - Timeline visualization
- `slack_integration` - Slack connectivity
- `github_integration` - GitHub connectivity
- `pricing` - Cost and plans
- `export` - Data export
- `team_management` - Adding members
- `file_upload` - File limits and issues
- `bug_report` - Technical issues
- `feature_request` - New feature requests

### Implementation Notes

**Prototype (Exercise 1.3):**
- Keyword-based topic extraction in `src/agent/memory_agent.py`
- Topic tracking in conversation state

**Production (Target):**
- ML-based topic classification
- Hierarchical topic taxonomy
- Auto-tagging for analytics
- Integration with routing engine

### Related MCP Tools
- None directly (used internally for analytics)

### Example Usage
```
Customer: "How do I connect Slack to get notifications for my projects?"

Skill Call: topic_extraction(
    message_content="How do I connect Slack to get notifications for my projects?",
    subject="Slack integration help"
)

Result: {
    "topics": ["slack_integration", "notification"],
    "primary_topic": "slack_integration",
    "confidence": 0.92,
    "requires_routing": false
}
```

---

## Skill Interaction Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    SKILL EXECUTION FLOW                          │
│                                                                  │
│  1. Customer Message Inbound                                     │
│         │                                                        │
│         ▼                                                        │
│  2. Customer Identification ◄───────┐                           │
│         │                            │                           │
│         ▼                            │                           │
│  3. Conversation Memory ────────────┤                           │
│         │                            │                           │
│         ▼                            │                           │
│  4. Sentiment Analysis              │                           │
│         │                            │                           │
│         ▼                            │                           │
│  5. Topic Extraction                │                           │
│         │                            │                           │
│         ▼                            │                           │
│  6. Knowledge Retrieval             │                           │
│         │                            │                           │
│         ▼                            │                           │
│  7. Escalation Decision ◄───────────┘                           │
│         │                                                        │
│    ┌────┴────┐                                                   │
│    │         │                                                   │
│    ▼         ▼                                                   │
│ Escalate   Don't Escalate                                        │
│    │         │                                                   │
│    │         ▼                                                   │
│    │    8. Channel Adaptation                                    │
│    │         │                                                   │
│    │         ▼                                                   │
│    │    Send Response                                            │
│    │                                                              │
│    ▼                                                              │
│ Human Handoff                                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Skill Priority Matrix

| Skill | Priority | Frequency | Critical For |
|-------|----------|-----------|--------------|
| Customer Identification | High | Every message | Cross-channel continuity |
| Sentiment Analysis | High | Every message | Customer experience |
| Escalation Decision | Critical | Every message | Risk management |
| Channel Adaptation | Medium | Every response | Customer experience |
| Knowledge Retrieval | High | Most messages | Answer accuracy |
| Conversation Memory | Medium | Follow-ups | Context awareness |
| Topic Extraction | Low | Analytics | Reporting |

---

## Skills Implementation Status

| Skill | Prototype | Production | Status |
|-------|-----------|------------|--------|
| Knowledge Retrieval | ✅ Keyword search | ⏳ Vector search | In Progress |
| Sentiment Analysis | ✅ Rule-based | ⏳ ML model | In Progress |
| Escalation Decision | ✅ Keyword rules | ⏳ Enhanced rules | In Progress |
| Channel Adaptation | ✅ Template-based | ⏳ Dynamic formatting | In Progress |
| Customer Identification | ✅ Email/phone lookup | ⏳ Fuzzy matching | In Progress |
| Conversation Memory | ✅ In-memory | ⏳ PostgreSQL | In Progress |
| Topic Extraction | ✅ Keyword matching | ⏳ Classification model | Planned |

---

## Skills to MCP Tools Mapping

| Skill | Primary MCP Tool | Supporting MCP Tools |
|-------|------------------|---------------------|
| Knowledge Retrieval | `search_knowledge_base` | - |
| Sentiment Analysis | `analyze_sentiment` | - |
| Escalation Decision | `escalate_to_human` | `get_ticket_status` |
| Channel Adaptation | `send_response` | - |
| Customer Identification | `create_ticket` | `get_customer_history` |
| Conversation Memory | `get_customer_history` | `get_ticket_status` |
| Topic Extraction | (internal) | - |

---

**End of Agent Skills Manifest**

*Generated during Phase 1 Incubation - Exercise 1.5*

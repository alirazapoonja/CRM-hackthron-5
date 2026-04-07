# Transition Checklist: General Agent → Custom Agent

**Phase:** Transition (Hours 15-18)  
**Date:** March 2025  
**Agent:** Customer Success FTE  
**Status:** Ready for Production Build

---

## 1. Discovered Requirements

### Functional Requirements (from Incubation)

- [x] **Requirement 1:** Support THREE communication channels (Email/Gmail, WhatsApp, Web Form)
- [x] **Requirement 2:** Cross-channel customer identification (unified profile by email/phone)
- [x] **Requirement 3:** Conversation continuity across channels (remember context if customer switches from email to WhatsApp)
- [x] **Requirement 4:** Channel-aware response formatting (Email=formal/detailed, WhatsApp=concise/casual, Web=semi-formal)
- [x] **Requirement 5:** Sentiment analysis with 4 levels (positive, neutral, frustrated, angry)
- [x] **Requirement 6:** Automatic escalation for pricing, refund, legal, security inquiries
- [x] **Requirement 7:** Mandatory tool execution order (create_ticket → get_history → search_kb → send_response)
- [x] **Requirement 8:** All interactions logged with channel metadata
- [x] **Requirement 9:** Knowledge base search with relevance scoring
- [x] **Requirement 10:** Topic extraction for analytics and reporting

### Non-Functional Requirements

- [x] **Requirement 11:** Response time < 3 seconds (processing), < 30 seconds (delivery)
- [x] **Requirement 12:** Accuracy > 85% on test set
- [x] **Requirement 13:** Escalation rate < 38%
- [x] **Requirement 14:** Cross-channel identification > 95% accuracy
- [x] **Requirement 15:** 24/7 uptime > 99.9%
- [x] **Requirement 16:** Auto-scaling based on load (3-30 worker pods)

---

## 2. Working Prompts

### System Prompt That Worked (from Incubation)

```
You are a Customer Success agent for TechCorp SaaS (TaskFlow Pro).

## Your Purpose
Handle routine customer support queries with speed, accuracy, and empathy across multiple channels.

## Channel Awareness
You receive messages from three channels. Adapt your communication style:
- **Email**: Formal, detailed responses. Include proper greeting and signature.
- **WhatsApp**: Concise, conversational. Keep responses under 300 characters when possible.
- **Web Form**: Semi-formal, helpful. Balance detail with readability.

## Required Workflow (ALWAYS follow this order)
1. FIRST: Call `create_ticket` to log the interaction
2. THEN: Call `get_customer_history` to check for prior context
3. THEN: Call `search_knowledge_base` if product questions arise
4. FINALLY: Call `send_response` to reply (NEVER respond without this tool)

## Hard Constraints (NEVER violate)
- NEVER discuss pricing → escalate immediately with reason "pricing_inquiry"
- NEVER promise features not in documentation
- NEVER process refunds → escalate with reason "refund_request"
- NEVER share internal processes or system details
- NEVER respond without using send_response tool
- NEVER exceed response limits: Email=500 words, WhatsApp=300 chars, Web=300 words

## Escalation Triggers (MUST escalate when detected)
- Customer mentions "lawyer", "legal", "sue", or "attorney"
- Customer uses profanity or aggressive language (sentiment < 0.3)
- Cannot find relevant information after 2 search attempts
- Customer explicitly requests human help
- Customer on WhatsApp sends "human", "agent", or "representative"

## Response Quality Standards
- Be concise: Answer the question directly, then offer additional help
- Be accurate: Only state facts from knowledge base or verified customer data
- Be empathetic: Acknowledge frustration before solving problems
- Be actionable: End with clear next step or question

## Context Variables Available
- {{customer_id}}: Unique customer identifier
- {{conversation_id}}: Current conversation thread
- {{channel}}: Current channel (email/whatsapp/web_form)
- {{ticket_subject}}: Original subject/topic
```

### Tool Descriptions That Worked

**search_knowledge_base:**
```
Search product documentation for relevant information.

Use this when the customer asks questions about product features,
how to use something, or needs technical information.

Args:
    query: The search query from the customer
    max_results: Maximum number of results to return (default: 5)

Returns:
    Formatted search results with relevance scores
```

**create_ticket:**
```
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
```

**get_customer_history:**
```
Get customer's complete interaction history across ALL channels.

Use this to understand context from previous conversations,
even if they happened on a different channel.

Args:
    customer_id: Customer identifier (UUID or email)

Returns:
    Formatted customer history with all interactions
```

**escalate_to_human:**
```
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
```

**send_response:**
```
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
```

---

## 3. Edge Cases Found

| Edge Case | How It Was Handled | Test Case Needed |
|-----------|-------------------|------------------|
| Empty message | Return helpful prompt asking for clarification | ✅ Yes |
| Pricing question | Immediate escalation with pricing_inquiry reason | ✅ Yes |
| Angry customer (sentiment < 0.3) | Show empathy OR escalate if very angry | ✅ Yes |
| Multi-part question | Answer all parts, number responses | ✅ Yes |
| Non-English message | Respond in same language if possible | ✅ Yes |
| Security incident mention | IMMEDIATE escalation (P1 critical) | ✅ Yes |
| Feature doesn't exist | Acknowledge, suggest workaround, escalate if insistent | ✅ Yes |
| Plan limitation question | Explain limitation, offer upgrade path | ✅ Yes |
| Third-party integration issue | Troubleshoot, escalate if on our end | ✅ Yes |
| Channel switch mid-conversation | Recognize customer, maintain context | ✅ Yes |
| Customer requests human | Immediate escalation with human_requested | ✅ Yes |
| Duplicate charge complaint | Escalate to billing (refund_request) | ✅ Yes |
| Vague/unclear question | Ask for clarification with examples | ✅ Yes |
| ALL CAPS anger | Detect as anger signal, escalate or show empathy | ✅ Yes |
| Multiple exclamation marks!!! | Detect as anger signal | ✅ Yes |

---

## 4. Response Patterns

### Email Response Pattern
```
Dear [NAME],

Thank you for reaching out to TaskFlow Support!

[ACKNOWLEDGMENT - I understand the frustration / Great question]

[ANSWER - Direct response with step-by-step if how-to]
1. Step one
2. Step two
3. Step three

[OFFER ADDITIONAL HELP]
Let me know if you need anything else!

Best regards,
TaskFlow Support Team
📧 support@taskflowpro.com
📚 https://help.taskflowpro.com

---
Ticket Reference: {ticket_id}
```

**Characteristics:**
- Formal greeting with customer name
- Complete, detailed answer
- Numbered steps for how-to
- Professional sign-off with contact info
- Ticket reference included

### WhatsApp Response Pattern
```
[GREETING - optional, casual]
[DIRECT ANSWER - under 300 characters]
[OFFER HELP - brief]

Example: "Hey! To reset password: Settings → Security → Reset Password. Check your email for the link! Need anything else? 😊"
```

**Characteristics:**
- Casual or no greeting
- Very concise (under 300 chars)
- Direct answer without fluff
- Optional emoji (1 max)
- Quick offer for more help

### Web Form Response Pattern
```
Thanks for contacting TaskFlow support!

[ANSWER with clear steps]

📖 Full guide: [LINK TO DOCS]

Reply if you need more help!

Thanks,
TaskFlow Support
```

**Characteristics:**
- Semi-formal tone
- Medium detail (200-300 words)
- Link to full documentation
- Friendly but professional

---

## 5. Escalation Rules (Finalized)

### Immediate Escalation (Do Not Answer)

| Trigger | Reason Code | Priority | Response Time |
|---------|-------------|----------|---------------|
| Pricing inquiry (cost, discount, enterprise) | `pricing_inquiry` | P3 | 4 hours |
| Refund request (refund, chargeback, money back) | `refund_request` | P2 | 4 hours |
| Security incident (hacked, breach, unauthorized) | `security_incident` | P1 | 1 hour |
| Legal mention (lawyer, sue, legal, attorney) | `legal_inquiry` | P1 | 1 hour |
| Human requested (human, agent, representative) | `human_requested` | P3 | 4 hours |

### Conditional Escalation (Try to Help First)

| Trigger | Reason Code | Priority | When to Escalate |
|---------|-------------|----------|------------------|
| Angry customer (sentiment < 0.3) | `angry_customer` | P2 | If sentiment doesn't improve OR very angry |
| Technical bug (crash, error, broken) | `technical_bug` | P3 | If no workaround exists |
| Integration issue (Slack, GitHub sync) | `integration_issue` | P3 | If issue is on our end |
| Feature request (can you add, wish it had) | `feature_request` | P4 | If customer insists or feature is critical |
| No answer found (after 2 searches) | `no_answer` | P3 | If knowledge base has no relevant info |

### Escalation Response Template
```
I understand your concern. I'm escalating this to our [TEAM] ({reason}).

A human agent will review your case and reach out within [TIME].

Reference: ESC-{ID}
```

---

## 6. Performance Baseline

From incubation prototype testing:

| Metric | Measured | Target | Status |
|--------|----------|--------|--------|
| **Response Time (Processing)** | 0.5-1.5 seconds | < 3 seconds | ✅ Pass |
| **Accuracy on Test Set** | ~80% (estimated) | > 85% | ⚠️ Needs improvement |
| **Escalation Rate** | 35% | < 38% | ✅ Pass |
| **Cross-Channel ID** | 90% (prototype) | > 95% | ⚠️ Needs production DB |
| **Sentiment Detection** | 85% (rule-based) | > 90% | ⚠️ Needs ML model |
| **Knowledge Search Accuracy** | 75% (keyword) | > 85% | ⚠️ Needs vector search |

---

## Pre-Transition Checklist

### From Incubation (Must Have Before Proceeding)

- [x] Working prototype that handles basic queries
- [x] Documented edge cases (minimum 10) → **15 documented**
- [x] Working system prompt
- [x] MCP tools defined and tested (7 tools)
- [x] Channel-specific response patterns identified
- [x] Escalation rules finalized
- [x] Performance baseline measured

### Transition Steps

- [ ] Created production folder structure
- [ ] Extracted prompts to prompts.py
- [ ] Converted MCP tools to @function_tool
- [ ] Added Pydantic input validation to all tools
- [ ] Added error handling to all tools
- [ ] Created transition test suite
- [ ] All transition tests passing

### Ready for Production Build

- [ ] Database schema designed
- [ ] Kafka topics defined
- [ ] Channel handlers outlined
- [ ] Kubernetes resource requirements estimated
- [ ] API endpoints listed

---

## Transition Complete Criteria

You're ready to proceed to Part 2 (Specialization) when:

- [ ] ✅ All transition tests pass
- [ ] ✅ Prompts are extracted and documented
- [ ] ✅ Tools have proper input validation
- [ ] ✅ Error handling exists for all tools
- [ ] ✅ Edge cases are documented with test cases
- [ ] ✅ Production folder structure is created

---

**Next Step:** Once all checkboxes are complete, proceed to Specialization Phase (Exercise 2.1: Database Schema)

---

*Generated during Transition Phase - Exercise 1.1*

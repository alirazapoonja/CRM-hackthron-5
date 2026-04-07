# Discovery Log: Customer Success FTE Requirements

**Date:** March 2025  
**Phase:** Incubation - Exercise 1.1  
**Analyzed By:** Claude Code (Agent Factory)  
**Dataset:** 35 sample tickets across 3 channels

---

## Executive Summary

Analysis of 35 customer support tickets reveals clear patterns in inquiry types, channel-specific behaviors, and escalation triggers. The Customer Success FTE must handle **7 primary categories** of inquiries with **channel-aware responses** and **strict escalation rules** for pricing, legal, and security matters.

---

## 1. Ticket Category Distribution

| Category | Count | Percentage | Escalation Rate |
|----------|-------|------------|-----------------|
| how_to | 7 | 20% | 0% |
| technical_issue | 8 | 23% | 12% |
| feature_question | 6 | 17% | 0% |
| pricing | 6 | 17% | 100% ⚠️ |
| billing | 4 | 11% | 75% ⚠️ |
| integration_issue | 3 | 9% | 0% |
| feature_request | 2 | 6% | 0% |
| security | 1 | 3% | 100% ⚠️ |
| positive_feedback | 1 | 3% | 0% |

### Key Finding: 
**38% of tickets require escalation** (pricing, billing disputes, security). The FTE must confidently handle 62% of inquiries autonomously.

---

## 2. Channel-Specific Patterns

### Email Characteristics
- **Average length:** 150-300 words
- **Tone:** Formal, detailed context provided
- **Structure:** Greeting → Context → Question → Sign-off
- **Common senders:** Managers, Directors, C-level
- **Typical issues:** Complex technical problems, account management, escalations

**Sample Email Patterns:**
```
"Hi TaskFlow Team,

I'm the [ROLE] at [COMPANY] and we've been using TaskFlow for [TIME].
[Detailed context about situation - 3-5 sentences]
[Specific question with multiple parts]

Thanks so much for your help!

Best,
[NAME]
[TITLE]"
```

### WhatsApp Characteristics
- **Average length:** 10-50 characters
- **Tone:** Casual, urgent, conversational
- **Structure:** Direct question, no greeting/signature
- **Common senders:** Individual users, on-the-go
- **Typical issues:** Quick how-to, urgent problems, status checks

**Sample WhatsApp Patterns:**
```
"Hey! How do I reset my password? Forgot it 😅"
"Hi, can't see Gantt view. On Pro plan. Bug?"
"Need to talk to a human about billing. Was charged twice!"
```

### Web Form Characteristics
- **Average length:** 80-150 words
- **Tone:** Semi-formal, structured
- **Structure:** Subject line + categorized form + detailed message
- **Common senders:** Power users, admins
- **Typical issues:** Technical configuration, plan upgrades, feature requests

**Sample Web Form Patterns:**
```
Subject: [Clear topic description]
Category: [Selected from dropdown]
Priority: [Selected: low/medium/high/urgent]

Hello TaskFlow Team,
[Context - 2-3 sentences]
[Specific question or issue]
[Account details if relevant]

Thanks,
[NAME]"
```

---

## 3. Question Type Analysis

### How-To Questions (20%)
**Examples:**
- "How do I set up recurring tasks?"
- "How to export all my data?"
- "How do I add custom statuses?"

**Handling Strategy:**
1. Search knowledge base for relevant documentation
2. Provide step-by-step instructions (numbered list)
3. Include links to full documentation
4. Offer additional related help

### Technical Issues (23%)
**Examples:**
- "Gantt chart not showing up"
- "GitHub integration not syncing"
- "App keeps crashing when uploading files"

**Handling Strategy:**
1. Acknowledge frustration
2. Ask clarifying questions (plan type, browser, steps to reproduce)
3. Provide troubleshooting steps
4. Escalate if no resolution after 2 attempts

### Feature Questions (17%)
**Examples:**
- "What types of custom fields are available?"
- "Is there a mobile app for iOS?"
- "What's the API rate limit on Pro?"

**Handling Strategy:**
1. Search product documentation
2. Provide accurate feature information
3. Include plan restrictions if applicable
4. Link to pricing/feature comparison page

### Pricing Inquiries (17%) → ALWAYS ESCALATE
**Examples:**
- "Enterprise pricing for 500+ users?"
- "Discount for non-profit organizations?"
- "Cost difference to upgrade from Pro to Business?"

**Handling Strategy:**
- **DO NOT ANSWER** - escalate immediately
- Response: "I'll connect you with our billing specialist..."

### Billing Issues (11%) → USUALLY ESCALATE
**Examples:**
- "Invoice request for Q1 2025"
- "Refund request - duplicate charge"
- "Was charged twice!"

**Handling Strategy:**
- Simple invoice requests → can provide if system access available
- Refunds/disputes → escalate immediately

---

## 4. Escalation Signal Analysis

### Clear Escalation Triggers Found

| Trigger | Frequency in Dataset | Priority |
|---------|---------------------|----------|
| Pricing inquiry | 6 tickets | P3 |
| Refund request | 2 tickets | P2 |
| Security concern | 1 ticket | P1 ⚠️ |
| Human requested | 1 ticket | P3 |
| Legal/compliance mention | 0 tickets | P1 |
| Angry customer (sentiment <0.3) | 2 tickets | P2 |

### Angry Customer Indicators
From the dataset:
```
"This is ridiculous!!! App keeps crashing..." (whatsapp_006)
"Fix this NOW!!!" (whatsapp_006)
"URGENT: Security concern..." (email_008)
```

**Signals:**
- Multiple exclamation marks (!!!)
- ALL CAPS words
- Words: "ridiculous", "unacceptable", "terrible"
- Threats: "cancel", "switch", "chargeback"

---

## 5. Customer Identification Patterns

### Email Channel
- **Primary identifier:** Email address (From header)
- **Secondary:** Name from signature
- **Company context:** Often in email domain or signature

### WhatsApp Channel
- **Primary identifier:** Phone number
- **Secondary:** Profile name (if available)
- **Challenge:** Same customer may use email AND WhatsApp

### Web Form Channel
- **Primary identifier:** Email address (form field)
- **Secondary:** Name (form field)
- **Additional:** Category, priority from form selection

### Cross-Channel Challenge
**Discovery:** Customers may contact via multiple channels. Need unified customer profile using:
- Email as primary key
- Phone as secondary key
- Name matching for disambiguation

---

## 6. Response Requirements by Channel

### Email Response Template
```
Dear [NAME],

[ACKNOWLEDGMENT - Thanks for reaching out / I understand the frustration]

[ANSWER - Direct response to question]

[STEPS - Numbered list if how-to]
1. Step one
2. Step two
3. Step three

[OFFER ADDITIONAL HELP]
Let me know if you need anything else!

Best regards,
TaskFlow Support Team
[TICKET REFERENCE]
```

### WhatsApp Response Template
```
[GREETING - optional, casual]
[DIRECT ANSWER - under 300 chars]
[OFFER HELP - brief]

Example: "Hey! To reset password: Settings → Security → Reset Password. Check your email for the link! Need anything else? 😊"
```

### Web Form Response Template
```
Thanks for contacting TaskFlow support!

[ANSWER with clear steps]

📖 Full guide: [LINK TO DOCS]

Reply if you need more help!

Thanks,
TaskFlow Support
```

---

## 7. Edge Cases Discovered

| Edge Case | Frequency | Handling Strategy |
|-----------|-----------|-------------------|
| Empty/vague message | Potential | Ask for clarification |
| Multi-part question | 8 tickets | Answer all parts, number responses |
| Non-English message | 1 ticket (French) | Respond in same language if possible |
| Extremely angry customer | 2 tickets | Empathy first, then escalate |
| Security incident | 1 ticket | IMMEDIATE escalation + urgent response |
| Feature doesn't exist | 3 tickets | Acknowledge, suggest workaround, escalate |
| Plan limitation question | 5 tickets | Explain limitation, offer upgrade path |
| Third-party integration issue | 3 tickets | Troubleshoot, then escalate if on our end |

---

## 8. Knowledge Base Requirements

Based on the tickets, the knowledge base must contain:

### Core Articles (Must Have)
1. **Getting Started**
   - Creating your first project
   - Inviting team members
   - Basic task management

2. **Task Management**
   - Creating and assigning tasks
   - Recurring tasks (ALL frequencies)
   - Task dependencies
   - Subtasks and checklists

3. **Views & Visualization**
   - Kanban board usage
   - Gantt chart (plan restrictions)
   - Calendar view
   - List view customization

4. **Integrations**
   - Slack setup and troubleshooting
   - GitHub integration
   - Google Drive integration
   - Zapier automations

5. **Account & Billing**
   - Password reset
   - Plan comparison
   - Export data
   - Cancel subscription

6. **Troubleshooting**
   - Common login issues
   - File upload problems
   - Sync issues
   - Browser compatibility

---

## 9. Sentiment Analysis Requirements

### Sentiment Scoring Needed
- **Positive (>0.7):** "Love the product!", "Amazing!", "Thank you!"
- **Neutral (0.4-0.7):** Standard inquiries
- **Frustrated (0.3-0.4):** "Having issues", "Not working"
- **Angry (<0.3):** "Ridiculous!", "Fix this NOW!", "!!!"

### Action Based on Sentiment
| Sentiment | Action |
|-----------|--------|
| > 0.7 | Friendly, enthusiastic response |
| 0.4 - 0.7 | Standard helpful response |
| 0.3 - 0.4 | Show empathy, prioritize resolution |
| < 0.3 | Escalate OR show high empathy + fast resolution |

---

## 10. Memory & State Requirements

### Conversation Memory
- Remember previous questions from same customer
- Track if customer is continuing a topic or asking new question
- Maintain context across channel switches

### State to Track Per Interaction
1. **Customer ID** (email or phone)
2. **Conversation ID** (thread)
3. **Channel** (email/whatsapp/web)
4. **Ticket ID** (if created)
5. **Sentiment Score**
6. **Topics Discussed**
7. **Resolution Status** (open/in-progress/resolved/escalated)
8. **Escalation Reason** (if escalated)

---

## 11. Performance Requirements (Inferred)

### Response Time Expectations
- **WhatsApp:** Immediate (<30 seconds) - users expect instant replies
- **Email:** Can be slower (minutes acceptable)
- **Web Form:** Fast response expected (<2 minutes)

### Accuracy Requirements
- **How-to answers:** 100% accurate steps
- **Feature info:** Must match actual product
- **Troubleshooting:** Must not provide incorrect fixes

---

## 12. Discovery Summary: Required Capabilities

### Core Agent Skills
1. ✅ **Knowledge Retrieval** - Search and extract from product docs
2. ✅ **Sentiment Analysis** - Detect customer emotional state
3. ✅ **Escalation Decision** - Know when to involve humans
4. ✅ **Channel Adaptation** - Format responses appropriately
5. ✅ **Customer Identification** - Unified profile across channels

### Required Tools
1. ✅ `search_knowledge_base(query)` - Find relevant documentation
2. ✅ `create_ticket(customer_id, issue, priority, channel)` - Log interactions
3. ✅ `get_customer_history(customer_id)` - Cross-channel context
4. ✅ `escalate_to_human(ticket_id, reason)` - Hand off complex issues
5. ✅ `send_response(ticket_id, message, channel)` - Reply via correct channel

### Required Data Stores
1. ✅ **Customers** - Unified profile (email, phone, name)
2. ✅ **Conversations** - Thread tracking with channel metadata
3. ✅ **Tickets** - Issue tracking with status
4. ✅ **Messages** - Full conversation history
5. ✅ **Knowledge Base** - Searchable product documentation

---

## 13. Next Steps (Exercise 1.2)

Based on this analysis, the prototype should:

1. **Accept input:** Message + channel metadata
2. **Identify customer:** By email or phone
3. **Analyze sentiment:** Score the message
4. **Check escalation triggers:** Pricing, legal, security, angry
5. **Search knowledge base:** Find relevant articles
6. **Generate response:** Channel-appropriate formatting
7. **Log interaction:** Create ticket and store messages

---

**End of Discovery Log**

*Generated during Phase 1 Incubation - Exercise 1.1*

# TechCorp Escalation Rules

## When to Escalate to Human Support

### Immediate Escalation (Do Not Attempt to Answer)

#### 1. Pricing and Billing Inquiries

**Triggers:**
- "How much does it cost?"
- "Can I get a discount?"
- "I was overcharged"
- "Refund"
- "Cancel my subscription"
- "Enterprise pricing"
- "Custom plan"

**Action:** Escalate with reason `pricing_inquiry`

**Response:** "I'll connect you with our billing specialist who can access your account and provide accurate pricing information. They'll reach out within 4 hours."

#### 2. Legal and Compliance

**Triggers:**
- "Lawyer" / "Attorney"
- "Sue" / "Lawsuit"
- "Legal action"
- "GDPR" / "Data privacy request"
- "Subpoena"
- "Terms of service dispute"
- "Contract"

**Action:** Escalate with reason `legal_inquiry`

**Response:** "I'm escalating this to our legal team who can properly address your concerns. They will contact you within 24 hours."

#### 3. Security Incidents

**Triggers:**
- "Hacked" / "Hack"
- "Unauthorized access"
- "Data breach"
- "Account compromised"
- "Someone else logged in"

**Action:** Escalate with reason `security_incident` (URGENT)

**Response:** "I'm immediately escalating this to our security team. They will contact you within 1 hour. For your security, please change your password now."

#### 4. Refund Requests

**Triggers:**
- "I want a refund"
- "Chargeback"
- "Money back"
- "Double charged"
- "Cancel and refund"

**Action:** Escalate with reason `refund_request`

**Response:** "I'm connecting you with our billing team who can review your account and discuss refund options. They'll reach out within 4 hours."

### Conditional Escalation (Try to Help First, Then Escalate)

#### 5. Feature Requests

**Process:**
1. Acknowledge the request
2. Check if feature exists (search docs)
3. If doesn't exist, explain workaround if available
4. Escalate if customer insists or feature is critical

**Triggers:**
- "Can you add..."
- "I wish it could..."
- "Why doesn't it have..."

**Action:** Escalate with reason `feature_request` if no workaround exists

#### 6. Technical Bugs

**Process:**
1. Attempt to reproduce based on description
2. Search known issues
3. Provide workaround if available
4. Escalate if:
   - No workaround exists
   - Issue affects multiple users
   - Customer is on Enterprise plan

**Action:** Escalate with reason `technical_bug`

#### 7. Integration Issues

**Process:**
1. Verify integration is properly connected
2. Walk through standard troubleshooting
3. Check integration status page
4. Escalate if:
   - Integration is broken on our end
   - Third-party API issue
   - Custom integration needed

**Action:** Escalate with reason `integration_issue`

#### 8. Angry/Frustrated Customers

**Triggers:**
- Sentiment score < 0.3
- ALL CAPS messages
- Multiple exclamation marks!!!
- Profanity
- Threats to leave/cancel

**Process:**
1. Show empathy first
2. Acknowledge frustration
3. Try to resolve
4. Escalate if sentiment doesn't improve or customer requests human

**Action:** Escalate with reason `customer_frustrated`

### Human Request (Always Escalate)

#### 9. Explicit Human Request

**Triggers:**
- "I want to talk to a human"
- "Speak to a real person"
- "Agent" / "Representative"
- "This bot isn't helping"

**Action:** Escalate with reason `human_requested`

**Response:** "Absolutely! I'm connecting you with a human agent who can help. They'll reach out within [plan-specific timeframe]."

## Escalation Priority Levels

| Priority | Response Time | Examples |
|----------|---------------|----------|
| **P1 - Critical** | 1 hour | Security incidents, Enterprise down |
| **P2 - High** | 4 hours | Billing disputes, angry customers |
| **P3 - Medium** | 24 hours | Feature requests, non-urgent bugs |
| **P4 - Low** | 48 hours | General feedback, questions |

## Escalation Information Required

When escalating, always include:

1. **Customer Info:**
   - Email/phone
   - Plan type
   - Account age

2. **Context:**
   - Full conversation history
   - What was already tried
   - Customer's emotional state

3. **Classification:**
   - Escalation reason (from categories above)
   - Priority level
   - Suggested next steps

## De-escalation Techniques

Before escalating, try:

1. **Acknowledge:** "I totally understand why that's frustrating."
2. **Apologize:** "I'm sorry you're dealing with this."
3. **Action:** "Here's what I can do right now..."
4. **Timeline:** "This should be resolved by..."
5. **Follow-up:** "I'll check back with you in 2 hours."

Only escalate if these don't improve the situation.

## Non-Escalation Scenarios

**Do NOT escalate for:**

- Password reset (provide instructions)
- How-to questions (answer from docs)
- Feature explanations (provide documentation)
- Plan comparisons (direct to pricing page)
- Basic troubleshooting (walk through steps)

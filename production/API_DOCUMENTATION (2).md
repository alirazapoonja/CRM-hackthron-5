# API Documentation — Customer Success Digital FTE

## FastAPI Endpoint Reference

> Base URL: `https://support-api.yourdomain.com` (production) or `http://localhost:8000` (development)
> 
> Interactive documentation available at: `http://localhost:8000/docs` (Swagger UI)

---

## 📋 Table of Contents

- [Authentication](#authentication)
- [Health & Readiness](#health--readiness)
- [Support Form](#support-form)
- [Webhooks](#webhooks)
- [Customer Lookup](#customer-lookup)
- [Conversations](#conversations)
- [Tickets](#tickets)
- [Metrics](#metrics)
- [Events](#events)
- [Error Responses](#error-responses)
- [Rate Limiting](#rate-limiting)

---

## Authentication

Most endpoints require API key authentication via Bearer token.

```http
Authorization: Bearer your-api-key-here
```

Endpoints that do NOT require authentication:
- `GET /health`
- `GET /ready`
- `GET /live`
- `POST /support/submit` (support form is public)
- `GET /support/status/{ticket_id}` (status lookup is public)
- `POST /webhooks/gmail` (verified by Pub/Sub)
- `POST /webhooks/whatsapp` (verified by Twilio signature)

---

## Health & Readiness

### GET /health

Returns overall system health status.

**Authentication:** Not required

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-04T17:30:00.000Z",
  "version": "1.0.0",
  "services": {
    "database": true,
    "kafka": true,
    "gmail": true,
    "whatsapp": true,
    "web_form": true
  }
}
```

**Status Values:**
- `"healthy"` — All critical services operational
- `"unhealthy"` — One or more services unavailable

---

### GET /ready

Kubernetes readiness probe endpoint.

**Authentication:** Not required

**Response (200):**
```json
{ "status": "ready" }
```

**Response (503):**
```json
{ "detail": "Kafka not ready" }
```

---

### GET /live

Kubernetes liveness probe endpoint.

**Authentication:** Not required

**Response:**
```json
{ "status": "alive" }
```

---

## Support Form

### POST /support/submit

Submit a customer support request. Creates a ticket and publishes to Kafka for async processing.

**Authentication:** Not required (public endpoint)

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "subject": "Cannot access my account",
  "description": "I've been trying to log in but keep getting an error saying my credentials are invalid. I've reset my password but the issue persists.",
  "category": "account",
  "priority": "high",
  "phone": "+15551234567",
  "company": "Acme Corp",
  "order_id": "ORD-12345"
}
```

**Field Reference:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `name` | string | ✅ | 2-100 chars, letters/spaces only | Customer's full name |
| `email` | string (email) | ✅ | Valid email format | Customer's email for follow-up |
| `subject` | string | ✅ | 5-200 chars | Brief subject line |
| `description` | string | ✅ | 10-5000 chars, min 3 words | Detailed issue description |
| `category` | string | ❌ | See categories below | Ticket category (default: `general`) |
| `priority` | string | ❌ | See priorities below | Ticket priority (default: `medium`) |
| `phone` | string | ❌ | Max 20 chars | Optional phone number |
| `company` | string | ❌ | Max 100 chars | Optional company name |
| `order_id` | string | ❌ | Max 50 chars | Optional order reference |

**Category Values:** `technical`, `billing`, `account`, `feature_request`, `bug_report`, `general`, `other`

**Priority Values:** `low`, `medium`, `high`, `critical`

**Success Response (200):**
```json
{
  "success": true,
  "ticket_id": "TKT-2026-A1B2C3",
  "message": "Your support request has been submitted successfully. We'll respond to your email shortly.",
  "estimated_response_time": "1 hour"
}
```

**Response Time Estimates by Priority:**

| Priority | Estimated Response |
|----------|-------------------|
| `critical` | 30 minutes |
| `high` | 1 hour |
| `medium` | 2-4 hours |
| `low` | 24 hours |

**Error Responses:**

| Status | Description |
|--------|-------------|
| 400 | Validation error (invalid fields) |
| 422 | Request body validation failed (detailed field errors) |
| 429 | Rate limited (too many submissions from same IP) |
| 500 | Server error |

**422 Validation Error Example:**
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "value is not a valid email address"
    },
    {
      "type": "value_error",
      "loc": ["body", "description"],
      "msg": "Description must be at least 10 characters"
    }
  ]
}
```

---

### GET /support/status/{ticket_id}

Check the status of a support ticket.

**Authentication:** Not required

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `ticket_id` | string | Ticket ID (e.g., `TKT-2026-A1B2C3`) |

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | ❌ | Customer email for verification |

**Success Response (200):**
```json
{
  "ticket_id": "TKT-2026-A1B2C3",
  "status": "open",
  "category": "account",
  "priority": "high",
  "created_at": "2026-04-04T17:30:16.457Z",
  "updated_at": "2026-04-04T17:30:16.457Z",
  "subject": "Cannot access my account",
  "public_message": null
}
```

**Status Values:** `open`, `in_progress`, `resolved`, `closed`

**Error Responses:**
| Status | Description |
|--------|-------------|
| 403 | Email does not match ticket owner |
| 404 | Ticket not found |

---

### GET /support/health

Health check for the support form service.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-04T17:30:00.000Z"
}
```

---

## Webhooks

### POST /webhooks/gmail

Receive Gmail push notifications from Google Cloud Pub/Sub.

**Authentication:** Verified by Pub/Sub service identity

**Request Body:**
```json
{
  "emailAddress": "customer@example.com",
  "historyId": "12345678",
  "data": "<base64-encoded-pubsub-message>"
}
```

**Success Response (200):**
```json
{
  "success": true,
  "messages_processed": 3
}
```

**Error Responses:**
| Status | Description |
|--------|-------------|
| 503 | Gmail service not configured |
| 500 | Processing error |

---

### GET /webhooks/gmail

Gmail webhook verification endpoint (used by Google to verify ownership).

**Response:** Plain text `gmail-webhook-verified`

---

### POST /webhooks/whatsapp

Receive WhatsApp messages from Twilio.

**Authentication:** Verified by Twilio signature (`X-Twilio-Signature` header)

**Request Format:** `application/x-www-form-urlencoded`

**Form Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `From` | string | Sender's WhatsApp number (with `whatsapp:` prefix) |
| `To` | string | Recipient WhatsApp number |
| `Body` | string | Message text content |
| `MessageSid` | string | Twilio message SID |
| `ProfileName` | string | Sender's WhatsApp display name |
| `NumMedia` | string | Number of attached media files |

**Response:** Empty 200 (Twilio will retry on error)

---

### GET /webhooks/whatsapp

WhatsApp webhook verification (Meta Cloud API).

**Query Parameters:**
| Parameter | Description |
|-----------|-------------|
| `hub.mode` | Should be `subscribe` |
| `hub.verify_token` | Your verification token |
| `hub.challenge` | Challenge string to echo back |

**Response:** Echo of `hub.challenge` if verification succeeds

---

### POST /webhooks/whatsapp/status

WhatsApp message delivery status callback from Twilio.

**Form Fields:**
| Field | Description |
|-------|-------------|
| `MessageSid` | Twilio message SID |
| `MessageStatus` | Delivery status (`sent`, `delivered`, `read`, `failed`) |
| `AccountSid` | Twilio account SID |

**Response:**
```json
{ "success": true }
```

---

## Customer Lookup

### GET /customers/{customer_id}

Get customer information by ID.

**Authentication:** Required (Bearer token)

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `customer_id` | string (UUID) | Customer UUID |

**Response (200):**
```json
{
  "customer_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john@example.com",
  "phone": "+15551234567",
  "name": "John Doe",
  "created_at": "2026-01-15T10:30:00.000Z",
  "conversation_count": 12,
  "ticket_count": 8
}
```

**Error Responses:**
| Status | Description |
|--------|-------------|
| 401 | Missing or invalid API key |
| 404 | Customer not found |

---

### GET /customers/{customer_id}/history

Get customer's conversation history across all channels.

**Authentication:** Required

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `customer_id` | string (UUID) | Customer UUID |

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Max conversations (1-200) |

**Response (200):**
```json
{
  "customer_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversations": [
    {
      "id": "conv-uuid-here",
      "initial_channel": "email",
      "started_at": "2026-04-01T10:00:00Z",
      "status": "closed",
      "sentiment_score": 0.85,
      "resolution_type": "resolved"
    }
  ],
  "count": 12
}
```

---

## Conversations

### GET /conversations/{conversation_id}

Get conversation details.

**Authentication:** Required

**Response (200):**
```json
{
  "conversation_id": "conv-uuid-here",
  "customer_id": "customer-uuid-here",
  "initial_channel": "email",
  "started_at": "2026-04-01T10:00:00Z",
  "ended_at": "2026-04-01T11:30:00Z",
  "status": "closed",
  "message_count": 8,
  "ticket_id": "TKT-2026-A1B2C3"
}
```

---

### GET /conversations/{conversation_id}/messages

Get messages in a conversation.

**Authentication:** Required

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 100 | Max messages (1-500) |

**Response (200):**
```json
{
  "conversation_id": "conv-uuid-here",
  "messages": [
    {
      "id": "msg-uuid",
      "channel": "email",
      "direction": "inbound",
      "role": "customer",
      "content": "I need help with my account...",
      "created_at": "2026-04-01T10:00:00Z"
    },
    {
      "id": "msg-uuid-2",
      "channel": "email",
      "direction": "outbound",
      "role": "agent",
      "content": "I'd be happy to help...",
      "created_at": "2026-04-01T10:05:00Z"
    }
  ],
  "count": 8
}
```

---

## Tickets

### GET /tickets/{ticket_id}

Get ticket details by ID.

**Authentication:** Required

**Response (200):**
```json
{
  "ticket": {
    "id": "ticket-uuid",
    "conversation_id": "conv-uuid",
    "customer_id": "customer-uuid",
    "source_channel": "email",
    "category": "technical",
    "priority": "high",
    "status": "open",
    "created_at": "2026-04-04T17:30:00Z",
    "resolved_at": null,
    "resolution_notes": null
  }
}
```

---

### GET /tickets

List open tickets.

**Authentication:** Required

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `customer_id` | string (UUID) | Filter by customer |
| `channel` | string | Filter by channel |
| `limit` | integer | Max results (1-200, default 50) |

**Response (200):**
```json
{
  "tickets": [...],
  "count": 25
}
```

---

## Metrics

### GET /metrics/channels/{channel}

Get metrics for a specific channel.

**Authentication:** Required

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `channel` | string | `email`, `whatsapp`, or `web_form` |

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 7 | Time range in days (1-30) |

**Response (200):**
```json
{
  "channel": "email",
  "total_messages": 1250,
  "messages_inbound": 680,
  "messages_outbound": 570,
  "avg_response_time_ms": 1850,
  "resolution_rate": 0.85,
  "escalation_rate": 0.12,
  "period_start": "2026-03-28T00:00:00Z",
  "period_end": "2026-04-04T00:00:00Z"
}
```

---

### GET /metrics/summary

Get overall metrics summary across all channels.

**Authentication:** Required

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 7 | Time range in days (1-30) |

**Response (200):**
```json
{
  "period": {
    "start": "2026-03-28T00:00:00Z",
    "end": "2026-04-04T00:00:00Z"
  },
  "channels": ["email", "whatsapp", "web_form"],
  "total_tickets": 450,
  "total_messages": 2800,
  "avg_response_time_ms": 1650,
  "resolution_rate": 0.82,
  "escalation_rate": 0.15,
  "customer_satisfaction": 0.78
}
```

---

## Events

### POST /events

Publish an event to Kafka (for manual testing and integrations).

**Authentication:** Required

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_type` | string | ✅ | Event type (see below) |

**Request Body:**
```json
{
  "payload": {
    "ticket_id": "TKT-2026-A1B2C3",
    "action": "manual_escalation"
  },
  "correlation_id": "corr-123"
}
```

**Response (200):**
```json
{
  "success": true,
  "topic": "fte.events",
  "partition": 2,
  "offset": 15432
}
```

---

## Error Responses

All error responses follow a consistent format:

```json
{
  "success": false,
  "error": "Error message here",
  "status_code": 400
}
```

### Common Error Codes

| Code | Meaning | Example |
|------|---------|---------|
| 400 | Bad request | Invalid query parameters |
| 401 | Unauthorized | Missing or invalid API key |
| 403 | Forbidden | Email doesn't match ticket owner |
| 404 | Not found | Ticket/customer not found |
| 422 | Validation error | Invalid form data |
| 429 | Rate limited | Too many requests |
| 500 | Internal error | Server-side failure |
| 503 | Service unavailable | Dependency (Kafka/DB) down |

---

## Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /support/submit` | 5 requests | 1 hour per IP |
| All authenticated endpoints | 100 requests | 1 minute per API key |

**Rate Limit Headers:**
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1712246400
Retry-After: 60
```

**429 Response:**
```json
{
  "detail": "Too many submissions. Please try again in 3600 seconds."
}
```

---

## Web Support Form Integration

The project includes a complete, standalone React support form component (`production/web-form/SupportForm.jsx`).

### Embedding the Form

```html
<!-- Include in your React app -->
import SupportForm from './SupportForm';

<SupportForm 
  apiEndpoint="https://support-api.yourdomain.com"
  onSuccess={(data) => console.log('Ticket:', data.ticket_id)}
  onError={(error) => console.error('Error:', error)}
/>
```

### Features

- ✅ Real-time field validation
- ✅ Loading and submission states
- ✅ Success state with ticket ID display
- ✅ Error handling with retry
- ✅ Responsive design (mobile-friendly)
- ✅ Accessible (ARIA compliant)
- ✅ Spam prevention (honeypot field)
- ✅ Character counter for description
- ✅ Optional fields: phone, company, order ID

### Form Submission Flow

```
[User fills form] 
    → [Client-side validation]
    → [POST /support/submit]
    → [Server creates ticket + publishes to Kafka]
    → [Response with ticket_id]
    → [Success UI with ticket display]
    → [Async: Agent processes and responds]
    → [Customer receives response via email]
```

---

*For deployment instructions, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)*
*For operations runbook, see [RUNBOOK.md](./RUNBOOK.md)*

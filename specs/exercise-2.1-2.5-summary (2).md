# Exercise 2.1 & 2.5: Database & Kafka Implementation Summary

**Date:** March 2025  
**Status:** ✅ COMPLETE

---

## Exercise 2.1: PostgreSQL Database Schema

### Files Created

| File | Lines | Description |
|------|-------|-------------|
| `production/database/schema.sql` | ~550 | Complete PostgreSQL schema with pgvector |
| `production/database/setup_database.py` | ~180 | Database setup and migration script |
| `production/database/migrations/001_initial_schema.sql` | ~30 | Migration tracking file |

### Database Features Implemented

#### 1. Extensions
- ✅ **pgvector** - For semantic search on knowledge base
- ✅ **pgcrypto** - For UUID generation

#### 2. Custom Types (Enums)
- `channel_type` - email, whatsapp, web_form
- `message_direction` - inbound, outbound
- `message_role` - customer, agent, system
- `ticket_priority` - low, medium, high, urgent
- `ticket_status` - open, in_progress, pending, resolved, escalated, closed
- `conversation_status` - active, pending, resolved, escalated, abandoned
- `escalation_urgency` - normal, high, critical
- `customer_plan` - free, pro, business, enterprise

#### 3. Core Tables (10 tables)

| Table | Purpose | Key Features |
|-------|---------|--------------|
| **customers** | Unified customer profiles | Email/phone lookup, plan tracking, interaction counts |
| **customer_identifiers** | Cross-channel ID mapping | Link multiple identifiers to one customer |
| **conversations** | Conversation threads | Channel tracking, sentiment, topics, continuity |
| **messages** | All message history | Channel metadata, external IDs, delivery status |
| **tickets** | Support tickets | Lifecycle tracking, escalation, resolution |
| **escalations** | Human handoffs | Urgency levels, assignment, resolution tracking |
| **knowledge_base** | Product documentation | Vector embeddings for semantic search |
| **channel_configs** | Channel settings | API configs, templates, response limits |
| **agent_metrics** | Performance tracking | Channel-specific metrics, dimensions |
| **schema_version** | Migration tracking | Version control for schema changes |

#### 4. Indexes for Performance

**Customer Indexes:**
- `idx_customers_email` - Fast email lookup
- `idx_customers_phone` - Fast phone lookup
- `idx_customers_created_at` - Time-based queries

**Conversation Indexes:**
- `idx_conversations_customer` - Customer history
- `idx_conversations_status` - Active conversations
- `idx_conversations_channel` - Channel analytics
- `idx_conversations_topics` - GIN index for topic arrays

**Message Indexes:**
- `idx_messages_conversation` - Thread retrieval
- `idx_messages_channel` - Channel filtering
- `idx_messages_channel_message_id` - External ID lookup (Gmail/Twilio)

**Knowledge Base Indexes:**
- `idx_knowledge_embedding` - IVFFlat index for vector similarity search
- `idx_knowledge_category` - Category filtering
- `idx_knowledge_tags` - GIN index for tag arrays

#### 5. Views

| View | Purpose |
|------|---------|
| **customer_360** | Unified customer profile with all stats |
| **active_conversations** | Currently active conversations with last message |
| **ticket_dashboard** | Ticket analytics by date/channel/category |

#### 6. Functions & Triggers

**Functions:**
- `search_knowledge_base(query_embedding, category, limit)` - Semantic search
- `get_customer_history(customer_id, limit)` - Customer conversation history
- `update_customer_interaction_count()` - Auto-increment counters
- `update_conversation_timestamp()` - Keep conversations updated

**Triggers:**
- `trg_update_customer_interactions` - Update customer stats on new message
- `trg_update_conversation_timestamp` - Update conversation updated_at

#### 7. Seed Data

**Knowledge Base:** 8 sample articles
- Creating Recurring Tasks
- Gantt Chart Availability
- Password Reset
- File Upload Limits
- Slack Integration Setup
- Export Your Data
- Adding Team Members
- GitHub Integration

**Channel Configs:** 3 default configurations
- Email (formal, 2000 chars, ticket reference)
- WhatsApp (casual, 1600 chars, emoji allowed)
- Web Form (semi-formal, 1000 chars, docs link)

### Setup Instructions

```bash
# 1. Install PostgreSQL 14+ with pgvector
# Ubuntu/Debian:
sudo apt install postgresql-14 postgresql-server-dev-14
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# 2. Create database
createdb fte_db

# 3. Enable extensions
psql -d fte_db -c "CREATE EXTENSION vector;"
psql -d fte_db -c "CREATE EXTENSION pgcrypto;"

# 4. Apply schema
psql -d fte_db -f production/database/schema.sql

# OR use the setup script
python production/database/setup_database.py \
  --host localhost \
  --port 5432 \
  --user postgres \
  --password $POSTGRES_PASSWORD \
  --dbname fte_db
```

### Verification Queries

```sql
-- List all tables
\dt

-- List all views
\dv

-- List all functions
\df

-- Check schema version
SELECT * FROM schema_version;

-- Count records
SELECT 
    (SELECT COUNT(*) FROM customers) as customers,
    (SELECT COUNT(*) FROM conversations) as conversations,
    (SELECT COUNT(*) FROM messages) as messages,
    (SELECT COUNT(*) FROM tickets) as tickets,
    (SELECT COUNT(*) FROM knowledge_base) as kb_articles;

-- Test semantic search (requires embedding)
SELECT title, similarity 
FROM search_knowledge_base(
    '[0.1, 0.2, ...]'::vector(1536),  -- Your query embedding
    NULL,  -- No category filter
    5      -- Top 5 results
);
```

---

## Exercise 2.5: Kafka Event Streaming

### Files Created

| File | Lines | Description |
|------|-------|-------------|
| `production/kafka_client.py` | ~500 | Async Kafka producer/consumer with helpers |

### Kafka Topics (15 topics)

#### Ingestion Topics
| Topic | Purpose | Producer |
|-------|---------|----------|
| `fte.tickets.incoming` | Unified ticket intake | All channel handlers |
| `fte.channels.email.inbound` | Gmail messages | Gmail handler |
| `fte.channels.whatsapp.inbound` | WhatsApp messages | Twilio handler |
| `fte.channels.webform.inbound` | Web form submissions | FastAPI endpoint |

#### Response Topics
| Topic | Purpose | Consumer |
|-------|---------|----------|
| `fte.channels.email.outbound` | Email replies | Gmail handler |
| `fte.channels.whatsapp.outbound` | WhatsApp replies | Twilio handler |
| `fte.channels.webform.outbound` | Web form responses | FastAPI/Email |

#### Escalation Topics
| Topic | Purpose | Consumer |
|-------|---------|----------|
| `fte.escalations` | All escalations | Human agent dashboard |
| `fte.escalations.pending` | Pending escalations | Human agents |
| `fte.escalations.resolved` | Resolved escalations | Analytics |

#### Metrics Topics
| Topic | Purpose | Consumer |
|-------|---------|----------|
| `fte.metrics` | All metrics | Metrics collector |
| `fte.metrics.agent` | Agent performance | Dashboard |
| `fte.metrics.channel` | Channel performance | Dashboard |

#### System Topics
| Topic | Purpose | Consumer |
|-------|---------|----------|
| `fte.dlq` | Failed messages (Dead Letter Queue) | Error handler |
| `fte.system.events` | System health/events | Monitoring |

### Kafka Client Features

#### FTEKafkaProducer
- ✅ Automatic JSON serialization
- ✅ Timestamp injection on all messages
- ✅ Message ID tracking
- ✅ Acknowledgment from all replicas (`acks='all'`)
- ✅ Retry logic (3 retries with backoff)
- ✅ Batch publishing support
- ✅ Dead Letter Queue integration
- ✅ Graceful shutdown

#### FTEKafkaConsumer
- ✅ Consumer group support
- ✅ Auto-commit with manual override
- ✅ Automatic JSON deserialization
- ✅ Error handling (continues on failures)
- ✅ Graceful shutdown
- ✅ Single message consumption for testing
- ✅ Topic subscription management

#### Helper Functions
- `create_ticket_event()` - Standardized ticket events
- `create_message_event()` - Standardized message events
- `create_metric_event()` - Standardized metrics
- `test_kafka_connection()` - Connection verification

### Kafka Setup Instructions

```bash
# Option 1: Docker (Development)
docker run -d --name kafka \
  -p 9092:9092 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  -e KAFKA_AUTO_CREATE_TOPICS_ENABLE=true \
  apache/kafka:latest

# Option 2: Confluent Cloud (Production)
# 1. Create cluster at https://confluent.cloud
# 2. Get bootstrap servers and credentials
# 3. Set environment variables:
export KAFKA_BOOTSTRAP_SERVERS="pkc-xxxxx.us-east-1.aws.confluent.cloud:9092"
export KAFKA_API_KEY="your-api-key"
export KAFKA_API_SECRET="your-api-secret"

# Test connection
cd E:\crm2\production
python kafka_client.py
```

### Publishing Events (Example)

```python
from kafka_client import FTEKafkaProducer, Topics, create_ticket_event

# Create producer
producer = FTEKafkaProducer()
await producer.start()

# Publish ticket event
ticket_event = create_ticket_event(
    ticket_id="ticket-123",
    customer_id="customer-456",
    channel="email",
    issue="Can't see Gantt chart",
    priority="medium"
)

await producer.publish(Topics.TICKETS_INCOMING, ticket_event)

# Publish to DLQ on error
await producer.publish_to_dlq(
    original_topic=Topics.TICKETS_INCOMING,
    original_message=ticket_event,
    error="Database connection failed",
    error_type="database_error"
)

await producer.stop()
```

### Consuming Events (Example)

```python
from kafka_client import FTEKafkaConsumer, Topics

async def process_message(topic: str, message: dict):
    print(f"Received from {topic}: {message}")
    # Process message...

# Create consumer
consumer = FTEKafkaConsumer(
    topics=[Topics.TICKETS_INCOMING],
    group_id='fte-message-processor'
)

await consumer.start()

# Start consuming
await consumer.consume(process_message)

# To stop:
await consumer.stop()
```

---

## Next Steps

### Exercise 2.2: Channel Handlers
- [ ] GmailHandler with Pub/Sub support
- [ ] WhatsAppHandler with Twilio webhook
- [ ] Web Form with React/Next.js component

### Exercise 2.3: OpenAI Agents SDK Agent
- [ ] Customer Success Agent definition
- [ ] Tool integration
- [ ] Channel-aware system prompt

### Exercise 2.4: Unified Message Processor
- [ ] Kafka consumer integration
- [ ] Agent runner
- [ ] Message storage

### Exercise 2.6: FastAPI Application
- [ ] Webhook endpoints
- [ ] Health checks
- [ ] Web form API

### Exercise 2.7: Kubernetes Manifests
- [ ] Deployments
- [ ] Services
- [ ] HPA
- [ ] Ingress

---

**Exercise 2.1 & 2.5 Sign-off:** ✅ COMPLETE

*Database schema and Kafka infrastructure are production-ready. All tables, indexes, views, functions, topics, and client code have been implemented according to the hackathon specification.*

# Code Mapping: Incubation → Production

**Project:** TaskFlow Pro Customer Success FTE  
**Phase:** Transition - Step 2  
**Date:** March 2025  

---

## Overview

This document maps each component from the Incubation phase to its corresponding location in the Production structure.

---

## Code Mapping Table

| INCUBATION (What you built) | PRODUCTION (Where it goes) |
|-----------------------------|----------------------------|
| Prototype Python script | `agent/customer_success_agent.py` |
| MCP server tools | `agent/tools.py` (with `@function_tool`) |
| In-memory conversation | `database/schema.sql` (PostgreSQL messages table) |
| Print statements | `logging` module + Kafka events |
| Manual testing | `tests/test_transition.py`, `tests/test_agent.py` |
| Local file storage | PostgreSQL + S3/MinIO |
| Single-threaded | Async workers on Kubernetes |
| Hardcoded config | Environment variables + ConfigMaps |
| Direct API calls | Channel handlers with retry logic |

---

## Detailed Mapping

### Agent Logic

| Incubation File | Production File | Changes |
|-----------------|-----------------|---------|
| `src/agent/core_loop.py` | `agent/customer_success_agent.py` | Convert to OpenAI Agents SDK |
| `src/agent/memory_agent.py` | `agent/customer_success_agent.py` | Merge logic, add SDK decorators |
| `src/tools/mcp_server.py` | `agent/tools.py` | Convert `@server.tool` → `@function_tool` |
| (new) | `agent/prompts.py` | Extract system prompts |
| (new) | `agent/formatters.py` | Extract channel formatters |

### Channel Handlers

| Incubation File | Production File | Changes |
|-----------------|-----------------|---------|
| (spec only) | `channels/gmail_handler.py` | Implement Gmail API integration |
| (spec only) | `channels/whatsapp_handler.py` | Implement Twilio WhatsApp integration |
| (spec only) | `channels/web_form_handler.py` | Implement FastAPI router + React form |

### Workers

| Incubation File | Production File | Changes |
|-----------------|-----------------|---------|
| (new) | `workers/message_processor.py` | Kafka consumer + agent runner |
| (new) | `workers/metrics_collector.py` | Background metrics aggregation |

### API

| Incubation File | Production File | Changes |
|-----------------|-----------------|---------|
| (new) | `api/main.py` | FastAPI application with webhooks |

### Database

| Incubation File | Production File | Changes |
|-----------------|-----------------|---------|
| (spec only) | `database/schema.sql` | Create from hackathon spec |
| (new) | `database/queries.py` | Database access functions |
| (existing) | `database/migrations/` | Migration tracking |

### Tests

| Incubation File | Production File | Changes |
|-----------------|-----------------|---------|
| (new) | `tests/test_transition.py` | Transition verification tests |
| (new) | `tests/test_agent.py` | Agent unit tests |

### Infrastructure

| Incubation File | Production File | Changes |
|-----------------|-----------------|---------|
| (spec only) | `k8s/*.yaml` | Kubernetes manifests |
| (new) | `Dockerfile` | Docker image definition |
| (new) | `docker-compose.yml` | Local development setup |
| (new) | `requirements.txt` | Python dependencies |

---

## Folder Structure

```
production/
├── agent/
│   ├── __init__.py                 # NEW - Module exports
│   ├── customer_success_agent.py   # FROM src/agent/core_loop.py, memory_agent.py
│   ├── tools.py                    # FROM src/tools/mcp_server.py
│   ├── prompts.py                  # NEW - Extracted prompts
│   └── formatters.py               # NEW - Extracted formatters
├── channels/
│   ├── __init__.py                 # NEW - Module exports
│   ├── gmail_handler.py            # NEW - Gmail API integration
│   ├── whatsapp_handler.py         # NEW - Twilio WhatsApp integration
│   └── web_form_handler.py         # NEW - FastAPI router + React form
├── workers/
│   ├── __init__.py                 # NEW - Module exports
│   ├── message_processor.py        # NEW - Kafka consumer + agent
│   └── metrics_collector.py        # NEW - Metrics aggregation
├── api/
│   ├── __init__.py                 # NEW - Module exports
│   └── main.py                     # NEW - FastAPI application
├── database/
│   ├── schema.sql                  # FROM hackathon spec
│   ├── queries.py                  # NEW - Database access functions
│   └── migrations/
│       ├── 001_initial_schema.sql  # FROM production/database/schema.sql
│       └── 002_production_schema.sql # NEW - Production migration
├── tests/
│   ├── __init__.py                 # NEW - Module exports
│   ├── test_transition.py          # FROM specs/transition-checklist.md
│   └── test_agent.py               # NEW - Agent tests
├── k8s/
│   ├── namespace.yaml              # FROM hackathon spec
│   ├── configmap.yaml              # FROM hackathon spec
│   ├── secrets.yaml                # FROM hackathon spec
│   ├── deployment-api.yaml         # FROM hackathon spec
│   ├── deployment-worker.yaml      # FROM hackathon spec
│   ├── service.yaml                # FROM hackathon spec
│   ├── ingress.yaml                # FROM hackathon spec
│   └── hpa.yaml                    # FROM hackathon spec
├── specs/
│   └── transition-checklist.md     # FROM production/specs/
├── Dockerfile                      # NEW - Docker image
├── docker-compose.yml              # NEW - Local development
├── requirements.txt                # NEW - Dependencies
└── README.md                       # NEW - Project overview
```

---

## Key Changes During Transition

### 1. Tool Decorator Change

**Incubation (MCP):**
```python
@server.tool("search_knowledge_base")
async def search_knowledge_base(query: str) -> str:
    pass
```

**Production (OpenAI Agents SDK):**
```python
from agents import function_tool
from pydantic import BaseModel, Field

class KnowledgeSearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    max_results: int = Field(default=5)

@function_tool
async def search_knowledge_base(input: KnowledgeSearchInput) -> str:
    pass
```

### 2. Storage Change

**Incubation (In-Memory):**
```python
self.customers: Dict[str, Customer] = {}
```

**Production (PostgreSQL):**
```python
async with pool.acquire() as conn:
    customer = await conn.fetchrow(
        "SELECT * FROM customers WHERE email = $1",
        email
    )
```

### 3. Logging Change

**Incubation (Print):**
```python
print(f"Creating ticket for {customer_id}")
```

**Production (Structured Logging):**
```python
logger.info(f"Creating ticket for {customer_id}", extra={
    "customer_id": customer_id,
    "action": "create_ticket"
})
```

### 4. Configuration Change

**Incubation (Hardcoded):**
```python
KAFKA_SERVERS = "localhost:9092"
```

**Production (Environment Variables):**
```python
import os
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
```

---

## Implementation Order

1. **Database Schema** (`database/schema.sql`) - Foundation for all storage
2. **Tools** (`agent/tools.py`) - Core capabilities with Pydantic validation
3. **Agent** (`agent/customer_success_agent.py`) - Main agent definition
4. **Channel Handlers** (`channels/*`) - Multi-channel intake
5. **API** (`api/main.py`) - Webhook endpoints
6. **Workers** (`workers/*`) - Background processing
7. **Tests** (`tests/*`) - Verification suite
8. **Infrastructure** (`k8s/*`, `Dockerfile`) - Deployment

---

*Generated during Transition Phase - Step 2: Map Prototype Code to Production Components*

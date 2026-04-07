# Operations Runbook — Customer Success Digital FTE

## Incident Response & 24/7 Operations Guide

> This runbook provides step-by-step procedures for diagnosing and resolving common issues, monitoring system health, and maintaining 24/7 operations for the Customer Success Digital FTE.

---

## 📋 Table of Contents

- [System Overview](#system-overview)
- [Monitoring & Alerts](#monitoring--alerts)
- [Common Issues & Troubleshooting](#common-issues--troubleshooting)
- [Restart Procedures](#restart-procedures)
- [Backup & Recovery](#backup--recovery)
- [24/7 Operation Best Practices](#247-operation-best-practices)
- [Escalation Matrix](#escalation-matrix)
- [Runbook Change Log](#runbook-change-log)

---

## System Overview

### Architecture at a Glance

```
[External Channels] → [Webhooks] → [FastAPI] → [Kafka] → [Message Processor] → [AI Agent]
                                                                    ↓
[Responses] ← [Channels] ← [Kafka: outgoing] ← [Response Delivery] ← [Database: PostgreSQL]
```

### Core Components

| Component | Deployment | Replicas | Purpose |
|-----------|-----------|----------|---------|
| **fte-api** | Kubernetes Deployment | 2-20 (auto-scaled) | API gateway, webhooks, REST endpoints |
| **fte-worker** | Kubernetes Deployment | 1-10 (auto-scaled) | Kafka consumer, message processing, agent orchestration |
| **PostgreSQL** | Managed or in-cluster | 1 primary + 1 replica | CRM data, tickets, knowledge base |
| **Kafka** | Managed or Strimzi | 3 brokers | Event streaming, decoupled processing |

### Critical Data Flows

1. **Inbound**: Channel webhook → API → Kafka topic `fte.tickets.incoming`
2. **Processing**: Worker consumes → resolves customer → runs agent → stores response
3. **Outbound**: Worker publishes to `fte.tickets.outgoing` → channel handler delivers
4. **Failure**: Unprocessable messages → `fte.dlq` (dead-letter queue)

---

## Monitoring & Alerts

### Key Metrics Dashboard

Configure Grafana dashboards for these metrics:

#### API Metrics
| Metric | Query | Warning | Critical |
|--------|-------|---------|----------|
| Request rate | `rate(http_requests_total[5m])` | < 1 req/min | 0 req/min for 5min |
| Error rate | `rate(http_requests_total{status=~"5.."}[5m])` | > 1% | > 10% |
| P95 latency | `histogram_quantile(0.95, http_request_duration_seconds_bucket)` | > 1s | > 5s |
| Active connections | `http_connections` | > 500 | > 900 |

#### Worker Metrics
| Metric | Query | Warning | Critical |
|--------|-------|---------|----------|
| Messages processed/min | `rate(messages_processed_total[5m])` | < 5 | 0 for 5min |
| Processing time (avg) | `processing_time_ms_average` | > 5s | > 30s |
| Error rate | `rate(processing_errors_total[5m])` | > 5% | > 20% |
| DLQ size | `dlq_message_count` | > 100 | > 1000 |

#### Kafka Metrics
| Metric | Query | Warning | Critical |
|--------|-------|---------|----------|
| Consumer lag | `kafka_consumer_lag` | > 1000 | > 10000 |
| Throughput | `rate(kafka_messages_processed[5m])` | Degraded > 50% | Stopped |
| Broker availability | `kafka_broker_up` | Any broker down | > 1 broker down |

#### Database Metrics
| Metric | Query | Warning | Critical |
|--------|-------|---------|----------|
| Connections | `pg_stat_activity_count` | > 80% of max | > 95% of max |
| Query duration | `pg_query_duration_seconds` | > 1s | > 10s |
| Disk usage | `pg_database_size_bytes` | > 70% | > 90% |
| Replication lag | `pg_replication_lag_seconds` | > 5s | > 30s |

#### Business Metrics
| Metric | Description | Alert |
|--------|-------------|-------|
| Escalation rate | % of tickets escalated to humans | > 30% in 1 hour |
| Resolution rate | % of tickets resolved automatically | < 60% in 1 hour |
| Ticket backlog | Open tickets not yet processed | > 500 |
| Response accuracy | Agent response quality score | < 80% |

### Alert Routing

```yaml
# AlertManager configuration example
route:
  receiver: 'slack-critical'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
      repeat_interval: 5m
    - match:
        severity: warning
      receiver: 'slack-warnings'
      repeat_interval: 1h

receivers:
  - name: 'slack-critical'
    slack_configs:
      - channel: '#fte-critical-alerts'
        text: '🚨 {{ .CommonAnnotations.summary }}'
  - name: 'slack-warnings'
    slack_configs:
      - channel: '#fte-warnings'
        text: '⚠️ {{ .CommonAnnotations.summary }}'
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
```

---

## Common Issues & Troubleshooting

### 1. Kafka Consumer Lag

**Symptom**: Messages piling up in `fte.tickets.incoming`, customers not getting responses.

**Detection**:
```bash
# Check consumer lag
kubectl exec -it fte-worker-xxxxx -n customer-success-fte -- \
  kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group fte-processor
```

**Root Causes & Fixes**:

| Cause | Fix |
|-------|-----|
| Worker pods crashed | `kubectl get pods -n customer-success-fte -l component=worker` — check `RESTARTS` |
| Kafka broker unreachable | Check Kafka pod health: `kubectl get pods -n kafka` |
| Processing too slow | Scale workers: `kubectl scale deployment fte-worker --replicas=5` |
| Message format changed | Check DLQ: malformed messages may be blocking partition |
| Network partition | Check pod-to-Kafka connectivity: `kubectl exec -it fte-worker -- nc -zv kafka 9092` |

**Resolution Steps**:
```bash
# Step 1: Check worker health
kubectl logs -l component=worker -n customer-success-fte --tail=100

# Step 2: Scale workers if healthy but slow
kubectl scale deployment fte-worker --replicas=5 -n customer-success-fte

# Step 3: Check for stuck messages in DLQ
kubectl exec -it fte-worker -- python -c "
from aiokafka import AIOKafkaConsumer
import asyncio
async def check():
    c = AIOKafkaConsumer('fte.dlq', bootstrap_servers='kafka:9092')
    await c.start()
    print(f'DLQ size: {len(await c.partitions_for_topic(\"fte.dlq\"))}')
    await c.stop()
asyncio.run(check())
"

# Step 4: Monitor lag reduction
watch -n 5 'kubectl top pods -n customer-success-fte -l component=worker'
```

### 2. Database Connection Issues

**Symptom**: API returns 500 errors, workers fail to store messages.

**Detection**:
```bash
# Check database connectivity
kubectl exec -it fte-api-xxxxx -n customer-success-fte -- \
  python -c "
import asyncpg, asyncio
async def test():
    try:
        conn = await asyncpg.connect('postgresql://postgres:PASSWORD@HOST:5432/crm_fte')
        await conn.fetchval('SELECT 1')
        print('Database connection OK')
        await conn.close()
    except Exception as e:
        print(f'Database connection FAILED: {e}')
asyncio.run(test())
"
```

**Root Causes & Fixes**:

| Cause | Fix |
|-------|-----|
| Max connections reached | Increase pool size or add PgBouncer |
| Database pod crashed | `kubectl describe pod postgres -n postgres` |
| Wrong credentials | Verify secret: `kubectl get secret fte-secrets -o jsonpath='{.data.db-password}' \| base64 -d` |
| Network policy blocking | Check NetworkPolicy: `kubectl get networkpolicy -n customer-success-fte` |

**Resolution Steps**:
```bash
# Step 1: Check PostgreSQL health
kubectl exec -it fte-postgres -n postgres -- pg_isready

# Step 2: Check connection count
kubectl exec -it fte-postgres -n postgres -- \
  psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Step 3: Kill idle connections if over limit
kubectl exec -it fte-postgres -n postgres -- \
  psql -U postgres -c "
    SELECT pg_terminate_backend(pid) 
    FROM pg_stat_activity 
    WHERE state = 'idle' AND query_start < NOW() - INTERVAL '30 minutes';
  "

# Step 4: Restart API pods to reset connection pool
kubectl rollout restart deployment/fte-api -n customer-success-fte
```

### 3. Webhook Failures (Gmail/Twilio)

**Symptom**: Incoming emails or WhatsApp messages not being processed.

#### Gmail Webhook

**Detection**:
```bash
# Check Gmail handler logs
kubectl logs -l component=api -n customer-success-fte --tail=50 | grep -i gmail

# Test Gmail connectivity
kubectl exec -it fte-api-xxxxx -n customer-success-fte -- \
  python -c "
from googleapiclient.discovery import build
# Test with service account credentials
"
```

**Common Issues**:

| Issue | Fix |
|-------|-----|
| Credentials expired | Rotate service account key, update secret |
| Pub/Sub topic deleted | Recreate: `gcloud pubsub topics create gmail-notifications` |
| Gmail watch expired | Restart watch: call `gmail.users().watch()` |
| API quota exceeded | Check Google Cloud Console → APIs & Services → Quotas |

#### WhatsApp/Twilio Webhook

**Detection**:
```bash
# Check Twilio webhook logs
kubectl logs -l component=api -n customer-success-fte --tail=50 | grep -i whatsapp

# Check Twilio webhook status in Twilio Console
# https://console.twilio.com/us1/develop/sms/services?frameUrl=/console/sms/services
```

**Common Issues**:

| Issue | Fix |
|-------|-----|
| Twilio credentials expired | Update `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` in secrets |
| Webhook URL changed | Update Twilio webhook URL to match your ingress |
| Twilio sandbox expired | Rejoin sandbox: send `join <sandbox-code>` to +14155238886 |
| Signature validation failing | Verify `X-Twilio-Signature` header is being passed through ingress |

### 4. Agent Not Escalating

**Symptom**: Complex issues not being escalated to human agents.

**Detection**:
```bash
# Check escalation metrics
kubectl exec -it fte-worker -- python -c "
# Query agent_metrics table for escalation counts
"

# Check escalation topic
kubectl exec -it fte-worker -- \
  kafka-topics --bootstrap-server localhost:9092 \
  --describe --topic fte.tickets.escalated
```

**Root Causes & Fixes**:

| Cause | Fix |
|-------|-----|
| Escalation triggers too strict | Adjust thresholds in `prompts.py` |
| OpenAI API unavailable | Check `OPENAI_API_KEY` validity, check OpenAI status page |
| Agent stuck in loop | Check worker logs for repeated tool calls |
| Sentiment analysis disabled | Verify `FEATURE_SENTIMENT_ANALYSIS` config |

**Resolution**:
```bash
# Step 1: Verify OpenAI connectivity
kubectl exec -it fte-api -n customer-success-fte -- \
  python -c "
import openai
openai.api_key = 'YOUR_KEY'
response = openai.chat.completions.create(
    model='gpt-4o',
    messages=[{'role': 'user', 'content': 'Hello'}]
)
print('OpenAI API: OK')
"

# Step 2: Manually escalate a stuck ticket
kubectl exec -it fte-worker -n customer-success-fte -- \
  python -c "
from production.agent.tools import escalate_to_human_tool
import asyncio
result = asyncio.run(escalate_to_human_tool(
    ticket_id='TICKET_UUID',
    reason='Manual escalation: agent not responding'
))
print(result)
"
```

### 5. High Latency

**Symptom**: Responses taking > 10 seconds, customer complaints.

**Detection**:
```bash
# Check API response times
kubectl top pods -n customer-success-fte

# Check for resource contention
kubectl describe node $(kubectl get pods -n customer-success-fte -o wide --no-headers | awk '{print $8}' | head -1)
```

**Root Causes & Fixes**:

| Cause | Fix |
|-------|-----|
| OpenAI API slow | Check OpenAI status (status.openai.com), consider switching model |
| Database slow queries | Add missing indexes, check `pg_stat_statements` |
| Memory pressure | Increase pod memory limits, check for memory leaks |
| Kafka lag causing backpressure | Scale workers (see Issue #1) |

**Resolution**:
```bash
# Step 1: Identify bottleneck
kubectl exec -it fte-api -n customer-success-fte -- \
  python -c "
import time, aiohttp, asyncpg
import asyncio

async def benchmark():
    # DB query time
    start = time.time()
    conn = await asyncpg.connect('postgresql://...')
    await conn.fetchval('SELECT 1')
    print(f'DB query: {(time.time()-start)*1000:.0f}ms')
    
    # Agent time (if OpenAI available)
    # ... test OpenAI call
    
asyncio.run(benchmark())
"

# Step 2: Scale up if needed
kubectl scale deployment fte-api --replicas=5 -n customer-success-fte

# Step 3: Check if HPA is triggering
kubectl get hpa -n customer-success-fte
```

---

## Restart Procedures

### Restart Single Component

```bash
# Restart API (rolling update, zero downtime)
kubectl rollout restart deployment/fte-api -n customer-success-fte
kubectl rollout status deployment/fte-api -n customer-success-fte --timeout=120s

# Restart Worker (graceful shutdown)
kubectl rollout restart deployment/fte-worker -n customer-success-fte
kubectl rollout status deployment/fte-worker -n customer-success-fte --timeout=120s
```

### Full System Restart

```bash
# Step 1: Delete all pods (deployments will recreate them)
kubectl delete pods --all -n customer-success-fte

# Step 2: Wait for all pods to be ready
kubectl wait --for=condition=Ready pods --all -n customer-success-fte --timeout=120s

# Step 3: Verify health
curl http://localhost:8000/health  # After port-forward
```

### Emergency: Delete and Recreate Everything

```bash
# WARNING: This will cause downtime
kubectl delete -f production/k8s/deployment-api.yaml
kubectl delete -f production/k8s/deployment-worker.yaml

# Wait for termination
kubectl wait --for=delete pods --all -n customer-success-fte --timeout=60s

# Recreate
kubectl apply -f production/k8s/deployment-api.yaml
kubectl apply -f production/k8s/deployment-worker.yaml

# Verify
kubectl wait --for=condition=Ready pods --all -n customer-success-fte --timeout=120s
```

---

## Backup & Recovery

### Database Backup

```bash
# One-time backup
kubectl exec -it fte-postgres -n postgres -- \
  pg_dump -U postgres crm_fte > /tmp/crm_fte_backup_$(date +%Y%m%d_%H%M%S).sql

# Copy to local machine
kubectl cp postgres:/tmp/crm_fte_backup.sql ./crm_fte_backup.sql

# Restore from backup
cat crm_fte_backup.sql | kubectl exec -i fte-postgres -n postgres -- \
  psql -U postgres -d crm_fte
```

### Automated Backup (CronJob)

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: customer-success-fte
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: pg-dump
              image: postgres:16
              command:
                - sh
                - -c
                - |
                  pg_dump -U postgres -h $DB_HOST crm_fte | \
                  gzip > /backups/crm_fte_$(date +%Y%m%d).sql.gz
              env:
                - name: DB_HOST
                  value: "postgres.postgres.svc.cluster.local"
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: fte-secrets
                      key: db-password
              volumeMounts:
                - name: backup-storage
                  mountPath: /backups
          volumes:
            - name: backup-storage
              persistentVolumeClaim:
                claimName: backup-pvc
          restartPolicy: OnFailure
```

### Knowledge Base Backup

```bash
# Export knowledge base entries
kubectl exec -it fte-postgres -n postgres -- \
  psql -U postgres -d crm_fte -c \
  "COPY (SELECT title, content, category FROM knowledge_base) TO STDOUT WITH CSV HEADER" \
  > knowledge_base_export.csv
```

### Disaster Recovery Checklist

- [ ] Verify PostgreSQL backups exist and are recent (< 24 hours old)
- [ ] Verify Kafka topic configurations are documented
- [ ] Store all Kubernetes manifests in version control (Git)
- [ ] Store all secrets in external secret manager (not in-cluster only)
- [ ] Test restore procedure monthly
- [ ] Document external service dependencies and their recovery procedures

---

## 24/7 Operation Best Practices

### Shift Handover Checklist

**Incoming Engineer:**
- [ ] Check Grafana dashboards for anomalies
- [ ] Review alerts from previous shift
- [ ] Verify all pods are running: `kubectl get pods -n customer-success-fte`
- [ ] Check Kafka consumer lag: `kubectl exec ... kafka-consumer-groups`
- [ ] Verify database health: `kubectl exec ... pg_isready`
- [ ] Review DLQ size and process any stuck messages
- [ ] Check escalation queue and handoff to on-call human agents

### Daily Checks

| Check | Command | Expected |
|-------|---------|----------|
| Pod health | `kubectl get pods -n customer-success-fte` | All `Running` |
| API health | `curl /health` | `"status": "healthy"` |
| Kafka lag | Consumer group describe | < 100 messages |
| DB connections | `SELECT count(*) FROM pg_stat_activity` | < 80% of max |
| Disk usage | `kubectl top nodes` | < 70% |
| Error rate | Grafana dashboard | < 1% |

### Weekly Maintenance

- [ ] Review and rotate logs if needed
- [ ] Check for Kubernetes security patches
- [ ] Review and optimize slow database queries
- [ ] Audit escalation reasons for pattern identification
- [ ] Update knowledge base with newly resolved issues
- [ ] Review and adjust HPA thresholds based on traffic patterns

### Monthly Maintenance

- [ ] Test backup restoration procedure
- [ ] Review and update alerting thresholds
- [ ] Run load test to validate capacity
- [ ] Audit API key usage and rotate if needed
- [ ] Review cost analysis (cloud resources)
- [ ] Update container images (security patches)

---

## Escalation Matrix

| Severity | Response Time | Who | Examples |
|----------|--------------|-----|----------|
| **P1 - System Down** | 5 minutes | On-call engineer + PagerDuty | All pods crashed, database unreachable |
| **P2 - Degraded** | 15 minutes | On-call engineer | High error rate, Kafka lag growing |
| **P3 - Partial Impact** | 1 hour | Support team | Single channel down, elevated latency |
| **P4 - Informational** | Next business day | Development team | Minor UI issues, documentation updates |

### On-Call Contact

| Role | Contact | Method |
|------|---------|--------|
| Primary On-Call | Slack: `#fte-oncall` | PagerDuty |
| Database Admin | DBA team | Email + Slack |
| Platform Team | `#platform-team` | Slack |
| AI/ML Team | `#ml-team` | Slack |

---

## Runbook Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | FTE Team | Initial runbook creation |
| — | — | — |

---

*For deployment instructions, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)*
*For API reference, see [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)*

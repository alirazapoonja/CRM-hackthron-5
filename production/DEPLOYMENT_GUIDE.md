# Deployment Guide — Customer Success Digital FTE

## Production-Grade Kubernetes Deployment Instructions

> This guide covers deploying the Customer Success Digital FTE to a Kubernetes cluster, including prerequisites, secrets management, Docker builds, and post-deployment verification.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Docker Image Build](#docker-image-build)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Environment Configuration](#environment-configuration)
- [Post-Deployment Verification](#post-deployment-verification)
- [Scaling & Auto-Scaling](#scaling--auto-scaling)
- [Monitoring](#monitoring)
- [Rollback Procedures](#rollback-procedures)
- [CI/CD Pipeline (Recommended)](#cicd-pipeline-recommended)

---

## Prerequisites

### Infrastructure

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Kubernetes Cluster** | 1.25+ | 1.28+ |
| **Nodes** | 3 (4 CPU, 8GB RAM each) | 3 (8 CPU, 16GB RAM each) |
| **Storage** | 50 GB | 100 GB SSD |
| **Ingress Controller** | NGINX Ingress | NGINX + cert-manager |
| **Container Registry** | Any (Docker Hub, ACR, GCR, ECR) | Private registry |

### Required Software

```bash
kubectl --version          # >= 1.28
helm version               # >= 3.12
docker --version           # >= 24.0
```

### Required Services (External Dependencies)

| Service | Purpose | Notes |
|---------|---------|-------|
| **PostgreSQL 16+** | CRM database | Can be external (Cloud SQL, RDS) or in-cluster |
| **Apache Kafka** | Message broker | Can be Confluent, Strimzi, or self-hosted |
| **OpenAI API Key** | Agent responses | Required for AI response generation |
| **Gmail API** (optional) | Email channel | Google Cloud project + service account |
| **Twilio** (optional) | WhatsApp channel | Twilio account + WhatsApp sandbox |

---

## Docker Image Build

### Build API Image

```bash
# From project root (E:\crm2)
docker build -f production/Dockerfile \
  --target api \
  -t customer-success-fte-api:v1.0.0 \
  .
```

### Build Worker Image

```bash
docker build -f production/Dockerfile \
  --target worker \
  -t customer-success-fte-worker:v1.0.0 \
  .
```

### Tag and Push to Registry

```bash
# Replace with your registry URL
REGISTRY=company-registry.azurecr.io

docker tag customer-success-fte-api:v1.0.0 $REGISTRY/fte-api:v1.0.0
docker tag customer-success-fte-worker:v1.0.0 $REGISTRY/fte-worker:v1.0.0

docker push $REGISTRY/fte-api:v1.0.0
docker push $REGISTRY/fte-worker:v1.0.0
```

### Multi-Platform Build (for production)

```bash
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 \
  -f production/Dockerfile --target api \
  -t $REGISTRY/fte-api:v1.0.0 \
  --push .
```

---

## Kubernetes Deployment

### Step 1: Create Namespace

```bash
kubectl apply -f production/k8s/namespace.yaml
```

Verify:
```bash
kubectl get namespace customer-success-fte
```

### Step 2: Create ConfigMap

Review and update `production/k8s/configmap.yaml` with your environment values, then:

```bash
kubectl apply -f production/k8s/configmap.yaml
```

Verify:
```bash
kubectl describe configmap fte-config -n customer-success-fte
```

### Step 3: Create Secrets

**⚠️ IMPORTANT:** Never store secrets in YAML files. Use one of these methods:

#### Option A: kubectl (Quick Setup)
```bash
kubectl create secret generic fte-secrets \
  --namespace customer-success-fte \
  --from-literal=db-password='YOUR_DB_PASSWORD' \
  --from-literal=api-key='YOUR_API_KEY' \
  --from-literal=openai-api-key='sk-YOUR_OPENAI_KEY' \
  --from-literal=twilio-account-sid='ACxxxxx' \
  --from-literal=twilio-auth-token='YOUR_TWILIO_TOKEN' \
  --from-literal=gmail-credentials-json='$(cat path/to/gmail-credentials.json)'
```

#### Option B: External Secrets Manager (Recommended for Production)
```bash
# HashiCorp Vault
helm install vault hashicorp/vault
# Then configure ExternalSecrets operator

# Azure Key Vault
# Use Azure Key Vault Provider for Secrets Store CSI Driver
```

#### Option C: Sealed Secrets (GitOps Friendly)
```bash
# Install kubeseal
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Seal your secrets
kubectl create secret generic fte-secrets --from-literal=db-password='xxx' --dry-run=client -o yaml | kubeseal > sealed-secrets.yaml
kubectl apply -f sealed-secrets.yaml
```

### Step 4: Deploy API

Update the image reference in `production/k8s/deployment-api.yaml`:
```yaml
spec:
  template:
    spec:
      containers:
        - name: api
          image: YOUR_REGISTRY/fte-api:v1.0.0  # Update this line
```

Then apply:
```bash
kubectl apply -f production/k8s/deployment-api.yaml
```

### Step 5: Deploy Worker

Update the image reference in `production/k8s/deployment-worker.yaml`:
```yaml
spec:
  template:
    spec:
      containers:
        - name: worker
          image: YOUR_REGISTRY/fte-worker:v1.0.0  # Update this line
```

Then apply:
```bash
kubectl apply -f production/k8s/deployment-worker.yaml
```

### Step 6: Deploy Services

```bash
kubectl apply -f production/k8s/service.yaml
```

### Step 7: Deploy Ingress

First, ensure you have TLS certificates (via cert-manager or manual):

```bash
# If using cert-manager:
kubectl apply -f production/k8s/ingress.yaml
```

Update the hostnames in `production/k8s/ingress.yaml` to match your domain:
```yaml
rules:
  - host: support-api.yourdomain.com    # Update this
  - host: webhooks.yourdomain.com       # Update this
```

### Step 8: Deploy HPA

```bash
kubectl apply -f production/k8s/hpa.yaml
```

Verify:
```bash
kubectl get hpa -n customer-success-fte
```

### Quick Deploy All

```bash
# Apply all manifests in order
kubectl apply -f production/k8s/namespace.yaml
kubectl apply -f production/k8s/configmap.yaml
kubectl apply -f production/k8s/secrets.yaml  # Only if using inline secrets
kubectl apply -f production/k8s/deployment-api.yaml
kubectl apply -f production/k8s/deployment-worker.yaml
kubectl apply -f production/k8s/service.yaml
kubectl apply -f production/k8s/ingress.yaml
kubectl apply -f production/k8s/hpa.yaml
```

---

## Environment Configuration

### Required ConfigMap Values

| Key | Description | Example |
|-----|-------------|---------|
| `DB_HOST` | PostgreSQL hostname | `postgres-fte.postgres.svc.cluster.local` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `crm_fte` |
| `DB_USER` | Database user | `postgres` |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka brokers | `kafka-headless.kafka.svc:9092` |
| `AGENT_MODEL` | OpenAI model | `gpt-4o` |
| `API_PORT` | API port | `8000` |
| `ALLOWED_ORIGINS` | CORS origins | `https://app.yourdomain.com` |

### Required Secrets

| Secret Key | Description | Source |
|------------|-------------|--------|
| `DB_PASSWORD` | PostgreSQL password | Your database |
| `API_KEY` | API authentication key | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `OPENAI_API_KEY` | OpenAI API key | https://platform.openai.com/api-keys |
| `TWILIO_ACCOUNT_SID` | Twilio account ID | https://console.twilio.com/ |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | https://console.twilio.com/ |

### Optional Secrets

| Secret Key | Description | When Needed |
|------------|-------------|-------------|
| `GMAIL_CREDENTIALS_JSON` | Gmail service account JSON | Using Gmail webhook |
| `WHATSAPP_VERIFY_TOKEN` | WhatsApp verification token | Using WhatsApp Cloud API |

---

## Post-Deployment Verification

### 1. Check All Pods Are Running

```bash
kubectl get pods -n customer-success-fte
```

Expected output:
```
NAME                          READY   STATUS    RESTARTS   AGE
fte-api-5d4b7c8f9-x2k4m      1/1     Running   0          2m
fte-api-5d4b7c8f9-j8n3p      1/1     Running   0          2m
fte-worker-7f8a9b6c5-m4k2l   1/1     Running   0          2m
fte-worker-7f8a9b6c5-q7w8e   1/1     Running   0          2m
```

### 2. Check Health Endpoint

```bash
kubectl port-forward svc/fte-api 8000:80 -n customer-success-fte &
curl http://localhost:8000/health | jq
```

Expected:
```json
{
  "status": "healthy",
  "services": {
    "database": true,
    "kafka": true,
    "gmail": true,
    "whatsapp": true,
    "web_form": true
  }
}
```

### 3. Test Form Submission

```bash
curl -X POST http://localhost:8000/support/submit \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "subject": "Deployment Test",
    "description": "Testing deployment of Customer Success FTE.",
    "category": "general",
    "priority": "low"
  }'
```

Expected:
```json
{
  "success": true,
  "ticket_id": "TKT-2026-XXXXXX",
  "message": "Your support request has been submitted successfully.",
  "estimated_response_time": "24 hours"
}
```

### 4. Verify Auto-Scaling

```bash
kubectl describe hpa fte-api-hpa -n customer-success-fte
kubectl describe hpa fte-worker-hpa -n customer-success-fte
```

### 5. Check Ingress

```bash
kubectl get ingress -n customer-success-fte
```

Test external access:
```bash
curl https://support-api.yourdomain.com/health
```

---

## Scaling & Auto-Scaling

### HPA Configuration Summary

| Deployment | Min Replicas | Max Replicas | Scale-Up Trigger | Scale-Down Trigger |
|------------|-------------|-------------|-----------------|-------------------|
| **fte-api** | 2 | 20 | CPU > 70%, Memory > 80%, RPS > 100 | CPU < 30%, Memory < 50% |
| **fte-worker** | 1 | 10 | Kafka lag > 1000 msgs, CPU > 70% | Kafka lag < 100, CPU < 30% |

### Manual Scaling

```bash
# Scale API to 5 replicas
kubectl scale deployment fte-api --replicas=5 -n customer-success-fte

# Scale workers to 3 replicas
kubectl scale deployment fte-worker --replicas=3 -n customer-success-fte
```

### Scaling Recommendations

| Scenario | Action |
|----------|--------|
| High traffic expected | Pre-scale: `kubectl scale deployment fte-api --replicas=5` |
| Kafka backlog growing | Increase workers: `kubectl scale deployment fte-worker --replicas=5` |
| Cost optimization | Reduce min replicas: edit HPA, `minReplicas: 1` |
| Database under load | Connection pooler (PgBouncer) + increase `DB_POOL_MAX_SIZE` |

---

## Monitoring

### Essential Metrics to Track

| Metric | Source | Alert Threshold |
|--------|--------|----------------|
| API response time (p95) | Prometheus | > 1 second |
| Error rate | Prometheus | > 5% |
| Kafka consumer lag | Kafka Lag Exporter | > 5000 messages |
| Pod restarts | Kubernetes | > 3 in 1 hour |
| Database connections | PostgreSQL exporter | > 80% of max |
| OpenAI token usage | Agent metrics | > budget threshold |
| Escalation rate | Agent metrics | > 30% |

### Recommended Stack

```
Prometheus (metrics collection)
    ↓
Grafana (dashboards)
    ↓
AlertManager (notifications → Slack, PagerDuty, Email)
```

### Key Grafana Dashboards

1. **API Overview** — Requests/sec, latency, error rate
2. **Worker Performance** — Messages processed, processing time, DLQ size
3. **Kafka Health** — Consumer lag, throughput, partition balance
4. **Database Health** — Connections, query time, cache hit ratio
5. **Business Metrics** — Tickets created, resolution rate, escalation rate

---

## Rollback Procedures

### Rollback Last Deployment

```bash
# Check rollout history
kubectl rollout history deployment/fte-api -n customer-success-fte

# Rollback to previous version
kubectl rollout undo deployment/fte-api -n customer-success-fte

# Rollback to specific revision
kubectl rollout undo deployment/fte-api -n customer-success-fte --to-revision=2
```

### Verify Rollback

```bash
kubectl rollout status deployment/fte-api -n customer-success-fte --timeout=120s
kubectl get pods -n customer-success-fte -l component=api
```

### Emergency Rollback (All Components)

```bash
# Save current state
kubectl get all -n customer-success-fte -o yaml > current-state-backup.yaml

# Rollback both deployments
kubectl rollout undo deployment/fte-api -n customer-success-fte
kubectl rollout undo deployment/fte-worker -n customer-success-fte
```

---

## CI/CD Pipeline (Recommended)

### GitHub Actions Example

```yaml
name: Deploy FTE
on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build and push API image
        run: |
          docker build -f production/Dockerfile --target api \
            -t $REGISTRY/fte-api:${{ github.sha }} .
          docker push $REGISTRY/fte-api:${{ github.sha }}
      
      - name: Build and push worker image
        run: |
          docker build -f production/Dockerfile --target worker \
            -t $REGISTRY/fte-worker:${{ github.sha }} .
          docker push $REGISTRY/fte-worker:${{ github.sha }}
      
      - name: Update Kubernetes manifests
        run: |
          sed -i "s|image:.*api:.*|image: $REGISTRY/fte-api:${{ github.sha }}|g" \
            production/k8s/deployment-api.yaml
          sed -i "s|image:.*worker:.*|image: $REGISTRY/fte-worker:${{ github.sha }}|g" \
            production/k8s/deployment-worker.yaml
      
      - name: Deploy to Kubernetes
        uses: azure/k8s-deploy@v4
        with:
          manifests: |
            production/k8s/configmap.yaml
            production/k8s/deployment-api.yaml
            production/k8s/deployment-worker.yaml
            production/k8s/service.yaml
          namespace: customer-success-fte
```

---

*For operations and incident response, see [RUNBOOK.md](./RUNBOOK.md)*

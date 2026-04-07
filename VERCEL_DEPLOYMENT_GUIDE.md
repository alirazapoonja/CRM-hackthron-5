# Vercel Deployment Guide — Customer Success Digital FTE

## Quick Deployment to Vercel

> This guide covers deploying the Customer Success Digital FTE to Vercel's serverless platform for easy, scalable hosting.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [One-Click Deploy](#one-click-deploy)
- [Manual Deployment via CLI](#manual-deployment-via-cli)
- [Deployment via Vercel Dashboard](#deployment-via-vercel-dashboard)
- [Environment Variables Configuration](#environment-variables-configuration)
- [Post-Deployment Setup](#post-deployment-setup)
- [Limitations & Considerations](#limitations--considerations)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Accounts

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Account**: Your code is already at `https://github.com/alirazapoonja/CRM-hackthron-5.git`
3. **External Services** (depending on features needed):
   - PostgreSQL database (Supabase, Neon, AWS RDS, etc.)
   - OpenAI API key (for AI agent features)
   - Gmail API credentials (optional)
   - Twilio WhatsApp credentials (optional)

### Local Setup (Optional)

```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login
```

---

## One-Click Deploy

### Deploy Directly from GitHub

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your repository: `alirazapoonja/CRM-hackthron-5`
3. Vercel will auto-detect the `vercel.json` configuration
4. Configure environment variables (see below)
5. Click **Deploy**

---

## Manual Deployment via CLI

### Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

### Step 2: Login to Vercel

```bash
vercel login
```

### Step 3: Deploy to Vercel

```bash
# Navigate to project root
cd "E:\crm2\CRM hackthron 5"

# Deploy (first time)
vercel

# Deploy to production
vercel --prod
```

### Step 4: Configure Environment Variables

```bash
# Set required environment variables
vercel env add DB_HOST
vercel env add DB_PORT
vercel env add DB_USER
vercel env add DB_PASSWORD
vercel env add DB_NAME
vercel env add OPENAI_API_KEY
vercel env add API_KEY
# ... add other variables as needed
```

---

## Deployment via Vercel Dashboard

### Step 1: Import Project

1. Go to [vercel.com/dashboard](https://vercel.com/dashboard)
2. Click **Add New...** → **Project**
3. Import from GitHub: `alirazapoonja/CRM-hackthron-5`
4. Click **Import**

### Step 2: Configure Build Settings

Vercel will auto-detect settings from `vercel.json`. Verify:

| Setting | Value |
|---------|-------|
| **Framework** | Other |
| **Build Command** | None (serverless) |
| **Output Directory** | api |
| **Install Command** | `pip install -r production/requirements.txt` |
| **Development Command** | `python -m uvicorn production.api.main:app --reload` |

### Step 3: Add Environment Variables

Add these in **Settings** → **Environment Variables**:

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL host | `db.example.supabase.co` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `your-password` |
| `DB_NAME` | Database name | `crm_fte` |
| `API_KEY` | API authentication key | `your-secret-api-key` |

#### Optional Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `AGENT_MODEL` | GPT model to use | `gpt-4o` |
| `GMAIL_CREDENTIALS_PATH` | Gmail credentials path | (leave empty for now) |
| `TWILIO_ACCOUNT_SID` | Twilio account SID | `AC...` |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | `your-token` |
| `ALLOWED_ORIGINS` | CORS allowed origins | `https://yourdomain.com` |

### Step 4: Deploy

Click **Deploy** and wait for the build to complete (~2-3 minutes).

---

## Environment Variables Configuration

### Using `.env` File Locally

Create a `.env` file in the project root:

```env
# Database (REQUIRED)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=crm_fte

# API Security (REQUIRED)
API_KEY=your-secret-api-key-here

# OpenAI (Optional - for AI features)
OPENAI_API_KEY=sk-your-openai-key

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080

# Gmail (Optional)
GMAIL_CREDENTIALS_PATH=
GMAIL_PROJECT_ID=

# WhatsApp (Optional)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

### Upload `.env` to Vercel

```bash
# Install dotenv-cli
npm install -g dotenv-cli

# Upload all env vars to Vercel
vercel env pull .env
```

---

## Post-Deployment Setup

### 1. Initialize Database

After deployment, you need to create the database schema:

```bash
# Get your deployed URL
DEPLOYED_URL="https://your-app.vercel.app"

# Call the init endpoint
curl -X POST "$DEPLOYED_URL/api/admin/init-db"
```

Or run the SQL schema directly on your PostgreSQL database:

```bash
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f production/database/schema.sql
```

### 2. Test the Deployment

```bash
# Health check
curl https://your-app.vercel.app/health

# API documentation
open https://your-app.vercel.app/api/docs

# Test with API key
curl -H "Authorization: Bearer your-api-key" \
     https://your-app.vercel.app/customers/test-id
```

### 3. Configure Webhooks (if using Gmail/WhatsApp)

Update your webhook URLs to point to your Vercel deployment:

| Service | Webhook URL |
|---------|-------------|
| **Gmail** | `https://your-app.vercel.app/webhooks/gmail` |
| **WhatsApp** | `https://your-app.vercel.app/webhooks/whatsapp` |

---

## Limitations & Considerations

### Vercel Serverless Limitations

| Feature | Limitation | Workaround |
|---------|------------|------------|
| **Execution Time** | Max 10-60 seconds | Use for API calls, not long-running tasks |
| **Cold Starts** | 1-5 seconds on first request | Use Vercel's "Always On" feature (Pro plan) |
| **WebSockets** | Not supported | Use HTTP polling or upgrade to dedicated server |
| **Background Tasks** | Not supported | Use external services (Kafka, Redis, etc.) |
| **File System** | Read-only (except `/tmp`) | Store files in cloud storage (S3, etc.) |

### Architecture Notes

**What Works on Vercel:**
- ✅ REST API endpoints
- ✅ Webhook receivers (Gmail, WhatsApp, Web Form)
- ✅ Database queries (PostgreSQL)
- ✅ OpenAI agent integration
- ✅ CORS and authentication

**What Doesn't Work on Vercel:**
- ❌ Kafka message processing (use external Kafka service)
- ❌ Background workers
- ❌ Long-running processes
- ❌ Real-time WebSocket connections

### Recommended Architecture for Production

```
┌─────────────────┐
│   Vercel API    │ ← Handles HTTP requests
│  (Serverless)   │
└────────┬────────┘
         │
         ├─→ PostgreSQL (Supabase/Neon/RDS)
         ├─→ OpenAI API (for agent)
         ├─→ Gmail API (via Pub/Sub webhooks)
         └─→ Twilio WhatsApp (via webhooks)
```

For full Kafka integration, consider:
- Using **Confluent Cloud** or **AWS MSK** for Kafka
- Deploy workers separately (AWS Lambda, ECS, or Kubernetes)

---

## Troubleshooting

### Issue: Import Error on Deployment

**Solution:** Check that all dependencies are in `production/requirements.txt`

```bash
# Test locally
pip install -r production/requirements.txt
python api/index.py
```

### Issue: Database Connection Fails

**Solutions:**
1. Verify environment variables are set in Vercel dashboard
2. Ensure PostgreSQL allows connections from Vercel IPs
3. Check database credentials
4. Test connection locally with same credentials

```bash
# Test database connection
psql -h YOUR_DB_HOST -U YOUR_DB_USER -d YOUR_DB_NAME
```

### Issue: API Returns 500 Error

**Check logs:**
```bash
# View Vercel logs
vercel logs

# Or in dashboard: Deployment → Logs
```

**Common causes:**
- Missing environment variables
- Database connection issues
- Missing API keys

### Issue: Cold Start Time Too Slow

**Solutions:**
1. Upgrade to Vercel Pro ($20/month) for "Always On"
2. Use a cron job to ping the health endpoint every minute
3. Optimize import statements in the app

```bash
# Keep-alive script
curl https://your-app.vercel.app/health
```

### Issue: File Not Found Errors

**Note:** Vercel serverless has a read-only filesystem. Only `/tmp` is writable.

**Solution:** Use cloud storage (S3, Google Cloud Storage) for file uploads.

---

## Monitoring & Analytics

### Vercel Dashboard

Monitor your deployment at: [vercel.com/dashboard](https://vercel.com/dashboard)

- **Analytics**: Request counts, response times
- **Logs**: Real-time function logs
- **Deployments**: Deployment history and rollbacks

### Health Monitoring

```bash
# Set up health check monitoring
curl -f https://your-app.vercel.app/health || \
  echo "Service is down!" | mail -s "Alert: FTE Down" admin@example.com
```

---

## CI/CD with GitHub

Vercel automatically deploys when you push to GitHub:

1. Push to `main` → Production deployment
2. Push to other branches → Preview deployment

```bash
# Commit and push changes
git add .
git commit -m "Update API endpoints"
git push origin main

# Vercel will auto-deploy!
```

---

## Quick Reference

### Useful Commands

```bash
# Deploy to preview
vercel

# Deploy to production
vercel --prod

# View logs
vercel logs

# List deployments
vercel ls

# Remove deployment
vercel rm <deployment-url>

# Add environment variable
vercel env add MY_VAR

# Pull environment variables locally
vercel env pull
```

### Important URLs

| Resource | URL |
|----------|-----|
| **API Docs** | `https://your-app.vercel.app/api/docs` |
| **Health Check** | `https://your-app.vercel.app/health` |
| **Readiness** | `https://your-app.vercel.app/ready` |
| **Liveness** | `https://your-app.vercel.app/live` |
| **Web Form** | `https://your-app.vercel.app/web-form` |

---

## Support

- **Vercel Docs**: [vercel.com/docs](https://vercel.com/docs)
- **FastAPI Docs**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Mangum Docs**: [mangum.co](https://mangum.co)

---

*Deployed with ❤️ for the CRM Digital FTE Factory Hackathon 5*

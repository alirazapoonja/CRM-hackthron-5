# =============================================================================
# Dockerfile for Customer Success FTE
# =============================================================================
# Multi-stage build for optimized production image
# Supports both API and Worker deployments

# =============================================================================
# STAGE 1: Base Image with Python
# =============================================================================
FROM python:3.11-slim-bookworm AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build dependencies
    build-essential \
    gcc \
    # Async support
    libevent-dev \
    # SSL/TLS support
    libssl-dev \
    # PostgreSQL client libraries
    libpq-dev \
    # Kafka support
    librdkafka-dev \
    # Utilities
    curl \
    netcat-openbsd \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# =============================================================================
# STAGE 2: Dependencies
# =============================================================================
FROM base AS dependencies

# Copy requirements first for better caching
COPY production/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# STAGE 3: Build
# =============================================================================
FROM base AS build

# Copy installed dependencies
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
COPY production/ /app/production/
COPY context/ /app/context/
COPY specs/ /app/specs/

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/live')" || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "uvicorn", "production.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# =============================================================================
# STAGE 4: API Image (slim, optimized for API workloads)
# =============================================================================
FROM base AS api

# Copy installed dependencies
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code (API only)
COPY production/api/ /app/production/api/
COPY production/channels/ /app/production/channels/
COPY production/agent/ /app/production/agent/
COPY production/database/ /app/production/database/
COPY production/kafka_client.py /app/production/
COPY production/__init__.py /app/production/

# Create necessary directories
RUN mkdir -p /app/logs /app/tmp && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/live')" || exit 1

# Run API server
CMD ["python", "-m", "uvicorn", "production.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# =============================================================================
# STAGE 5: Worker Image (optimized for message processing)
# =============================================================================
FROM base AS worker

# Copy installed dependencies
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code (Worker only)
COPY production/workers/ /app/production/workers/
COPY production/channels/ /app/production/channels/
COPY production/agent/ /app/production/agent/
COPY production/database/ /app/production/database/
COPY production/kafka_client.py /app/production/
COPY production/__init__.py /app/production/

# Create necessary directories
RUN mkdir -p /app/logs /app/tmp && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose metrics port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "message_processor" || exit 1

# Run worker
CMD ["python", "-m", "production.workers.message_processor"]

# =============================================================================
# BUILD INSTRUCTIONS
# =============================================================================
# Build API image:
#   docker build -f production/Dockerfile --target api -t customer-success-fte-api:v1.0.0 .
#
# Build Worker image:
#   docker build -f production/Dockerfile --target worker -t customer-success-fte-worker:v1.0.0 .
#
# Build both (multi-platform):
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     -f production/Dockerfile --target api \
#     -t company-registry/customer-success-fte-api:v1.0.0 \
#     --push .
#
# Run locally:
#   docker run -p 8000:8000 --env-file production/.env customer-success-fte-api:v1.0.0

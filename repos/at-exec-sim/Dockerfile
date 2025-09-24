# Multi-stage build for production-ready container
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Production stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN groupadd -r execsim && useradd -r -g execsim execsim

# Create application directory
WORKDIR /app

# Copy application code
COPY src/at_exec_sim /app/at_exec_sim

# Set environment defaults
ENV PORT=8004 \
    SERVICE_NAME=at-exec-sim \
    NATS_URL=nats://nats:4222 \
    NATS_STREAM=trading-events \
    NATS_DURABLE=exec-sim-consumer \
    NATS_SUBJECT_ORDER_INTENT=decisions.order_intent \
    NATS_SUBJECT_FILL=executions.fill \
    NATS_SUBJECT_RECONCILE=executions.reconcile \
    SIMULATION_MIN_DELAY_MS=100 \
    SIMULATION_MAX_DELAY_MS=2000 \
    SIMULATION_PARTIAL_FILL_CHANCE=0.1 \
    SIMULATION_SLIPPAGE_BPS=2 \
    IDEMPOTENCY_TTL_SEC=3600 \
    RATE_LIMIT_RPS=100 \
    REPLAY_WINDOW_SEC=300 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc \
    LOG_LEVEL=INFO \
    ENV=production \
    PYTHONPATH=/app

# Create Prometheus multiproc directory
RUN mkdir -p /tmp/prometheus_multiproc && \
    chown -R execsim:execsim /tmp/prometheus_multiproc

# Switch to non-root user
USER execsim

# Expose port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8004/healthz || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "at_exec_sim.app:app", "--host", "0.0.0.0", "--port", "8004", "--workers", "1"]
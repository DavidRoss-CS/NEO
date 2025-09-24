FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8002 \
    SERVICE_NAME=at-agent-mcp \
    LOG_LEVEL=INFO \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus \
    STRATEGY_TYPE=momentum \
    RISK_LIMIT=0.02 \
    CONFIDENCE_THRESHOLD=0.7 \
    MAX_POSITIONS=5

# Create prometheus metrics directory
RUN mkdir -p /tmp/prometheus && \
    chmod 777 /tmp/prometheus

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY at_agent_mcp/ ./at_agent_mcp/

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /tmp/prometheus

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/healthz').read()"

# Expose port
EXPOSE 8002

# Start the application with single worker for proper signal handling
CMD ["python", "-m", "uvicorn", "at_agent_mcp.app:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
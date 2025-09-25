FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8001 \
    SERVICE_NAME=at-gateway \
    LOG_LEVEL=INFO \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus \
    PYTHONPATH=/app/at-core:$PYTHONPATH

# Create prometheus metrics directory
RUN mkdir -p /tmp/prometheus && \
    chmod 777 /tmp/prometheus

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy at-core for imports
COPY at-core ./at-core/

# Copy requirements first for better caching
COPY at-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY at-gateway/at_gateway/ ./at_gateway/

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /tmp/prometheus

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/healthz || exit 1

# Expose port
EXPOSE 8001

# Start the application with single worker for proper signal handling
CMD ["python", "-m", "uvicorn", "at_gateway.app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
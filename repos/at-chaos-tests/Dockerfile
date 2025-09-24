# Chaos Testing Framework
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    netcat-openbsd \
    iptables \
    stress-ng \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create logs directory
RUN mkdir -p /app/logs

# Environment defaults
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO
ENV CHAOS_MODE=safe

# Expose metrics port
EXPOSE 8008

# Health check
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8008/healthz || exit 1

# Run chaos tests
CMD ["python", "-m", "src.chaos_runner"]
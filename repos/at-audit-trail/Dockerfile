# Audit Trail Service
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/

# Create audit storage directory
RUN mkdir -p /app/audit_logs

# Environment defaults
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO
ENV AUDIT_STORAGE_PATH=/app/audit_logs

# Expose ports
EXPOSE 8009

# Health check
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8009/healthz || exit 1

# Run audit service
CMD ["python", "-m", "uvicorn", "src.audit_service:app", "--host", "0.0.0.0", "--port", "8009"]
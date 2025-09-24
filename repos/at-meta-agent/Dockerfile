FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY at_meta_agent/ ./at_meta_agent/

# Create non-root user
RUN useradd -m -u 1000 metaagent
USER metaagent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/healthz || exit 1

EXPOSE 8003

CMD ["python", "-m", "at_meta_agent.app"]
FROM python:3.12-slim

WORKDIR /app

# Set PYTHONPATH to include at-core
ENV PYTHONPATH=/app/at-core:$PYTHONPATH

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy at-core for the editable install (will be provided by build context)
COPY at-core ./at-core/

# Copy requirements first for better Docker layer caching
COPY at-agent-orchestrator/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY at-agent-orchestrator/at_agent_orchestrator/ ./at_agent_orchestrator/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8010/healthz || exit 1

# Expose port
EXPOSE 8010

# Run the application
CMD ["python", "-m", "uvicorn", "at_agent_orchestrator.app:app", "--host", "0.0.0.0", "--port", "8010"]
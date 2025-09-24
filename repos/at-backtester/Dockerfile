FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY at_backtester/ ./at_backtester/

# Create non-root user
RUN useradd -m -u 1000 backtester
USER backtester

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8005/healthz || exit 1

EXPOSE 8005

CMD ["python", "-m", "at_backtester.app"]
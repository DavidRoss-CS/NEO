FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY at_strategy_manager/ ./at_strategy_manager/

# Create plugins directory
RUN mkdir -p plugins

# Create non-root user
RUN useradd -m -u 1000 strategist
USER strategist

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8007/healthz || exit 1

EXPOSE 8007

CMD ["python", "-m", "at_strategy_manager.app"]
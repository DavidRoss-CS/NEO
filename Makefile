.PHONY: help up down restart logs test test-smoke test-unit test-integration clean build status metrics health golden verify setup dev-setup

# Default target - show help
help:
	@echo "Agentic Trading Architecture - Development Commands"
	@echo ""
	@echo "Quick Start:"
	@echo "  make setup         - Initial setup (create .env, install deps)"
	@echo "  make up           - Start minimal services (development)"
	@echo "  make up-prod      - Start all services (production)"
	@echo "  make verify       - Quick verification test"
	@echo "  make down         - Stop services"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make up           - Start minimal services (development)"
	@echo "  make up-prod      - Start all services (production)"
	@echo "  make down         - Stop services"
	@echo "  make down-prod    - Stop production services"
	@echo "  make build        - Build minimal images"
	@echo "  make build-prod   - Build all images"
	@echo "  make clean        - Clean minimal setup"
	@echo "  make clean-prod   - Clean production setup"
	@echo ""
	@echo "Monitoring:"
	@echo "  make status       - Show service status"
	@echo "  make logs         - Tail all service logs"
	@echo "  make health       - Check health endpoints"
	@echo "  make metrics      - Show key metrics"
	@echo ""
	@echo "Testing:"
	@echo "  make test         - Run all tests"
	@echo "  make test-smoke   - Run smoke tests"
	@echo "  make golden       - Run golden path test"
	@echo "  make verify       - Quick verification test"
	@echo ""
	@echo "Development:"
	@echo "  make watch        - Watch logs in real-time"
	@echo "  make nats-stats   - Show NATS statistics"
	@echo "  make check-secrets - Check for hardcoded secrets"

# Setup commands
setup:
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then \
		cp .env.example .env 2>/dev/null || echo "No .env.example found"; \
		echo "Created .env - please review settings"; \
	else \
		echo ".env already exists"; \
	fi
	@chmod +x quick_verify.sh test_smoke_ci.sh setup_dev.sh 2>/dev/null || true
	@echo "Setup complete!"

dev-setup: setup
	@echo "Checking prerequisites..."
	@command -v docker >/dev/null 2>&1 || { echo "❌ Docker required but not found"; exit 1; }
	@command -v docker-compose >/dev/null 2>&1 || command -v docker compose >/dev/null 2>&1 || { echo "❌ Docker Compose required"; exit 1; }
	@echo "✅ Development environment ready!"

# Docker commands
# Minimal services (development)
up:
	@echo "Starting minimal services (development)..."
	@docker-compose -f docker-compose.minimal.yml up -d
	@echo "Waiting for services to start..."
	@sleep 5
	@echo "Services started. Checking health..."
	@make health-quiet || true

down:
	@echo "Stopping minimal services..."
	@docker-compose -f docker-compose.minimal.yml down

# Production services (full system)
up-prod:
	@echo "Starting production services (full system)..."
	@docker-compose -f docker-compose.production.yml up -d
	@echo "Waiting for services to start..."
	@sleep 10
	@echo "All services started. Checking health..."
	@make health-prod-quiet || true

down-prod:
	@echo "Stopping production services..."
	@docker-compose -f docker-compose.production.yml down

restart: down up

build:
	@echo "Building minimal Docker images..."
	@docker-compose -f docker-compose.minimal.yml build

build-prod:
	@echo "Building all Docker images..."
	@docker-compose -f docker-compose.production.yml build

clean:
	@echo "Cleaning minimal setup..."
	@docker-compose -f docker-compose.minimal.yml down -v
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Minimal cleanup complete!"

clean-prod:
	@echo "Cleaning production setup..."
	@docker-compose -f docker-compose.production.yml down -v
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Production cleanup complete!"

reset: clean up

# Monitoring commands
status:
	@echo "=== Service Status ==="
	@docker-compose -f docker-compose.minimal.yml ps

logs:
	@docker-compose -f docker-compose.minimal.yml logs -f --tail=100

watch: logs

health:
	@echo "=== Service Health Check ==="
	@echo -n "Gateway (8001): "
	@curl -s http://localhost:8001/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"
	@echo -n "Agent (8002): "
	@curl -s http://localhost:8002/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"
	@echo -n "Exec-Sim (8004): "
	@curl -s http://localhost:8004/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"
	@echo -n "Audit (8005): "
	@curl -s http://localhost:8005/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"

health-quiet:
	@curl -s http://localhost:8001/healthz | jq -r '.ok' >/dev/null 2>&1 || true
	@curl -s http://localhost:8004/healthz | jq -r '.ok' >/dev/null 2>&1 || true

health-prod:
	@echo "=== Production Service Health Check ==="
	@echo -n "Gateway (8001): "
	@curl -s http://localhost:8001/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"
	@echo -n "Agent (8002): "
	@curl -s http://localhost:8002/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"
	@echo -n "Meta-Agent (8003): "
	@curl -s http://localhost:8003/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"
	@echo -n "Exec-Sim (8004): "
	@curl -s http://localhost:8004/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"
	@echo -n "Backtester (8005): "
	@curl -s http://localhost:8005/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"
	@echo -n "Broker-Adapters (8006): "
	@curl -s http://localhost:8006/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"
	@echo -n "Audit-Trail (8009): "
	@curl -s http://localhost:8009/healthz | jq -r '.ok' 2>/dev/null && echo " ✅" || echo " ❌"

health-prod-quiet:
	@curl -s http://localhost:8001/healthz | jq -r '.ok' >/dev/null 2>&1 || true
	@curl -s http://localhost:8002/healthz | jq -r '.ok' >/dev/null 2>&1 || true
	@curl -s http://localhost:8003/healthz | jq -r '.ok' >/dev/null 2>&1 || true
	@curl -s http://localhost:8004/healthz | jq -r '.ok' >/dev/null 2>&1 || true
	@curl -s http://localhost:8005/healthz | jq -r '.ok' >/dev/null 2>&1 || true
	@curl -s http://localhost:8006/healthz | jq -r '.ok' >/dev/null 2>&1 || true
	@curl -s http://localhost:8009/healthz | jq -r '.ok' >/dev/null 2>&1 || true

metrics:
	@echo "=== Key Metrics ==="
	@echo ""
	@echo "Gateway webhooks received:"
	@curl -s http://localhost:8001/metrics 2>/dev/null | grep "gateway_webhooks_received_total" | grep -v "#" || echo "  No data"
	@echo ""
	@echo "Agent signals processed:"
	@curl -s http://localhost:8002/metrics 2>/dev/null | grep "agent_signals_received_total" | grep -v "#" || echo "  No data"
	@echo ""
	@echo "Exec-sim orders processed:"
	@curl -s http://localhost:8004/metrics 2>/dev/null | grep "exec_sim_orders_received_total" | grep -v "#" || echo "  No data"
	@echo ""
	@echo "Exec-sim fills generated:"
	@curl -s http://localhost:8004/metrics 2>/dev/null | grep "exec_sim_fills_generated_total" | grep -v "#" || echo "  No data"

# Testing commands
test: test-smoke

test-smoke:
	@echo "Running smoke tests..."
	@bash test_smoke_ci.sh

verify:
	@echo "Running quick verification..."
	@bash quick_verify.sh

golden:
	@echo "=== Running Golden Path Test ==="
	@CORRELATION_ID=$$(uuidgen 2>/dev/null || echo "golden-$$RANDOM") && \
	TIMESTAMP=$$(date +%s) && \
	NONCE="nonce-$$RANDOM" && \
	SECRET="test-secret" && \
	PAYLOAD='{"instrument":"AAPL","price":150.50,"signal":"buy","strength":0.75}' && \
	MESSAGE="$$TIMESTAMP.$$NONCE.$$PAYLOAD" && \
	SIGNATURE=$$(echo -n "$$MESSAGE" | openssl dgst -sha256 -hmac "$$SECRET" -hex | cut -d' ' -f2) && \
	echo "Correlation ID: $$CORRELATION_ID" && \
	echo "Sending webhook to gateway..." && \
	curl -s -X POST http://localhost:8001/webhook/test \
		-H "Content-Type: application/json" \
		-H "X-Signature: $$SIGNATURE" \
		-H "X-Timestamp: $$TIMESTAMP" \
		-H "X-Nonce: $$NONCE" \
		-d "$$PAYLOAD" | jq . && \
	echo "✅ Webhook sent. Check metrics with: make metrics"

test-unit:
	@echo "⚠️  Unit tests not yet implemented"
	@echo "See TASK_ASSIGNMENTS.md to contribute"

test-integration:
	@echo "⚠️  Integration tests not yet implemented"
	@echo "See TASK_ASSIGNMENTS.md to contribute"

# NATS debugging
nats-stats:
	@echo "=== NATS Stream Info ==="
	@docker run --rm --network agentic-trading-architecture-full_default \
		natsio/nats-box:latest \
		nats -s nats://nats:4222 str info trading-events 2>/dev/null || echo "NATS not available"
	@echo ""
	@echo "=== NATS Consumers ==="
	@docker run --rm --network agentic-trading-architecture-full_default \
		natsio/nats-box:latest \
		nats -s nats://nats:4222 con ls trading-events 2>/dev/null || echo "NATS not available"

# Security check
check-secrets:
	@echo "Checking for hardcoded secrets..."
	@! grep -r "password\|secret\|key\|token" --include="*.py" --include="*.yml" --include="*.yaml" \
		--exclude-dir=.git --exclude-dir=__pycache__ --exclude="*.md" . 2>/dev/null | \
		grep -v "os.getenv\|environment\|SECRET\|TOKEN\|KEY\|getenv" || \
		echo "✅ No obvious secrets found"

# Service-specific logs
gateway-logs:
	@docker logs -f agentic-trading-architecture-full-gateway-1

agent-logs:
	@docker logs -f agentic-trading-architecture-full-agent-1

exec-logs:
	@docker logs -f agentic-trading-architecture-full-exec-1

# Development database
db-shell:
	@echo "⚠️  No database configured yet"
	@echo "SQLite audit trail at: repos/at-audit/audit.db"

# Quick development cycle
dev: clean up verify
	@echo "✅ Development environment ready and verified!"

# CI simulation
ci: check-secrets test-smoke
	@echo "✅ CI checks passed!"

.SILENT: health-quiet
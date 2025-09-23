# Agentic Trading Architecture - Master Guide

## Purpose

This platform orchestrates AI agents for automated trading across futures, FX, and crypto markets. We use a multi-repo, event-driven architecture to enable independent deployment, parallel development, and clean separation of concerns. Each repository handles a specific domain (ingestion, analysis, execution, monitoring) while communicating through standardized NATS events.

## Repo Map

| Repo | Role | Language | Runs As | Exposes | Subscribes | Emits |
|------|------|----------|---------|---------|------------|-------|
| at-gateway | Market data ingestion | Python | FastAPI service | REST webhooks | - | `signals.raw`, `signals.normalized` |
| at-core | Shared contracts & schemas | Python | Library | Event schemas | - | Contract definitions |
| at-agent-mcp | Trading strategy agents | Python | MCP servers | Agent endpoints | `signals.*` | `decisions.order_intent` |
| at-exec-sim | Execution & simulation | Python | FastAPI service | Trade APIs | `decisions.*` | `executions.fill`, `executions.reconcile` |
| at-observability | Metrics & monitoring | Python | Grafana/Prometheus | Dashboards | All events | Alerts |

## Local Dev Quickstart

### Python Setup
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # if present in repo
uvicorn main:app --reload --port 8000
```

### Docker Infrastructure
```bash
docker compose -f docker-compose.dev.yml up -d
```

### Ports Table

| Service | Port | Notes |
|---------|------|-------|
| at-gateway | 8001 | Webhook endpoints |
| at-mcp | 8002 | Agent management |
| at-exec-sim | 8004 | Execution simulation |
| NATS | 4222 | Message broker |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Dashboards (admin/admin) |

## Run Order

1. **NATS** - Start message broker first
2. **at-core** - Ensure schemas are available
3. **at-gateway** - Begin ingesting market data
4. **at-agent-mcp** - Start strategy agents
5. **at-exec-sim** - Enable trade execution
6. **at-observability** - Monitor system health

**Healthy looks like**: Each service responds to health checks, NATS shows active consumers, Grafana displays incoming metrics.

## Environment Variables

| Variable | Sample Value | Description |
|----------|--------------|-------------|
| `NATS_URL` | `nats://localhost:4222` | NATS server connection |
| `NATS_STREAM` | `trading-events` | JetStream stream name |
| `NATS_DURABLE` | `service-consumer` | Durable consumer name |
| `API_KEY_HMAC_SECRET` | `your-secret-key` | Webhook signature validation |
| `PROMETHEUS_MULTIPROC_DIR` | `/tmp/prometheus` | Metrics storage directory |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `SERVICE_NAME` | `at-gateway` | Service identifier |
| `ENV` | `development` | Environment name |

## Branching & PR Workflow

- **Trunk-based development** with short-lived feature branches
- **Commit prefix**: `repo-scope: description` (e.g., `gateway: add TradingView webhook`)
- **Required checks**: unit tests, contract tests, pylint/black
- **PR template**: includes updated docs, tests, and rollback plan

## Failure Drills

- **NATS outage**: `docker stop nats` - services should gracefully degrade
- **Slow consumer**: Set consumer max-inflight=1 - backpressure should engage
- **Bad contract**: Deploy incompatible schema - contract tests should fail

## Glossary

- **Signal**: Raw or normalized market data event
- **Decision**: Trading action proposed by an agent
- **Execution**: Actual trade fill or simulation result
- **Contract**: Versioned event schema definition
- **Idempotency key**: Unique identifier preventing duplicate processing
- **JetStream**: NATS persistent streaming layer
- **Backpressure**: Flow control mechanism when consumers lag
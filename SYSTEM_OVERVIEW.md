# Agentic Trading Architecture - System Overview

An event-driven algorithmic trading system that receives market signals, makes automated trading decisions, and executes orders through broker connections.

## Quick Start

```bash
# Start the system
docker compose -f docker-compose.dev.yml up -d

# Verify it's working
./quick_verify.sh

# Run comprehensive tests
./test_smoke_ci.sh
```

## Architecture Overview

```
Market Signal → Gateway → NATS → Agent → Decision → Executor → Broker
                  ↓         ↓      ↓        ↓          ↓        ↓
               Validation  Queue Analysis Risk Check  Fill   Audit
                  ↓         ↓      ↓        ↓          ↓        ↓
               Metrics   Durability AI    Portfolio Reconcile Trail
```

## Information Flow

### 1. Signal Ingestion (`at-gateway`)
```http
POST /webhook/test
{
  "instrument": "AAPL",
  "price": 150.25,
  "signal": "buy",
  "strength": 0.8
}
```
- **Authentication**: HMAC-SHA256 signature validation
- **Validation**: Schema validation with unknown field tracking
- **Idempotency**: Correlation ID prevents duplicate processing
- **Output**: Publishes to `signals.normalized` NATS subject

### 2. Decision Making (`at-agent-mcp`)
```json
// Consumes from: signals.normalized
{
  "corr_id": "req_abc123",
  "instrument": "AAPL",
  "signal": "buy",
  "strength": 0.8,
  "price": 150.25,
  "timestamp": "2025-01-15T10:30:00Z"
}

// Publishes to: decisions.order_intent
{
  "corr_id": "req_abc123",
  "agent_id": "momentum_v1",
  "instrument": "AAPL",
  "side": "buy",
  "quantity": 100,
  "order_type": "market",
  "risk_params": {
    "max_position": 1000,
    "stop_loss": 0.02
  }
}
```

### 3. Order Execution (`at-exec-sim`)
```json
// Consumes from: decisions.order_intent
// Publishes to: executions.fill
{
  "corr_id": "req_abc123",
  "fill_id": "fill_xyz789",
  "instrument": "AAPL",
  "side": "buy",
  "quantity_filled": 100,
  "avg_fill_price": 150.27,
  "fill_status": "complete",
  "execution_venue": "simulator",
  "fill_timestamp": "2025-01-15T10:30:01.250Z"
}
```

### 4. Audit Trail (`at-audit`)
Every event is logged with hash-chaining for immutability:
```json
{
  "event_id": "evt_001",
  "correlation_id": "req_abc123",
  "event_type": "execution_fill",
  "timestamp": "2025-01-15T10:30:01.250Z",
  "data": { /* fill event */ },
  "hash": "sha256:abcd...",
  "previous_hash": "sha256:1234...",
  "chain_position": 1337
}
```

## Service Breakdown

| Service | Port | Purpose | Key Features |
|---------|------|---------|--------------|
| **at-gateway** | 8001 | API Gateway | HMAC auth, rate limiting, webhook ingestion |
| **at-agent-mcp** | 8002 | Decision Engine | Strategy execution, risk assessment, ML models |
| **at-exec-sim** | 8004 | Order Execution | Broker simulation, fill generation, reconciliation |
| **at-audit** | 8005 | Audit Trail | Immutable logging, hash-chaining, tamper detection |
| **at-observability** | 8006 | Monitoring | Grafana dashboards, alerting, system health |

## Technology Stack

### Core Infrastructure
- **Message Bus**: NATS JetStream (durability, replay, low latency)
- **Runtime**: Python 3.12 + FastAPI (async, performant, typed)
- **Containerization**: Docker + Docker Compose (K8s ready)
- **Observability**: Prometheus + Grafana + structured logging

### Data Storage
- **Audit Logs**: SQLite (embedded, sufficient for current scale)
- **Message Persistence**: NATS JetStream (file storage)
- **Configuration**: Environment variables (12-factor app)

### Future Stack (Roadmap)
- **Production DB**: PostgreSQL (when scaling beyond embedded)
- **Orchestration**: Kubernetes (production deployment)
- **Secrets**: HashiCorp Vault or K8s Secrets
- **Tracing**: OpenTelemetry (distributed debugging)

## Event-Driven Architecture

### NATS Subjects (Event Contract)
```yaml
signals.normalized:      # Validated market signals
decisions.order_intent:  # Trading decisions from agents
executions.fill:         # Order execution results
executions.reconcile:    # Position reconciliation
audit.event:            # Immutable audit entries
```

See [CONTRACT.md](CONTRACT.md) for complete schema definitions.

### JetStream Consumers
```yaml
mcp-signals:       # Agent consumes signals
exec-intents:      # Exec-sim consumes decisions
audit-all:         # Audit consumes all events
meta-decisions:    # Meta-agent consumes decisions
```

### State Management

**Stateless Services**: Gateway, Exec-sim (simulation only)
**In-Memory State**: Agent (strategies, models), Audit (recent events)
**Persistent State**:
- Audit trail (SQLite, hash-chained)
- NATS JetStream (message durability)
- Future: Portfolio positions (PostgreSQL)

## Security Model

### Authentication
```bash
# HMAC-SHA256 signature
STRING_TO_SIGN = "{timestamp}.{nonce}.{body}"
SIGNATURE = HMAC-SHA256(SECRET, STRING_TO_SIGN)

# Headers
X-Timestamp: 1642250400
X-Nonce: unique-request-id
X-Signature: abcd1234...
```

### Security Boundaries
- **API Gateway**: External-facing, HMAC validation
- **Internal Services**: Trust boundary (no auth between services)
- **Future**: mTLS between services, service mesh

### Secrets Management
- **Development**: Environment variables
- **Production**: Kubernetes Secrets or HashiCorp Vault

## Development Paradigm

### Event-First Design
Every action produces events that flow through NATS:
```python
# Example: Order processing produces multiple events
order_received → validation_passed → risk_checked → execution_started → fill_generated
```

### Defensive Programming
```python
# Fail fast on missing configuration
REQUIRED_CONFIGS = ["NATS_URL", "NATS_STREAM", "NATS_DURABLE"]
missing = [k for k in REQUIRED_CONFIGS if not os.getenv(k)]
if missing:
    raise SystemExit(f"FATAL: Missing environment variables: {missing}")

# Schema validation with unknown field tracking
jsonschema.validate(order_data, schema)
unknown_fields = set(order_data.keys()) - set(schema["properties"].keys())
if unknown_fields:
    logger.info("Unknown fields detected", fields=list(unknown_fields))
```

### Observable by Default
```python
# Metrics everywhere
orders_received = Counter('orders_received_total', ['status'])
processing_time = Histogram('processing_duration_seconds', ['operation'])

# Structured logging with correlation IDs
logger.info("Processing order",
           corr_id=corr_id,
           instrument=order["instrument"],
           side=order["side"],
           quantity=order["quantity"])
```

## Service Interaction Patterns

### Command Flow (Orders)
```
Gateway → NATS → Agent → NATS → Exec-sim → NATS → Audit
```

### Query Flow (Metrics/Health)
```
Client → Service REST API (no NATS for synchronous queries)
```

### Event Flow (Notifications)
```
Any Service → NATS → Interested Consumers
```

## Testing Strategy

See [TESTING.md](TESTING.md) for detailed testing practices.

### Test Pyramid
```
    ┌─────────────────┐
    │   E2E Tests     │  Smoke tests, full flow validation
    │─────────────────│
    │ Integration     │  Service-to-service, NATS interactions
    │─────────────────│
    │   Unit Tests    │  Schema validation, business logic
    └─────────────────┘
```

### Running Tests
```bash
# Unit tests
pytest tests/unit/

# Integration tests
docker compose -f docker-compose.test.yml up --abort-on-container-exit

# End-to-end smoke test
./test_smoke_ci.sh
```

## Deployment Targets

### Development
```bash
docker compose -f docker-compose.dev.yml up -d
```

### Production (Future)
```bash
# Kubernetes deployment
kubectl apply -f k8s/
helm install trading-system ./chart
```

## Observability

See [OBSERVABILITY.md](OBSERVABILITY.md) for comprehensive monitoring setup.

### Health Checks
```bash
# Service health
curl localhost:8001/healthz  # Gateway
curl localhost:8002/healthz  # Agent
curl localhost:8004/healthz  # Exec-sim

# Enhanced exec-sim health with consumer status
curl localhost:8004/healthz | jq '.consumer'
```

### Metrics
```bash
# Key metrics endpoints
curl localhost:8001/metrics  # Gateway metrics
curl localhost:8004/metrics  # Execution metrics

# Example metrics
gateway_webhooks_received_total{source="test",status="success"}
exec_sim_orders_received_total{status="valid"}
exec_sim_fills_generated_total{fill_type="full",instrument="AAPL"}
```

### Sample End-to-End Trace
```
[2025-01-15T10:30:00.000Z] Gateway: webhook received, corr_id=req_abc123
[2025-01-15T10:30:00.010Z] Gateway: published to signals.normalized
[2025-01-15T10:30:00.015Z] Agent: consumed signal, applying strategy
[2025-01-15T10:30:00.025Z] Agent: published to decisions.order_intent
[2025-01-15T10:30:00.030Z] Exec-sim: consumed order intent, simulating
[2025-01-15T10:30:01.250Z] Exec-sim: published fill event
[2025-01-15T10:30:01.255Z] Audit: logged execution, hash=sha256:abcd...
```

## Getting Started as a Contributor

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (for local development)
- Basic understanding of async Python
- Familiarity with event-driven architecture

### Your First Contribution
1. **Start the system**: `docker compose -f docker-compose.dev.yml up -d`
2. **Explore the flow**: Send a test webhook and watch logs
3. **Pick a Good First Issue**: See [CONTRIBUTING.md](CONTRIBUTING.md)
4. **Run tests**: Ensure your changes don't break existing functionality

### Good First Issues
- Add unit tests for schema validation
- Create OpenAPI/Swagger documentation
- Implement stop-loss order types
- Add Redis caching for idempotency
- Create a simple monitoring dashboard

## Schema Evolution

### Versioning Strategy
- **Backward Compatible**: Add optional fields, preserve required fields
- **Breaking Changes**: Increment schema version, support parallel processing
- **Migration**: Gradual rollout with feature flags

### Unknown Field Handling
```python
# Services accept unknown fields but log them
unknown_fields = set(data.keys()) - set(schema["properties"].keys())
if unknown_fields:
    metrics.unknown_fields.labels(service="exec-sim").inc()
    logger.info("Unknown fields", fields=list(unknown_fields))
```

## Current Status & Next Steps

### ✅ What's Working
- End-to-end signal → fill flow
- HMAC authentication with replay protection
- Resilient NATS JetStream integration
- Comprehensive observability (metrics, logs, health)
- Consumer configuration validation

### 🚧 In Progress
- Real broker integration (currently simulation)
- Advanced trading strategies
- Kubernetes deployment manifests
- Unit test coverage

### 📋 Roadmap
See [ROADMAP.md](ROADMAP.md) for detailed development priorities.

**Short-term (1 month)**: Broker adapters, core strategies, test coverage
**Medium-term (3 months)**: K8s deployment, PostgreSQL migration, performance optimization
**Long-term (6+ months)**: Multi-region, event sourcing, advanced ML

## References

- [CONTRACT.md](CONTRACT.md) - Event schemas and API contracts
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [TESTING.md](TESTING.md) - Testing practices and CI/CD
- [OBSERVABILITY.md](OBSERVABILITY.md) - Monitoring and alerting
- [ROADMAP.md](ROADMAP.md) - Development priorities and timeline

---

**Questions?** Check the docs above or open an issue for clarification.
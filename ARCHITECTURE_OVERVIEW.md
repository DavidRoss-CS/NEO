# Architecture Overview

## System Overview

The agentic trading architecture operates as an event-driven system where autonomous agents consume market signals and produce trading decisions. The backbone is a NATS JetStream message broker that ensures reliable, ordered delivery of events across service boundaries. Each service operates as a stateless worker, processing events and emitting results without maintaining persistent state.

Agents are designed as independent decision-makers that can be developed, deployed, and scaled independently. They consume normalized market data, apply their strategies, and propose trades through standardized event contracts. This design enables multiple strategies to run concurrently while maintaining system stability and observability.

## System Flow

```
TradingView/Webhook
        ↓
   at-gateway (validate, transform)
        ↓
   NATS: signals.raw, signals.normalized
        ↓
   at-core (schema validation)
        ↓
   at-agent-mcp (strategy execution)
        ↓
   NATS: decisions.order_intent
        ↓
   at-exec-sim (execution/simulation)
        ↓
   NATS: executions.fill, executions.reconcile
        ↓
   at-observability (metrics, alerts)
        ↓
   Prometheus → Grafana
```

## Event Subjects & Lifecycle

| Subject | Key Fields | Producer(s) | Consumer(s) | Idempotency Key |
|---------|------------|-------------|-------------|-----------------|
| `signals.raw` | `source`, `timestamp`, `payload` | at-gateway | at-core | `hash(source+timestamp+payload)` |
| `signals.normalized` | `instrument`, `price`, `volume` | at-core | at-agent-mcp | `hash(instrument+timestamp)` |
| `decisions.order_intent` | `strategy`, `instrument`, `side`, `quantity` | at-agent-mcp | at-exec-sim | `hash(strategy+instrument+timestamp+side)` |
| `executions.fill` | `order_id`, `fill_price`, `fill_quantity` | at-exec-sim | at-observability | `order_id` |
| `executions.reconcile` | `strategy`, `pnl`, `timestamp` | at-exec-sim | at-observability | `hash(strategy+timestamp)` |

## Idempotency & Retries

All events include an idempotency key derived from message content. Consumers must handle duplicate messages gracefully using these keys. The system operates under at-least-once delivery semantics.

**Retry Policy**: Exponential backoff starting at 1s, max 60s, up to 5 attempts. Failed messages after max retries are routed to poison queues for manual investigation.

**Consumer Implementation**: Each service maintains an in-memory cache of processed idempotency keys (TTL: 1 hour) to detect and skip duplicates.

## Backpressure

JetStream durable consumers operate in pull mode with configurable max-in-flight messages. When consumers lag, the broker automatically applies backpressure by withholding new messages until processing catches up.

**Per-repo settings**:
- Gateway: max-in-flight=100 (high throughput)
- Agents: max-in-flight=10 (deliberate processing)
- Execution: max-in-flight=5 (careful order handling)

## Security Boundaries

- **Webhook validation**: HMAC-SHA256 signatures on all inbound webhooks
- **Secrets management**: All secrets in environment variables, never in code
- **NATS credentials**: Least-privileged subjects per service
- **PII avoidance**: No personal data in events; use anonymized trader IDs

## Data Retention

- **Signals**: 7 days (high volume, short-term relevance)
- **Decisions**: 30 days (strategy analysis)
- **Executions**: 365 days (regulatory compliance)
- **Metrics**: 90 days in Prometheus

**Export hooks**: Automated daily exports to object storage for long-term analysis and compliance.

## Observability Hooks

Every event processed generates:
- **Structured logs**: JSON format with `corr_id` for tracing
- **Prometheus metrics**: Counter/histogram pattern per service
- **Health checks**: `/health` endpoint on all services
- **Circuit breakers**: Automatic fallback when downstream services fail

See [at-observability/OBSERVABILITY_MODEL.md](repos/at-observability/OBSERVABILITY_MODEL.md) for complete metrics catalog.
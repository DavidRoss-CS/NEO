# at-gateway

## Purpose

The gateway service is the **only** trusted ingress point for external market data and trading signals. It validates incoming webhooks, authenticates sources, normalizes payloads, and publishes structured events to NATS. The gateway does NOT make trading decisions, store data persistently, or communicate directly with execution systems.

**Responsibilities:**
- Webhook endpoint hosting and HTTP request handling
- HMAC signature validation and replay attack prevention
- Rate limiting and source allowlisting
- Payload normalization from external formats to canonical schemas
- Publishing `signals.raw` and `signals.normalized` events to NATS

**Non-responsibilities:**
- Trading strategy logic or decision making
- Data persistence or historical storage
- Direct broker/exchange communication
- User authentication or session management

## Data Flow

External sources (TradingView, custom webhooks) send HTTP POST requests to gateway endpoints. The gateway validates signatures, checks replay windows, normalizes payloads, and emits standardized NATS events for downstream consumption by agents and other services.

```
TradingView/External → HTTP POST → Validate/Auth → Normalize → NATS signals.*
                                        ↓
                               signals.raw, signals.normalized
                                        ↓
                                  Downstream agents
```

## Quick Start

### Python Environment
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn at_gateway.app:app --port 8001 --reload
```

### Infrastructure
```bash
docker compose -f ../../docker-compose.dev.yml up -d nats prom grafana
```

## Environment Variables

| Variable | Sample Value | Description |
|----------|--------------|-------------|
| `SERVICE_NAME` | `at-gateway` | Service identifier for logs/metrics |
| `NATS_URL` | `nats://localhost:4222` | NATS server connection |
| `NATS_STREAM` | `trading-events` | JetStream stream name |
| `NATS_DURABLE` | `gateway-consumer` | Durable consumer name |
| `API_KEY_HMAC_SECRET` | `your-secret-key` | Webhook signature validation |
| `IDEMPOTENCY_TTL_SEC` | `3600` | Duplicate detection window |
| `RATE_LIMIT_RPS` | `100` | Requests per second limit |
| `REPLAY_WINDOW_SEC` | `300` | Event replay tolerance |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENV` | `development` | Environment name |

**Source Validation**: Values in `ALLOWED_SOURCES` must exactly match the `source` field in request payloads or derived source identifiers (e.g., "tradingview" for TradingView endpoints). Case-sensitive matching.

## Contracts Overview

The gateway consumes HTTP webhooks and produces NATS events following schemas defined in at-core. See [API_SPEC.md](API_SPEC.md) for detailed endpoint documentation and [ADR-0002](../../DECISIONS/ADR-0002-event-contracts.md) for schema versioning policy.

**Input**: HTTP POST with JSON payload and authentication headers
**Output**: `signals.raw` (immediate) and `signals.normalized` (processed) NATS events

## Security Model

- **HMAC validation**: All requests must include valid `X-Signature` header using HMAC-SHA256
- **Replay protection**: `X-Timestamp` and `X-Nonce` headers prevent replay attacks within `REPLAY_WINDOW_SEC`
- **Source allowlist**: Only configured sources in `ALLOWED_SOURCES` are accepted
- **Request limits**: 1MB max payload size, configurable rate limiting per source
- **Error behavior**: 4xx for client errors (bad auth, invalid payload), 5xx for server errors (NATS down)

## Observability

Follows [ADR-0003](../../DECISIONS/ADR-0003-observability.md) conventions:

**Key metrics**:
- `gateway_webhooks_received_total{source, status}`
- `gateway_webhook_duration_seconds{source}`
- `gateway_nats_publish_total{subject, status}`
- `gateway_validation_errors_total{type}`

**Log fields**: `corr_id`, `source`, `instrument`, `latency_ms`, `validation_status`

**Endpoints**:
- `GET /healthz` - Service health and NATS connectivity
- `GET /metrics` - Prometheus metrics

## Failure Modes & Policies

### NATS Unavailable (Fail-Closed)
When NATS is unreachable, the gateway operates in **fail-closed** mode:
- Returns 503 for all webhook requests
- Buffers up to 1000 messages in memory (30-second window)
- Health check shows `nats: "disconnected"`
- No data loss: clients must retry failed requests

**Rationale**: Trading systems require guaranteed delivery; better to reject requests than lose market signals.

### Graceful Degradation
- Invalid signatures: Return 401, continue processing valid requests
- Rate limits: Return 429 for excess, allow normal traffic through
- Schema validation: Log errors, still publish raw events for manual review

## Limitations & TODOs

- **Schema version pinning**: Currently uses latest schemas; needs version pinning for rollback safety
- **Replay cache persistence**: Nonce cache is in-memory only; lost on restart (brief replay window vulnerability)
- **Dead letter queue**: Failed normalizations logged but not queued for automated retry
- **Schema registry integration**: Uses local schema files; integrate with at-core registry for version management
- **Structured key rotation**: Manual secret rotation; implement overlap periods and automated validation
- **Burst RPS handling**: Fixed rate limits; add token bucket for traffic spike tolerance
- **Request prioritization**: All requests treated equally; consider priority lanes for critical sources
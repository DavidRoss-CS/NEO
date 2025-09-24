# Event Contract Definitions

This document defines all event schemas, NATS subjects, and API contracts for the Agentic Trading Architecture.

## Version Information
- **Current Schema Version**: 1.0.0
- **Breaking Change Policy**: New major version with parallel support for 2 releases
- **Schema Format**: JSON Schema Draft 7

## NATS Subjects

### Subject Naming Convention
```
{domain}.{action}
```

| Subject | Publisher | Consumers | Description |
|---------|-----------|-----------|-------------|
| `signals.normalized` | at-gateway | at-agent-mcp | Validated market signals |
| `decisions.order_intent` | at-agent-mcp | at-exec-sim, at-audit | Trading decisions |
| `executions.fill` | at-exec-sim | at-audit, at-portfolio | Order fill notifications |
| `executions.reconcile` | at-exec-sim | at-audit, at-portfolio | Position reconciliation |
| `audit.event` | all services | at-audit | Immutable audit entries |

## Correlation ID Propagation

Every event MUST include a correlation ID for end-to-end tracing:

```json
{
  "corr_id": "req_abc123def456",  // Required, unique per flow
  "parent_corr_id": "req_xyz789",  // Optional, for sub-flows
  "timestamp": "2025-01-15T10:30:00.000Z",  // ISO 8601 UTC
  ...event_data
}
```

### Correlation ID Rules
1. **Gateway generates** initial `corr_id` for incoming webhooks
2. **Services preserve** `corr_id` when publishing derived events
3. **Idempotency key** maps to same `corr_id` for duplicate requests
4. **Format**: `{source}_{random_hex}` (e.g., `webhook_abc123def456`)

## Event Schemas

### 1. Market Signal (`signals.normalized`)

**Publisher**: at-gateway
**Schema Version**: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["corr_id", "instrument", "signal", "strength", "timestamp"],
  "properties": {
    "corr_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]{8,64}$"
    },
    "instrument": {
      "type": "string",
      "pattern": "^[A-Z]{2,10}(/[A-Z]{3,6})?$",
      "description": "Trading symbol (e.g., AAPL, EUR/USD)"
    },
    "signal": {
      "type": "string",
      "enum": ["buy", "sell", "hold", "close"],
      "description": "Trading signal direction"
    },
    "strength": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Signal confidence (0=weak, 1=strong)"
    },
    "price": {
      "type": "number",
      "minimum": 0,
      "description": "Current market price"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Signal generation time (ISO 8601)"
    },
    "source": {
      "type": "string",
      "enum": ["tradingview", "custom", "test", "ml_model"],
      "description": "Signal origin"
    },
    "metadata": {
      "type": "object",
      "additionalProperties": true,
      "description": "Additional signal context"
    }
  },
  "additionalProperties": true
}
```

### 2. Order Intent (`decisions.order_intent`)

**Publisher**: at-agent-mcp
**Schema Version**: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["corr_id", "agent_id", "instrument", "side", "quantity", "order_type", "timestamp"],
  "properties": {
    "corr_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]{8,64}$"
    },
    "agent_id": {
      "type": "string",
      "description": "Identifier of the deciding agent"
    },
    "instrument": {
      "type": "string",
      "pattern": "^[A-Z]{2,10}(/[A-Z]{3,6})?$"
    },
    "side": {
      "type": "string",
      "enum": ["buy", "sell"]
    },
    "quantity": {
      "type": "number",
      "minimum": 0.001,
      "description": "Order size"
    },
    "order_type": {
      "type": "string",
      "enum": ["market", "limit", "stop", "stop_limit"]
    },
    "price_limit": {
      "type": ["number", "null"],
      "description": "Limit price for limit orders"
    },
    "stop_price": {
      "type": ["number", "null"],
      "description": "Stop trigger price"
    },
    "time_in_force": {
      "type": "string",
      "enum": ["IOC", "FOK", "GTC", "GTD", "DAY"],
      "default": "DAY"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "risk_params": {
      "type": "object",
      "properties": {
        "max_position": {"type": "number"},
        "stop_loss": {"type": "number"},
        "take_profit": {"type": "number"},
        "max_slippage_bps": {"type": "number"}
      }
    },
    "strategy": {
      "type": "string",
      "description": "Strategy identifier"
    }
  },
  "additionalProperties": true
}
```

### 3. Execution Fill (`executions.fill`)

**Publisher**: at-exec-sim
**Schema Version**: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["corr_id", "fill_id", "instrument", "side", "quantity_filled", "avg_fill_price", "fill_status", "fill_timestamp"],
  "properties": {
    "corr_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]{8,64}$"
    },
    "fill_id": {
      "type": "string",
      "description": "Unique fill identifier"
    },
    "order_id": {
      "type": "string",
      "description": "Original order identifier"
    },
    "instrument": {
      "type": "string",
      "pattern": "^[A-Z]{2,10}(/[A-Z]{3,6})?$"
    },
    "side": {
      "type": "string",
      "enum": ["buy", "sell"]
    },
    "quantity_requested": {
      "type": "number",
      "minimum": 0
    },
    "quantity_filled": {
      "type": "number",
      "minimum": 0
    },
    "avg_fill_price": {
      "type": "number",
      "minimum": 0
    },
    "fill_status": {
      "type": "string",
      "enum": ["complete", "partial", "rejected", "cancelled"]
    },
    "rejection_reason": {
      "type": ["string", "null"],
      "description": "Reason if rejected"
    },
    "execution_venue": {
      "type": "string",
      "description": "Exchange or simulator"
    },
    "fill_timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "fees": {
      "type": "object",
      "properties": {
        "commission": {"type": "number"},
        "exchange_fee": {"type": "number"},
        "regulatory_fee": {"type": "number"}
      }
    },
    "slippage_bps": {
      "type": "number",
      "description": "Slippage in basis points"
    }
  },
  "additionalProperties": true
}
```

### 4. Position Reconciliation (`executions.reconcile`)

**Publisher**: at-exec-sim
**Schema Version**: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["corr_id", "reconcile_id", "instrument", "position_delta", "new_position", "reconcile_timestamp"],
  "properties": {
    "corr_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]{8,64}$"
    },
    "reconcile_id": {
      "type": "string",
      "description": "Unique reconciliation identifier"
    },
    "instrument": {
      "type": "string",
      "pattern": "^[A-Z]{2,10}(/[A-Z]{3,6})?$"
    },
    "position_delta": {
      "type": "number",
      "description": "Change in position (+ for buy, - for sell)"
    },
    "new_position": {
      "type": "number",
      "description": "Total position after reconciliation"
    },
    "avg_entry_price": {
      "type": "number",
      "minimum": 0
    },
    "realized_pnl": {
      "type": "number",
      "description": "Realized profit/loss if closing"
    },
    "unrealized_pnl": {
      "type": "number",
      "description": "Mark-to-market P&L"
    },
    "reconcile_timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "account_id": {
      "type": "string",
      "description": "Trading account identifier"
    }
  },
  "additionalProperties": true
}
```

### 5. Audit Event (`audit.event`)

**Publisher**: All services
**Schema Version**: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["event_id", "correlation_id", "event_type", "timestamp", "data"],
  "properties": {
    "event_id": {
      "type": "string",
      "description": "Unique audit event ID"
    },
    "correlation_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]{8,64}$"
    },
    "event_type": {
      "type": "string",
      "enum": ["webhook_received", "signal_published", "decision_made", "order_sent", "fill_received", "position_updated", "error_occurred"]
    },
    "service": {
      "type": "string",
      "description": "Service that generated the event"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "data": {
      "type": "object",
      "description": "Event payload"
    },
    "hash": {
      "type": "string",
      "description": "SHA256 hash of event"
    },
    "previous_hash": {
      "type": "string",
      "description": "Hash of previous event in chain"
    },
    "chain_position": {
      "type": "integer",
      "minimum": 1
    }
  },
  "additionalProperties": false
}
```

## REST API Contracts

### Gateway Webhook Endpoint

**POST** `/webhook/{source}`

#### Request Headers
```http
Content-Type: application/json
X-Timestamp: 1642250400
X-Nonce: unique-request-id
X-Signature: hmac_signature_hex
X-Idempotency-Key: optional-idempotency-key
```

#### Request Body
```json
{
  "instrument": "AAPL",
  "price": 150.25,
  "signal": "buy",
  "strength": 0.85,
  "metadata": {
    "strategy": "momentum",
    "timeframe": "5m"
  }
}
```

#### Response (200 OK)
```json
{
  "status": "accepted",
  "corr_id": "req_abc123def456",
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

#### Error Response (400/401/422)
```json
{
  "detail": "GW-001: Invalid signature",
  "corr_id": "req_abc123def456",
  "errors": [
    {
      "field": "X-Signature",
      "message": "HMAC validation failed"
    }
  ]
}
```

### Health Check Endpoints

**GET** `/healthz`

#### Response (200 OK - Healthy)
```json
{
  "ok": true,
  "uptime_s": 3600,
  "version": "1.0.0",
  "nats": "connected",
  "processor_status": "active",
  "consumer": {
    "status": "healthy",
    "durable_name": "exec-sim-consumer",
    "filter_subject": "decisions.order_intent",
    "num_pending": 0,
    "num_waiting": 1
  }
}
```

#### Response (503 Service Unavailable - Unhealthy)
```json
{
  "ok": false,
  "uptime_s": 3600,
  "version": "1.0.0",
  "nats": "disconnected",
  "processor_status": "stopped",
  "error": "NATS connection lost"
}
```

### Metrics Endpoint

**GET** `/metrics`

Returns Prometheus-formatted metrics:
```prometheus
# HELP gateway_webhooks_received_total Total webhooks received
# TYPE gateway_webhooks_received_total counter
gateway_webhooks_received_total{source="test",status="success"} 42.0

# HELP exec_sim_orders_received_total Total order intents received
# TYPE exec_sim_orders_received_total counter
exec_sim_orders_received_total{status="valid"} 38.0
exec_sim_orders_received_total{status="invalid"} 4.0
```

## Schema Evolution Guidelines

### Backward Compatible Changes (Minor Version)
✅ Adding optional fields
✅ Adding new enum values
✅ Relaxing validation constraints
✅ Adding new event types

### Breaking Changes (Major Version)
❌ Removing required fields
❌ Changing field types
❌ Renaming fields
❌ Tightening validation constraints

### Migration Strategy
```python
# Support multiple schema versions
SCHEMA_VERSIONS = {
    "1.0.0": schema_v1,
    "2.0.0": schema_v2
}

def validate_event(event, version="2.0.0"):
    # Try new version first
    if version in SCHEMA_VERSIONS:
        return validate(event, SCHEMA_VERSIONS[version])

    # Fallback to older versions
    for v in sorted(SCHEMA_VERSIONS.keys(), reverse=True):
        try:
            return validate(event, SCHEMA_VERSIONS[v])
        except ValidationError:
            continue

    raise ValidationError("No compatible schema version")
```

## Unknown Field Handling

Services MUST accept events with unknown fields but SHOULD log them:

```python
# Schema allows additional properties
"additionalProperties": true

# But track unknown fields
unknown_fields = set(event.keys()) - set(schema["properties"].keys())
if unknown_fields:
    metrics.unknown_fields.labels(
        service="my-service",
        event_type="order_intent"
    ).inc(len(unknown_fields))

    logger.info("Unknown fields in event",
               corr_id=event["corr_id"],
               unknown_fields=list(unknown_fields))
```

## Error Codes

### Gateway Errors (GW-XXX)
- `GW-001`: Invalid signature
- `GW-002`: Replay attack detected
- `GW-003`: Rate limit exceeded
- `GW-004`: Schema validation failed
- `GW-005`: Idempotency conflict
- `GW-006`: Unsupported webhook source
- `GW-007`: Source not allowed

### Execution Errors (EXEC-XXX)
- `EXEC-001`: Schema validation failed
- `EXEC-002`: Insufficient liquidity
- `EXEC-003`: Risk limit exceeded
- `EXEC-004`: Market closed
- `EXEC-005`: Invalid order type

### Agent Errors (AGENT-XXX)
- `AGENT-001`: Strategy not found
- `AGENT-002`: Risk check failed
- `AGENT-003`: Position limit exceeded
- `AGENT-004`: Model inference failed

## Testing Event Contracts

### Unit Test Example
```python
def test_order_intent_schema():
    """Test order intent schema validation"""
    valid_order = {
        "corr_id": "test_123",
        "agent_id": "test_agent",
        "instrument": "AAPL",
        "side": "buy",
        "quantity": 100,
        "order_type": "market",
        "timestamp": "2025-01-15T10:30:00Z"
    }

    # Should pass
    assert validate_schema(valid_order, ORDER_INTENT_SCHEMA)

    # Should accept unknown fields
    order_with_extra = {**valid_order, "custom_field": "value"}
    assert validate_schema(order_with_extra, ORDER_INTENT_SCHEMA)

    # Should fail without required fields
    invalid_order = {**valid_order}
    del invalid_order["corr_id"]
    with pytest.raises(ValidationError):
        validate_schema(invalid_order, ORDER_INTENT_SCHEMA)
```

### Contract Test Example
```bash
# Publish test event and verify consumption
docker run --rm --network agentic-trading-architecture-full_default \
  natsio/nats-box:latest \
  nats -s nats://nats:4222 pub decisions.order_intent \
  '{"corr_id":"contract_test_001","agent_id":"test","instrument":"AAPL","side":"buy","quantity":100,"order_type":"market","timestamp":"2025-01-15T10:30:00Z"}'

# Verify consumer received it
curl -s localhost:8004/metrics | grep 'exec_sim_orders_received_total'
```

## References

- [JSON Schema Draft 7](https://json-schema.org/draft-07/json-schema-release-notes.html)
- [NATS JetStream Documentation](https://docs.nats.io/nats-concepts/jetstream)
- [Semantic Versioning](https://semver.org/)
- [HTTP Status Codes](https://httpstatuses.com/)
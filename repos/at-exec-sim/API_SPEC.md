# Execution Simulator API Specification

## Base URL

`http://localhost:8004` (development)

The execution simulator operates primarily as a NATS consumer/producer service. It does not accept HTTP webhook requests but provides health and metrics endpoints for operational monitoring.

For complete error code reference, see [ERROR_CATALOG.md](ERROR_CATALOG.md). For operational procedures, see [RUNBOOK.md](RUNBOOK.md).

## Service Architecture

The execution simulator follows an event-driven architecture:

1. **NATS Consumer**: Subscribes to `decisions.order_intent` events
2. **Event Processor**: Validates and simulates execution
3. **NATS Producer**: Publishes `executions.fill` and `executions.reconcile` events
4. **HTTP Endpoints**: Health checks and metrics only

## NATS Event Contracts

### Input Events

#### decisions.order_intent
The service consumes order intent decisions from trading agents.

**Expected Schema** (from at-core):
```json
{
  "corr_id": "req_abc123",
  "agent_id": "momentum_agent_v1",
  "instrument": "EURUSD",
  "side": "buy",
  "quantity": 10000,
  "order_type": "market",
  "price_limit": null,
  "timestamp": "2024-01-15T10:30:00Z",
  "strategy": "momentum_breakout",
  "risk_params": {
    "max_slippage_bps": 5,
    "time_in_force": "IOC"
  }
}
```

**Required Fields**:
- `corr_id` (string): Correlation ID for tracing
- `agent_id` (string): Source agent identifier
- `instrument` (string): Trading instrument (EURUSD, BTC/USD, etc.)
- `side` (string): "buy" or "sell"
- `quantity` (number): Order size (positive)
- `order_type` (string): "market", "limit", "stop"
- `timestamp` (string): ISO8601 timestamp

### Output Events

#### executions.fill
Published when simulation completes successfully.

**Schema**:
```json
{
  "corr_id": "req_abc123",
  "fill_id": "fill_xyz789",
  "instrument": "EURUSD",
  "side": "buy",
  "quantity_requested": 10000,
  "quantity_filled": 8500,
  "avg_fill_price": 1.0947,
  "fill_status": "partial",
  "execution_venue": "simulator",
  "fill_timestamp": "2024-01-15T10:30:01.234Z",
  "simulation_metadata": {
    "delay_ms": 1250,
    "slippage_bps": 1.8,
    "partial_fill_reason": "liquidity_constraint"
  }
}
```

#### executions.reconcile
Published for position tracking and accounting.

**Schema**:
```json
{
  "corr_id": "req_abc123",
  "reconcile_id": "rec_456def",
  "agent_id": "momentum_agent_v1",
  "instrument": "EURUSD",
  "position_delta": 8500,
  "realized_pnl": 0.0,
  "unrealized_pnl": -15.30,
  "reconcile_timestamp": "2024-01-15T10:30:01.345Z",
  "reconcile_type": "execution"
}
```

## HTTP Endpoints

### GET /healthz

Service health check endpoint.

#### Response 200 (Healthy)
```json
{
  "ok": true,
  "uptime_s": 3600,
  "nats": "connected",
  "version": "1.0.0",
  "processor_status": "active",
  "pending_events": 5
}
```

#### Response 503 (Unhealthy)
```json
{
  "ok": false,
  "uptime_s": 3600,
  "nats": "disconnected",
  "version": "1.0.0",
  "processor_status": "stopped",
  "pending_events": 1000,
  "error": "NATS connection failed"
}
```

#### Response Fields
- `ok` (boolean): Overall service health
- `uptime_s` (integer): Seconds since service start
- `nats` (string): Connection status - "connected", "degraded", or "disconnected"
- `version` (string): Service version
- `processor_status` (string): Event processor status - "active", "stopped", "degraded"
- `pending_events` (integer): Number of buffered events awaiting processing

### GET /metrics

Prometheus metrics endpoint.

**Response**: Prometheus exposition format (text/plain)
**Authentication**: None required in development

#### Key Metrics
```
# Counter: Total order intents received
exec_sim_orders_received_total{status="success|validation_error|processing_error"}

# Counter: Total fills generated
exec_sim_fills_generated_total{fill_type="full|partial", instrument="EURUSD|BTC/USD|..."}

# Counter: Total reconcile events published
exec_sim_reconciles_generated_total{status="success|error"}

# Histogram: Simulation processing duration
exec_sim_simulation_duration_seconds{instrument="EURUSD|BTC/USD|..."}

# Counter: Schema validation errors
exec_sim_validation_errors_total{type="schema|correlation_id|instrument"}

# Counter: NATS publishing errors
exec_sim_nats_publish_errors_total{subject="executions.fill|executions.reconcile"}

# Gauge: Pending events in buffer
exec_sim_pending_events_count

# Gauge: Active processor threads
exec_sim_active_processors

# Counter: Simulation results by type
exec_sim_simulation_results_total{result="full_fill|partial_fill|rejected"}
```

## Simulation Behavior

### Fill Simulation Algorithm

1. **Validation**: Validate incoming order against schema
2. **Delay Simulation**: Random delay between `SIMULATION_MIN_DELAY_MS` and `SIMULATION_MAX_DELAY_MS`
3. **Slippage Calculation**: Random slippage up to `SIMULATION_SLIPPAGE_BPS`
4. **Partial Fill Decision**: Based on `SIMULATION_PARTIAL_FILL_CHANCE` probability
5. **Fill Generation**: Create fill event with simulated results
6. **Publishing**: Emit fill and reconcile events to NATS

### Partial Fill Logic
```python
# Simplified algorithm
if random() < SIMULATION_PARTIAL_FILL_CHANCE:
    fill_ratio = uniform(0.3, 0.95)  # 30-95% fill
    quantity_filled = quantity_requested * fill_ratio
    fill_status = "partial"
else:
    quantity_filled = quantity_requested
    fill_status = "full"
```

### Slippage Simulation
```python
# Market orders: simulate slippage
if order_type == "market":
    slippage_bps = uniform(0, SIMULATION_SLIPPAGE_BPS)
    if side == "buy":
        fill_price = market_price * (1 + slippage_bps / 10000)
    else:
        fill_price = market_price * (1 - slippage_bps / 10000)
```

## Error Handling

### Standard Error Response
NATS events that fail processing are logged but do not generate HTTP error responses. However, health checks and metrics reflect error states.

### Common Error Scenarios

#### Schema Validation Failure (EXEC-001)
**Trigger**: Incoming order intent doesn't match expected schema
**Action**: Log error, increment `exec_sim_validation_errors_total`, skip processing
**Output**: No fill or reconcile events generated

#### NATS Publishing Failure (EXEC-002)
**Trigger**: Cannot publish fill/reconcile events to NATS
**Action**: Buffer event for retry, log error, increment `exec_sim_nats_publish_errors_total`
**Recovery**: Retry publishing when NATS connectivity restored

#### Correlation ID Missing (EXEC-003)
**Trigger**: Order intent event lacks correlation ID
**Action**: Generate warning log, create synthetic correlation ID
**Output**: Process with synthetic ID for downstream tracing

## Event Processing Guarantees

### Delivery Semantics
- **At-least-once processing**: Events may be processed multiple times during failures
- **Idempotency**: Duplicate events with same correlation ID generate identical fills
- **Ordering**: No ordering guarantees across different instruments
- **Buffering**: Up to 1000 events buffered during NATS outages

### Failure Recovery
- **NATS Reconnection**: Automatic reconnection with exponential backoff
- **Event Replay**: Durable consumer ensures no event loss
- **Graceful Degradation**: Health endpoint reflects degraded state during issues

## Rate Limits

**Processing Capacity**: ~1000 orders/second sustained
**NATS Publishing**: Limited by NATS server capacity
**Memory Limit**: 1000 pending events maximum (fail-stop beyond limit)

## Observability

### Correlation ID Propagation
- Preserve correlation ID from input `decisions.order_intent`
- Include in all output events (`executions.fill`, `executions.reconcile`)
- Add to all log entries for distributed tracing

### Structured Logging Example
```json
{
  "timestamp": "2024-01-15T10:30:01.234Z",
  "level": "INFO",
  "service": "at-exec-sim",
  "corr_id": "req_abc123",
  "event_type": "fill_generated",
  "message": "Market order fill simulated",
  "metadata": {
    "instrument": "EURUSD",
    "side": "buy",
    "quantity_requested": 10000,
    "quantity_filled": 8500,
    "simulation_delay_ms": 1250,
    "fill_status": "partial"
  }
}
```

### Performance Monitoring
- **Latency**: Track simulation processing time per instrument
- **Throughput**: Monitor orders processed per second
- **Error Rate**: Track validation and publishing failures
- **Resource Usage**: Memory and CPU utilization tracking
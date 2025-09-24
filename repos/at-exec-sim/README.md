# at-exec-sim

## Purpose

The execution simulator service consumes order intent decisions from agents and simulates realistic execution fills. It validates incoming `decisions.order_intent` events, simulates market execution with realistic delays and partial fills, then publishes both `executions.fill` and `executions.reconcile` events via NATS. The simulator provides a stateless execution environment for testing trading strategies without connecting to real brokers.

**Responsibilities:**
- Consume `decisions.order_intent` events from NATS
- Validate order decisions against at-core schemas
- Simulate realistic execution timing and partial fills
- Generate `executions.fill` events for successful simulations
- Emit `executions.reconcile` events for position tracking
- Provide execution metrics and observability

**Non-responsibilities:**
- Making trading decisions or strategy logic
- Persistent storage of execution history
- Real broker/exchange connectivity
- Risk management or position limits
- Order routing or smart execution

## Data Flow

Agents publish order intent decisions to NATS. The execution simulator consumes these events, validates the order details, simulates market execution with realistic delays, and publishes fill confirmations back to NATS for consumption by downstream services.

```
Agents → decisions.order_intent → NATS → Validate → Simulate → executions.fill/reconcile
                                    ↓                      ↓
                              Schema validation    Random delays,
                              Correlation ID       partial fills,
                              propagation         slippage simulation
```

## Quick Start

### Python Environment
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn at_exec_sim.app:app --port 8004 --reload
```

### Infrastructure
```bash
docker compose -f ../../docker-compose.dev.yml up -d nats prom grafana
```

## Environment Variables

| Variable | Sample Value | Description |
|----------|--------------|-------------|
| `SERVICE_NAME` | `at-exec-sim` | Service identifier for logs/metrics |
| `PORT` | `8004` | HTTP server port for health/metrics endpoints |
| `NATS_URL` | `nats://localhost:4222` | NATS server connection |
| `NATS_STREAM` | `trading-events` | JetStream stream name |
| `NATS_DURABLE` | `exec-sim-consumer` | Durable consumer name |
| `NATS_SUBJECT_ORDER_INTENT` | `decisions.order_intent` | Order intent subscription subject |
| `NATS_SUBJECT_FILL` | `executions.fill` | Fill event publication subject |
| `NATS_SUBJECT_RECONCILE` | `executions.reconcile` | Reconcile event publication subject |
| `API_KEY_HMAC_SECRET` | `your-secret-key` | HMAC secret for event validation |
| `IDEMPOTENCY_TTL_SEC` | `3600` | Duplicate detection window |
| `RATE_LIMIT_RPS` | `100` | Events per second processing limit |
| `REPLAY_WINDOW_SEC` | `300` | Event replay tolerance window |
| `SIMULATION_MIN_DELAY_MS` | `100` | Minimum execution delay simulation |
| `SIMULATION_MAX_DELAY_MS` | `2000` | Maximum execution delay simulation |
| `SIMULATION_PARTIAL_FILL_CHANCE` | `0.1` | Probability of partial fill (0.0-1.0) |
| `SIMULATION_SLIPPAGE_BPS` | `2` | Maximum slippage in basis points |
| `PROMETHEUS_MULTIPROC_DIR` | `/tmp/prometheus_multiproc` | Prometheus metrics directory |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENV` | `development` | Environment name |

**Simulation Parameters**: Control execution realism. Higher delays and slippage create more realistic market conditions for strategy testing.

## Contracts Overview

The execution simulator strictly validates incoming events using schemas from at-core and produces standardized execution events. All schemas follow [ADR-0002](../../DECISIONS/ADR-0002-event-contracts.md) versioning policy.

**Input**: `decisions.order_intent` - Order decisions from trading agents
**Output**: `executions.fill` and `executions.reconcile` - Simulated execution results

## Security Model

- **Schema validation**: All incoming events validated against at-core schemas
- **Correlation ID tracking**: Request tracing through execution pipeline
- **Request limits**: 1MB max event payload size
- **Error isolation**: Invalid events logged but don't affect other processing
- **Stateless design**: No persistent state reduces attack surface

## Observability

Follows [ADR-0003](../../DECISIONS/ADR-0003-observability.md) conventions:

**Key metrics**:
- `exec_sim_orders_received_total{status}`
- `exec_sim_fills_generated_total{fill_type}`
- `exec_sim_simulation_duration_seconds`
- `exec_sim_validation_errors_total{type}`

**Log fields**: `corr_id`, `instrument`, `order_type`, `simulation_delay_ms`, `fill_status`

**Endpoints**:
- `GET /healthz` - Service health and NATS connectivity
- `GET /metrics` - Prometheus metrics

## Failure Modes & Policies

### NATS Unavailable (Fail-Stop)
When NATS is unreachable, the execution simulator operates in **fail-stop** mode:
- Stops processing new order intents
- Returns 503 for health checks with `nats: "disconnected"`
- Buffers up to 1000 pending events in memory
- Resumes processing when NATS connectivity restored

**Rationale**: Execution simulation requires guaranteed event delivery; better to pause than lose execution confirmations.

### Schema Validation Failures
- Log validation errors with correlation ID and schema version
- Increment `exec_sim_validation_errors_total` metric
- Continue processing valid events (isolation)
- No execution events generated for invalid orders

## Limitations & TODOs

- **Market hours simulation**: Currently operates 24/7; needs market calendar integration
- **Advanced slippage models**: Uses simple random slippage; needs volatility-based models
- **Latency simulation**: Fixed delay ranges; needs market condition dependent latency
- **Liquidity simulation**: No depth/size restrictions; assumes infinite liquidity
- **Event replay**: No replay capability for failed simulations
- **Performance tuning**: Single-threaded processing; consider async execution pools
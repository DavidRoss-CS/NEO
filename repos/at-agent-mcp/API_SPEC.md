# at-agent-mcp API Specification

## Overview

The at-agent-mcp service implements autonomous trading agents using the Model Context Protocol (MCP). It consumes normalized market signals and generates trading decisions based on configurable strategies.

## Service Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://localhost:4222` | NATS server connection |
| `NATS_STREAM` | `trading-events` | JetStream stream name |
| `SERVICE_NAME` | `at-agent-mcp` | Service identifier |
| `AGENT_ID` | `agent_{random}` | Unique agent identifier |
| `STRATEGY_TYPE` | `momentum` | Strategy type: momentum, mean_reversion, hybrid |
| `RISK_LIMIT` | `0.02` | Maximum risk per trade (2%) |
| `CONFIDENCE_THRESHOLD` | `0.7` | Minimum signal confidence to act |
| `MAX_POSITIONS` | `5` | Maximum concurrent positions |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `PORT` | `8002` | HTTP server port |

## HTTP API

### Health Check

**GET /healthz**

Returns service health status.

**Response**:
```json
{
  "ok": true,
  "service": "at-agent-mcp",
  "agent_id": "agent_abc123",
  "strategy": "momentum",
  "uptime_seconds": 3600,
  "nats_connected": true,
  "active_positions": 3,
  "signals_buffered": 75
}
```

**Status Codes**:
- 200: Service healthy
- 503: Service degraded (NATS disconnected)

### Metrics

**GET /metrics**

Prometheus metrics endpoint.

**Response**: Prometheus text format

### Status

**GET /status**

Detailed agent status and configuration.

**Response**:
```json
{
  "agent_id": "agent_abc123",
  "strategy": {
    "type": "momentum",
    "risk_limit": 0.02,
    "confidence_threshold": 0.7,
    "max_positions": 5
  },
  "positions": {
    "EURUSD": {
      "side": "buy",
      "quantity": 10000,
      "timestamp": "2024-01-15T10:30:00Z"
    }
  },
  "metrics": {
    "signals_received": 150,
    "active_positions": 1
  },
  "health": {
    "nats_connected": true,
    "uptime_seconds": 3600
  }
}
```

### Clear Positions

**POST /positions/clear**

Clears all tracked positions (admin endpoint).

**Response**:
```json
{
  "status": "cleared",
  "positions_cleared": 3
}
```

## NATS Event Consumption

### Signals Consumption

**Subject**: `signals.normalized`
**Consumer**: `mcp-agent-consumer`
**Durable**: Yes
**Manual Ack**: Yes

**Expected Schema**: signals.normalized.schema.json

**Example Signal**:
```json
{
  "corr_id": "req_abc123",
  "timestamp": "2024-01-15T10:30:00Z",
  "instrument": "EURUSD",
  "signal_type": "bullish_momentum",
  "strength": 0.85,
  "price": 1.0895,
  "source": "tradingview",
  "metadata": {}
}
```

## NATS Event Production

### Order Intent Publication

**Subject**: `decisions.order_intent`
**Schema**: decisions.order_intent.schema.json

**Headers**:
- `Corr-ID`: Correlation ID from signal
- `Agent-ID`: Agent identifier
- `Strategy`: Strategy identifier

**Example Decision**:
```json
{
  "corr_id": "req_abc123",
  "strategy_id": "momentum_v1",
  "agent_id": "agent_abc123",
  "timestamp": "2024-01-15T10:30:05Z",
  "instrument": "EURUSD",
  "side": "buy",
  "order_type": "market",
  "quantity": 10000,
  "confidence": 0.85,
  "reasoning": "Strong bullish momentum detected",
  "risk_score": 3.5,
  "signal_refs": ["req_abc123"]
}
```

## Trading Strategies

### Momentum Strategy

**Strategy ID**: `momentum_v1`
**Logic**: Follows strong directional signals

**Signal Analysis**:
- Looks for "bullish", "bearish", "buy", "sell" in signal_type
- Boosts confidence by 10% for momentum trades
- Uses market orders for immediate execution

**Decision Criteria**:
- Signal strength >= confidence_threshold
- Available position slots
- Clear directional indication

### Mean Reversion Strategy

**Strategy ID**: `mean_reversion_v1`
**Logic**: Trades against price extremes

**Signal Analysis**:
- Maintains 100-signal price buffer
- Calculates Z-score vs rolling mean
- Trades when Z-score > ±2.0 standard deviations

**Decision Criteria**:
- Minimum 20 signals for analysis
- Z-score exceeds threshold
- Uses limit orders near current price

### Hybrid Strategy

**Strategy ID**: `hybrid_v1`
**Logic**: Combines momentum and mean reversion

**Signal Analysis**:
- Runs both momentum and mean reversion
- Requires strategy agreement for action
- Averages confidence when both agree

**Decision Criteria**:
- Both strategies must agree on direction
- Higher combined confidence
- Skips on strategy disagreement

## Risk Management

### Position Sizing

```python
position_size = base_size * signal_strength * risk_limit * 10
```

- Base size: 10,000 units
- Scaled by signal strength (0-1)
- Limited by risk_limit parameter

### Risk Scoring

```python
risk_score = base_risk + order_type_adj + confidence_adj
```

- Base risk: 5.0 (medium)
- Market orders: +1.0 risk
- Low confidence: +3.0 risk
- Range: 0-10

### Position Limits

- Maximum concurrent positions: MAX_POSITIONS
- No new positions when limit reached
- Positions tracked by instrument

## Metrics

### Counters
- `mcp_signals_received_total{instrument, signal_type}`
- `mcp_decisions_generated_total{strategy, side}`
- `mcp_errors_total{error_type}`

### Histograms
- `mcp_strategy_confidence{strategy}`
- `mcp_processing_duration_seconds{strategy}`

### Gauges
- `mcp_active_positions`
- `mcp_nats_connected`

## Error Handling

### Signal Processing Errors

1. **Schema Validation**: Logs error, doesn't ack message
2. **Strategy Failures**: Logs error, acks message to prevent retry
3. **NATS Publish Failures**: Logs error, doesn't ack message

### Connection Handling

1. **NATS Disconnection**: Sets health status to unhealthy
2. **Reconnection**: Automatic via nats-py client
3. **Startup Failures**: Service starts but marks unhealthy

## Development

### Local Development

```bash
cd repos/at-agent-mcp
export NATS_URL="nats://localhost:4222"
export STRATEGY_TYPE="momentum"
python -m uvicorn at_agent_mcp.app:app --port 8002 --reload
```

### Docker Development

```bash
docker build -t at-agent-mcp .
docker run -p 8002:8002 -e NATS_URL="nats://host.docker.internal:4222" at-agent-mcp
```

### Testing Strategies

```python
from at_agent_mcp.app import StrategyEngine

engine = StrategyEngine("momentum", 0.02)
signal = {
    "instrument": "EURUSD",
    "signal_type": "bullish_momentum",
    "strength": 0.8,
    "price": 1.0900,
    "corr_id": "test_123"
}

decision = await engine.analyze_signal(signal)
print(decision)
```

## Integration Examples

### Signal Producer (at-gateway)

```python
# Publish signal that agent will consume
await js_client.publish(
    "signals.normalized",
    json.dumps(signal).encode(),
    headers={"Corr-ID": corr_id}
)
```

### Decision Consumer (at-exec-sim)

```python
# Subscribe to agent decisions
await js_client.subscribe(
    "decisions.order_intent",
    cb=handle_order_intent
)
```

## Configuration Examples

### Conservative Agent

```bash
CONFIDENCE_THRESHOLD=0.8
RISK_LIMIT=0.01
MAX_POSITIONS=3
STRATEGY_TYPE=mean_reversion
```

### Aggressive Agent

```bash
CONFIDENCE_THRESHOLD=0.6
RISK_LIMIT=0.05
MAX_POSITIONS=10
STRATEGY_TYPE=momentum
```

### Balanced Agent

```bash
CONFIDENCE_THRESHOLD=0.7
RISK_LIMIT=0.02
MAX_POSITIONS=5
STRATEGY_TYPE=hybrid
```
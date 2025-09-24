# Agent MCP Prometheus Metrics

This document describes all metrics exported by the at-agent-mcp service on `/metrics` endpoint.

## Counters

### `mcp_signals_received_total`
**Description**: Total number of trading signals received from NATS
**Type**: Counter
**Labels**:
- `instrument` - Trading instrument (e.g., AAPL, BTCUSD)
- `signal_type` - Type of signal (BUY, SELL, HOLD)

**Example**:
```
mcp_signals_received_total{instrument="AAPL",signal_type="BUY"} 12.0
```

### `mcp_decisions_generated_total`
**Description**: Total number of trading decisions generated
**Type**: Counter
**Labels**:
- `strategy` - Strategy used (e.g., momentum_v1, mean_reversion_v1)
- `side` - Trading side (buy, sell)

**Example**:
```
mcp_decisions_generated_total{side="TradingSide.BUY",strategy="momentum_v1"} 4.0
```

### `mcp_errors_total`
**Description**: Total number of errors encountered
**Type**: Counter
**Labels**:
- `error_type` - Type of error (validation, nats, strategy, etc.)

## Histograms

### `mcp_strategy_confidence`
**Description**: Distribution of strategy confidence scores
**Type**: Histogram
**Labels**:
- `strategy` - Strategy name

**Buckets**: Default Prometheus buckets (0.005 to 10.0)

### `mcp_processing_duration_seconds`
**Description**: Time taken to process each signal
**Type**: Histogram
**Labels**:
- `strategy` - Strategy used for processing

**Buckets**: Default Prometheus buckets
**Metrics Generated**:
- `mcp_processing_duration_seconds_count` - Total number of processed signals
- `mcp_processing_duration_seconds_sum` - Total processing time
- `mcp_processing_duration_seconds_bucket` - Histogram buckets

**Example**:
```
mcp_processing_duration_seconds_count{strategy="momentum"} 12.0
mcp_processing_duration_seconds_sum{strategy="momentum"} 0.245
```

## Gauges

### `mcp_active_positions`
**Description**: Current number of active trading positions
**Type**: Gauge

**Example**:
```
mcp_active_positions 3.0
```

### `mcp_nats_connected`
**Description**: NATS connection status (1=connected, 0=disconnected)
**Type**: Gauge

**Example**:
```
mcp_nats_connected 1.0
```

## Configuration Metrics

The following environment variables affect metric collection:

- `STRATEGY_TYPE` - Default strategy for labeling (default: "momentum")
- `AGENT_ID` - Agent identifier included in decisions
- `CONFIDENCE_THRESHOLD` - Minimum confidence for decision generation

## Grafana Queries

### Signal Processing Rate
```promql
rate(mcp_signals_received_total[5m])
```

### Decision Generation Rate
```promql
rate(mcp_decisions_generated_total[5m])
```

### Processing Latency P95
```promql
histogram_quantile(0.95, rate(mcp_processing_duration_seconds_bucket[5m]))
```

### Error Rate
```promql
rate(mcp_errors_total[5m])
```

### Strategy Confidence Average
```promql
rate(mcp_strategy_confidence_sum[5m]) / rate(mcp_strategy_confidence_count[5m])
```

## Alerting Rules

### High Error Rate
```yaml
- alert: AgentHighErrorRate
  expr: rate(mcp_errors_total[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "Agent error rate is high"
```

### Low Decision Rate
```yaml
- alert: AgentLowDecisionRate
  expr: rate(mcp_decisions_generated_total[5m]) < 0.01
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Agent decision generation rate is low"
```

### NATS Disconnected
```yaml
- alert: AgentNATSDisconnected
  expr: mcp_nats_connected == 0
  for: 30s
  labels:
    severity: critical
  annotations:
    summary: "Agent NATS connection lost"
```
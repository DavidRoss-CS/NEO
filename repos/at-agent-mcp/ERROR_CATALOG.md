# MCP Agent Error Catalog

| Code | HTTP Status | Title | When It Happens | Operator Fix | Client Fix | Telemetry |
|------|-------------|-------|-----------------|--------------|------------|----------|
| MCP-001 | N/A | Schema validation failed | Incoming signal doesn't match expected schema | Check at-core schema version compatibility | Ensure signal follows signals.normalized schema | `mcp_errors_total{error_type="validation"}`, log: `corr_id`, `validation_errors`, `schema_version` |
| MCP-002 | N/A | NATS connection failed | Cannot connect to NATS server on startup | Check NATS server status and connectivity | Wait for service recovery | `mcp_nats_connected=0`, `mcp_errors_total{error_type="startup"}`, log: `nats_url`, `error_details` |
| MCP-003 | N/A | Signal processing error | Exception during signal analysis | Check strategy logic and data quality | Retry signal submission | `mcp_errors_total{error_type="signal_processing"}`, log: `corr_id`, `error`, `signal_data` |
| MCP-004 | N/A | Position limit exceeded | Max positions reached for risk management | Increase MAX_POSITIONS or close positions | Wait for positions to clear | `mcp_active_positions`, log: `current_positions`, `max_positions`, `instrument` |
| MCP-005 | N/A | Confidence below threshold | Signal strength below minimum confidence | Lower CONFIDENCE_THRESHOLD if appropriate | Send stronger signals | log: `strength`, `threshold`, `instrument`, `signal_type` |
| MCP-006 | N/A | Strategy execution failed | Error in strategy calculation | Review strategy parameters and logic | No client action needed | `mcp_errors_total{error_type="strategy"}`, log: `strategy_type`, `error_details`, `corr_id` |
| MCP-007 | N/A | NATS publish failed | Cannot publish decision to NATS | Check NATS connection and stream health | Retry after recovery | `mcp_errors_total{error_type="publish"}`, log: `corr_id`, `subject`, `retry_attempts` |
| MCP-008 | N/A | Invalid instrument format | Instrument identifier doesn't match pattern | Review instrument naming conventions | Use standard format (EURUSD, BTC/USD) | `mcp_errors_total{error_type="instrument"}`, log: `invalid_instrument`, `expected_pattern` |
| MCP-009 | N/A | Risk limit exceeded | Position would exceed risk parameters | Adjust RISK_LIMIT or position sizing | Reduce order quantity | log: `risk_score`, `risk_limit`, `proposed_position` |
| MCP-010 | N/A | Insufficient signal data | Not enough historical data for analysis | Wait for more signals to accumulate | Continue sending signals | log: `buffer_size`, `required_size`, `strategy_type` |
| MCP-011 | 503 | Service degraded | NATS connected but high error rate | Check logs for specific errors | Retry with exponential backoff | `mcp_errors_total`, health endpoint: `ok=false`, log: `error_rate`, `degradation_reason` |
| MCP-012 | 503 | Service unavailable | NATS disconnected after startup | Restore NATS connectivity | Wait for service recovery | `mcp_nats_connected=0`, health endpoint: `nats_connected=false` |

## Strategy-Specific Errors

### Momentum Strategy
| Code | Title | When It Happens | Resolution |
|------|-------|-----------------|------------|
| MCP-M01 | No directional signal | Signal lacks clear buy/sell indication | Ensure signal_type contains directional keywords |
| MCP-M02 | Momentum window insufficient | Not enough recent signals for momentum calc | Wait for momentum_window signals |

### Mean Reversion Strategy
| Code | Title | When It Happens | Resolution |
|------|-------|-----------------|------------|
| MCP-MR01 | Insufficient price history | <20 signals in buffer | Wait for more signals |
| MCP-MR02 | Zero standard deviation | All prices identical | Normal market conditions needed |
| MCP-MR03 | Z-score within threshold | Price not extreme enough | Wait for larger deviations |

### Hybrid Strategy
| Code | Title | When It Happens | Resolution |
|------|-------|-----------------|------------|
| MCP-H01 | Strategy disagreement | Momentum and mean reversion conflict | No action - designed behavior |
| MCP-H02 | Both strategies null | Neither strategy generates decision | Send stronger signals |

## Metrics and Monitoring

### Key Metrics
- `mcp_signals_received_total{instrument, signal_type}` - Signal ingestion rate
- `mcp_decisions_generated_total{strategy, side}` - Decision generation rate
- `mcp_strategy_confidence{strategy}` - Confidence distribution
- `mcp_processing_duration_seconds{strategy}` - Processing latency
- `mcp_active_positions` - Current position count
- `mcp_errors_total{error_type}` - Error rates by type
- `mcp_nats_connected` - NATS connection status (0/1)

### Health Check Response Examples

#### Healthy
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

#### NATS Disconnected
```json
{
  "ok": false,
  "service": "at-agent-mcp",
  "agent_id": "agent_abc123",
  "strategy": "momentum",
  "uptime_seconds": 3600,
  "nats_connected": false,
  "error": "NATS disconnected"
}
```

## Log Examples

### MCP-003: Signal Processing Error
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "ERROR",
  "service": "at-agent-mcp",
  "error_code": "MCP-003",
  "corr_id": "req_xyz789",
  "message": "Error processing signal",
  "error": "KeyError: 'price'",
  "signal_data": {
    "instrument": "EURUSD",
    "signal_type": "bullish"
  }
}
```

### MCP-004: Position Limit Exceeded
```json
{
  "timestamp": "2024-01-15T10:31:00.456Z",
  "level": "WARNING",
  "service": "at-agent-mcp",
  "error_code": "MCP-004",
  "message": "Max positions reached",
  "current_positions": 5,
  "max_positions": 5,
  "instrument": "GBPUSD"
}
```

## Recovery Procedures

### NATS Connection Issues
1. Check NATS server status: `nats-server --version`
2. Verify network connectivity to NATS_URL
3. Check JetStream stream exists: `nats stream ls`
4. Restart agent service if needed

### High Error Rate
1. Check specific error types in metrics
2. Review recent logs for patterns
3. Verify signal schema compatibility
4. Check strategy parameters are valid

### Position Management
1. GET /status - View current positions
2. POST /positions/clear - Clear all positions (admin)
3. Adjust MAX_POSITIONS environment variable
4. Restart service to apply changes
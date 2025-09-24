# Execution Simulator Error Catalog

| Code | HTTP Status | Title | When It Happens | Operator Fix | Client Fix | Telemetry |
|------|-------------|-------|-----------------|--------------|------------|----------|
| EXEC-001 | N/A | Schema validation failed | Order intent event doesn't match expected schema | Check at-core schema version compatibility | Fix event structure per schema definition | `exec_sim_validation_errors_total{type="schema"}`, `exec_sim_orders_received_total{status="validation_error"}`, log: `corr_id`, `validation_errors`, `schema_version` |
| EXEC-002 | N/A | NATS publish failed | Cannot publish fill or reconcile events to NATS | Check NATS server status and connectivity | Retry order submission after recovery | `exec_sim_nats_publish_errors_total{subject}`, log: `corr_id`, `nats_status`, `retry_attempts`, `error_details` |
| EXEC-003 | N/A | Correlation ID missing | Order intent lacks correlation ID for tracing | No action needed, synthetic ID generated | Include correlation ID in all events | `exec_sim_validation_errors_total{type="correlation_id"}`, log: `synthetic_corr_id`, `original_event` |
| EXEC-004 | N/A | Invalid instrument format | Instrument identifier doesn't match expected pattern | Review instrument naming conventions | Use standard instrument format (EURUSD, BTC/USD) | `exec_sim_validation_errors_total{type="instrument"}`, log: `corr_id`, `invalid_instrument`, `expected_pattern` |
| EXEC-005 | N/A | Invalid order type | Order type not in supported list | Check for new order type requirements | Use supported types: market, limit, stop | `exec_sim_validation_errors_total{type="order_type"}`, log: `corr_id`, `invalid_order_type`, `supported_types` |
| EXEC-006 | N/A | Buffer overflow | Event buffer exceeded maximum capacity | Restore NATS connectivity or increase buffer | Reduce event submission rate temporarily | `exec_sim_buffer_overflow_total`, log: `buffer_size`, `max_capacity`, `dropped_events` |
| EXEC-007 | N/A | Simulation timeout | Simulation took longer than maximum allowed time | Check system resources and simulation config | No client action, retry automatically | `exec_sim_simulation_timeout_total`, log: `corr_id`, `simulation_duration`, `timeout_limit` |
| EXEC-008 | N/A | Consumer lag critical | NATS consumer lag exceeds threshold | Scale service or optimize processing | Reduce order submission rate | `exec_sim_consumer_lag_critical_total`, log: `lag_messages`, `threshold`, `consumer_name` |
| EXEC-009 | N/A | Invalid quantity | Order quantity is zero, negative, or non-numeric | No operator action unless persistent | Ensure quantity is positive number | `exec_sim_validation_errors_total{type="quantity"}`, log: `corr_id`, `invalid_quantity`, `instrument` |
| EXEC-010 | N/A | Duplicate order processing | Same correlation ID processed multiple times | Check for duplicate event publishing | Ensure unique correlation IDs | `exec_sim_duplicate_orders_total`, log: `corr_id`, `previous_fill_id`, `duplicate_count` |
| EXEC-011 | 503 | Service degraded | NATS connected but high error rate or latency | Check NATS health and network stability | Retry with exponential backoff | `exec_sim_service_degraded_total`, health endpoint: `processor_status="degraded"`, log: `degradation_reason` |
| EXEC-012 | 503 | Service unavailable | NATS disconnected, cannot process events | Restore NATS connectivity | Wait for service recovery | `exec_sim_service_unavailable_total`, health endpoint: `ok=false`, log: `nats_status="disconnected"` |

## Latency Telemetry

All event processing must record duration in `exec_sim_simulation_duration_seconds` histogram with labels:
- `instrument`: Trading instrument being simulated
- `order_type`: Type of order (market, limit, stop)
- `fill_status`: Result of simulation (full, partial, rejected)

Duration measurement starts at event consumption and ends at fill/reconcile publication. Include validation, simulation, and publishing time.

## Error Response Examples

### EXEC-001: Schema Validation Failed
**Log Entry**:
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "ERROR",
  "service": "at-exec-sim",
  "error_code": "EXEC-001",
  "corr_id": "req_abc123",
  "message": "Order intent schema validation failed",
  "metadata": {
    "validation_errors": [
      "Field 'quantity' must be positive number",
      "Field 'instrument' format invalid"
    ],
    "schema_version": "1.0.0"
  }
}
```

### EXEC-002: NATS Publish Failed
**Log Entry**:
```json
{
  "timestamp": "2024-01-15T10:30:01.234Z",
  "level": "ERROR",
  "service": "at-exec-sim",
  "error_code": "EXEC-002",
  "corr_id": "req_abc123",
  "message": "Failed to publish fill event to NATS",
  "metadata": {
    "subject": "executions.fill",
    "nats_status": "disconnected",
    "retry_attempts": 3,
    "error_details": "Connection refused"
  }
}
```

### EXEC-006: Buffer Overflow
**Log Entry**:
```json
{
  "timestamp": "2024-01-15T10:30:02.345Z",
  "level": "CRITICAL",
  "service": "at-exec-sim",
  "error_code": "EXEC-006",
  "message": "Event buffer overflow, dropping events",
  "metadata": {
    "buffer_size": 1000,
    "max_capacity": 1000,
    "dropped_events": 5,
    "oldest_event_age_ms": 30000
  }
}
```

## Error Aggregation Rules

### High Error Rate Alert
Trigger when error rate exceeds thresholds:
```promql
# Alert if validation errors >5% of total orders for 5 minutes
rate(exec_sim_validation_errors_total[5m])
/
rate(exec_sim_orders_received_total[5m]) > 0.05
```

### NATS Publishing Failures
Monitor publishing reliability:
```promql
# Alert if NATS publishing fails >1% for 2 minutes
rate(exec_sim_nats_publish_errors_total[2m]) > 0.01
```

### Buffer Overflow Warning
Detect buffer pressure:
```promql
# Warn if buffer >80% capacity
exec_sim_pending_events_count > 800
```

## Recovery Procedures

### EXEC-001 Recovery
1. Check at-core schema version in logs
2. Verify agent event format compliance
3. Update service if schema mismatch
4. Monitor validation success rate

### EXEC-002 Recovery
1. Verify NATS server status: `nats server check`
2. Check network connectivity to NATS
3. Restart NATS if necessary
4. Monitor publishing success metrics

### EXEC-006 Recovery
1. **Immediate**: Restore NATS connectivity
2. **Short-term**: Monitor buffer drain rate
3. **Long-term**: Increase buffer size or add backpressure
4. **Prevention**: Implement rate limiting at source

## Error Code Reservation

Reserved ranges for future expansion:
- EXEC-013 to EXEC-020: Reserved for additional validation errors
- EXEC-021 to EXEC-030: Reserved for simulation logic errors
- EXEC-031 to EXEC-040: Reserved for reconciliation errors
- EXEC-041 to EXEC-050: Reserved for performance/resource errors

## Correlation and Tracing

All errors must include:
1. **Correlation ID**: From original order intent or synthetically generated
2. **Timestamp**: When error occurred
3. **Service context**: Service name, version, environment
4. **Error metadata**: Specific details about the failure

Example correlation flow:
```
Order Intent (corr_id: req_123)
  → Validation Error (EXEC-001, corr_id: req_123)
    → Logged with full context
    → Metric incremented
    → No downstream events
```

## Client Error Handling

Clients consuming from `executions.fill` should:
1. Implement timeout for expected fills (recommended: 10 seconds)
2. Check correlation IDs to match orders with fills
3. Handle partial fills appropriately
4. Retry order submission on timeout (with new correlation ID)

## Monitoring Dashboard

Key error metrics to display:
1. **Error rate by type**: Stacked graph of EXEC-xxx error codes
2. **Validation failures**: Breakdown by validation type
3. **NATS health**: Publishing success/failure rates
4. **Buffer utilization**: Current vs maximum capacity
5. **Processing latency**: p50, p95, p99 percentiles
# ADR-0003: Observability

## Status
Accepted

## Context

A distributed trading system with autonomous agents requires comprehensive observability to:
- Quickly diagnose issues during market hours when every second counts
- Track agent performance and decision quality over time
- Meet regulatory requirements for trade audit trails
- Enable data-driven optimization of strategies and execution
- Provide clear operational runbooks for incident response

Without proper observability, system failures can result in significant financial losses and regulatory violations.

## Decision

We will implement a standardized observability stack across all repositories:

### Metrics (Prometheus)
**Standard metric naming**: `{service}_{event}_{type}`
- Counters: `gateway_webhooks_received_total`, `agent_decisions_generated_total`
- Histograms: `execution_fill_duration_seconds`, `signal_processing_duration_seconds`
- Gauges: `agent_active_positions`, `nats_consumer_lag_messages`

**Required metrics per service**:
- Request/event counters with status labels
- Duration histograms for all async operations
- Error rate counters with error type classification
- Business metrics (positions, PnL, signal accuracy)

### Logging (Structured JSON)
**Standard fields**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "at-gateway",
  "corr_id": "req_123456789",
  "event_type": "webhook_received",
  "message": "TradingView webhook processed",
  "metadata": {
    "source": "tradingview",
    "instrument": "EURUSD",
    "latency_ms": 45
  }
}
```

**Correlation ID propagation**:
- Generated at system entry points (webhooks, API calls)
- Passed through all NATS events in headers
- Included in all log entries for request tracing

### Dashboards (Grafana)
**Standard dashboard structure**:
1. **System Health**: Service status, error rates, latency percentiles
2. **Business Metrics**: Active strategies, PnL, position sizes
3. **Infrastructure**: NATS lag, message rates, resource utilization
4. **Alerts**: Critical issues requiring immediate attention

### Alerting Rules
**Critical alerts** (immediate response):
- Service down for >2 minutes
- Error rate >5% for >5 minutes
- NATS consumer lag >1000 messages
- Execution latency >10 seconds

**Warning alerts** (business hours response):
- Unusual strategy performance deviation
- High resource utilization
- Deprecated schema usage

### Trace IDs
- Use `corr_id` for distributed tracing
- Include in all NATS message headers
- Log at service boundaries (ingress/egress)
- Propagate through agent decision chains

## Consequences

### Positive
- **Fast incident resolution**: Correlation IDs enable quick problem isolation
- **Data-driven optimization**: Rich metrics support strategy improvement
- **Regulatory compliance**: Complete audit trails for all trades
- **Operational confidence**: Clear health indicators and runbooks

### Negative
- **Performance overhead**: Logging and metrics collection adds latency
- **Storage costs**: Metrics and logs require significant storage
- **Alert fatigue**: Too many alerts can reduce response effectiveness
- **Cardinality management**: High-cardinality metrics can overwhelm Prometheus

### Implementation Guidelines

**Cardinality limits**:
- Maximum 1000 unique label combinations per metric
- Avoid user IDs or order IDs as metric labels
- Use histogram buckets appropriate for trading latencies

**Log retention**:
- ERROR/WARN logs: 30 days
- INFO logs: 7 days
- DEBUG logs: 1 day (development only)

**Dashboard maintenance**:
- Review and update dashboards monthly
- Archive unused panels quarterly
- Ensure all alerts have corresponding runbook entries
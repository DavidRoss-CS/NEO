# Observability Model

**Three pillars of observability and implementation patterns for the Agentic Trading Architecture.**

## Overview

Observability provides deep insights into system behavior through three complementary pillars: Metrics, Logs, and Traces. This model ensures we can understand not just what is happening, but why it's happening across our distributed trading system.

## The Three Pillars

### 1. Metrics (Prometheus)

**Purpose**: Aggregate numerical measurements over time for trend analysis and alerting.

**Key Metrics Categories**:

#### Business Metrics
```yaml
# Trading Performance
- trading_signals_received_total
- trading_decisions_made_total
- trading_opportunities_identified_total
- trading_pnl_realized_dollars

# Agent Performance
- agent_confidence_score_histogram
- agent_decision_accuracy_ratio
- agent_processing_lag_seconds
```

#### Operational Metrics
```yaml
# Service Health
- service_uptime_seconds
- service_error_rate_ratio
- service_request_duration_seconds

# Infrastructure
- nats_consumer_lag_messages
- nats_jetstream_messages_total
- redis_memory_usage_bytes
- redis_keyspace_hits_total
```

#### System Metrics
```yaml
# Resource Usage
- container_cpu_usage_seconds_total
- container_memory_usage_bytes
- container_network_io_bytes_total
- container_disk_io_bytes_total
```

**Metric Types**:
- **Counter**: Monotonically increasing values (requests_total)
- **Gauge**: Values that go up and down (active_connections)
- **Histogram**: Distribution of values (request_duration_seconds)
- **Summary**: Similar to histogram with quantiles

**Collection Pattern**:
```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
webhook_counter = Counter(
    'gateway_webhooks_total',
    'Total webhooks received',
    ['source', 'status']
)

processing_histogram = Histogram(
    'gateway_processing_duration_seconds',
    'Webhook processing time',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

active_connections = Gauge(
    'gateway_active_connections',
    'Currently active connections'
)

# Use in code
webhook_counter.labels(source='tradingview', status='success').inc()
with processing_histogram.time():
    process_webhook()
active_connections.set(42)
```

### 2. Logs (Structured JSON)

**Purpose**: Detailed event records for debugging and audit trails.

**Log Levels and Usage**:

| Level | Use Case | Example |
|-------|----------|---------|
| DEBUG | Development troubleshooting | "Entering function X with args Y" |
| INFO | Normal operations | "Webhook processed successfully" |
| WARN | Recoverable issues | "Retry attempt 3 of 5" |
| ERROR | Failures requiring attention | "Failed to connect to NATS" |
| FATAL | Service-ending failures | "Unable to bind to port" |

**Structured Log Format**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "at-gateway",
  "version": "1.2.0",
  "environment": "production",
  "corr_id": "req_abc123",
  "span_id": "span_def456",
  "trace_id": "trace_ghi789",
  "message": "Webhook validation completed",
  "metadata": {
    "instrument": "EURUSD",
    "source": "tradingview",
    "validation_ms": 23,
    "schema_version": "1.0.0"
  },
  "error": null
}
```

**Correlation Fields**:
- **corr_id**: End-to-end request correlation
- **span_id**: Current operation identifier
- **trace_id**: Distributed trace identifier
- **parent_span_id**: Parent operation (if nested)

**Log Aggregation Pipeline**:
```
Service → stdout/stderr → Docker → Fluentd → Elasticsearch → Kibana
                                  ↓
                           Archive to S3 (long-term)
```

**Best Practices**:
- Always include correlation ID
- Use consistent field names across services
- Sanitize sensitive data (no passwords, keys, PII)
- Include relevant context without over-logging
- Use structured fields instead of string concatenation

### 3. Traces (OpenTelemetry - Optional)

**Purpose**: Track request flow across distributed services.

**When to Use Traces**:
- Complex multi-service workflows
- Performance bottleneck investigation
- Understanding service dependencies
- SLA compliance verification

**Trace Structure**:
```
Webhook Received (root span)
├── Validation (child span)
├── NATS Publish (child span)
├── Agent Processing (child span)
│   ├── Momentum Analysis
│   ├── Risk Check
│   └── Feature Calculation
├── Orchestration (child span)
│   ├── Signal Aggregation
│   └── Decision Making
└── Execution (child span)
    ├── Order Validation
    └── Simulated Fill
```

**OpenTelemetry Integration**:
```python
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("at-gateway", "1.0.0")

with tracer.start_as_current_span("process_webhook") as span:
    span.set_attribute("corr_id", correlation_id)
    span.set_attribute("instrument", instrument)

    try:
        result = process_webhook(data)
        span.set_attribute("result", "success")
    except Exception as e:
        span.record_exception(e)
        span.set_status(Status(StatusCode.ERROR))
        raise
```

## Service Conventions

### Health Check Endpoint

**Path**: `/healthz`

**Response Format**:
```json
{
  "status": "healthy",
  "service": "at-gateway",
  "version": "1.2.0",
  "uptime_seconds": 3600,
  "checks": {
    "nats": "healthy",
    "redis": "healthy",
    "disk_space": "healthy"
  },
  "metadata": {
    "last_webhook": "2024-01-15T10:30:00Z",
    "total_processed": 1234
  }
}
```

**Health Status Values**:
- `healthy`: All systems operational
- `degraded`: Partial functionality available
- `unhealthy`: Service not operational

### Metrics Endpoint

**Path**: `/metrics`

**Format**: Prometheus text format

**Example Output**:
```
# HELP gateway_webhooks_total Total webhooks received
# TYPE gateway_webhooks_total counter
gateway_webhooks_total{source="tradingview",status="success"} 1234
gateway_webhooks_total{source="tradingview",status="error"} 12

# HELP gateway_processing_duration_seconds Webhook processing time
# TYPE gateway_processing_duration_seconds histogram
gateway_processing_duration_seconds_bucket{le="0.01"} 100
gateway_processing_duration_seconds_bucket{le="0.025"} 200
gateway_processing_duration_seconds_bucket{le="0.05"} 400
gateway_processing_duration_seconds_bucket{le="+Inf"} 500
gateway_processing_duration_seconds_sum 123.45
gateway_processing_duration_seconds_count 500
```

## Correlation ID Management

### Generation Strategy

```python
import uuid
import time

def generate_correlation_id(prefix: str = "req") -> str:
    """Generate unique correlation ID."""
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}_{timestamp}_{unique_id}"
```

### Propagation Pattern

```python
# HTTP Headers
headers = {
    "X-Correlation-ID": correlation_id,
    "X-Parent-Span-ID": parent_span_id,
    "X-Trace-ID": trace_id
}

# NATS Message Headers
message = {
    "corr_id": correlation_id,
    "trace_id": trace_id,
    "span_id": span_id,
    "data": payload
}

# Log Context
logger = logging.getLogger(__name__)
logger = logging.LoggerAdapter(logger, {"corr_id": correlation_id})
```

### Cross-Service Correlation

```
┌─────────────┐     corr_id: req_123     ┌─────────────┐
│  Gateway    │ ────────────────────────> │   Agent     │
└─────────────┘                           └─────────────┘
      ↓ corr_id: req_123                        ↓ corr_id: req_123
┌─────────────┐                           ┌─────────────┐
│ Orchestrator│ <──────────────────────── │   Redis     │
└─────────────┘     corr_id: req_123     └─────────────┘
```

## Retention Policies

### Metrics Retention

| Resolution | Retention | Use Case |
|------------|-----------|----------|
| Raw (15s) | 7 days | Debugging recent issues |
| 5-minute | 30 days | Daily operations |
| 1-hour | 90 days | Trend analysis |
| 1-day | 1 year | Long-term planning |

### Log Retention

| Level | Hot Storage | Cold Storage | Total |
|-------|-------------|--------------|-------|
| DEBUG | 1 day | 0 | 1 day |
| INFO | 7 days | 30 days | 37 days |
| WARN | 30 days | 90 days | 120 days |
| ERROR | 90 days | 365 days | 455 days |

### Trace Retention

- **Sampled traces**: 100% for errors, 1% for success
- **Retention**: 7 days hot, 30 days cold
- **Archive**: Monthly exports to S3

## SLO Monitoring

### Service Level Objectives

```yaml
SLOs:
  gateway:
    availability: 99.9%  # 43.2 min/month downtime
    latency_p95: 100ms
    error_rate: <1%

  agents:
    availability: 99.5%  # 3.6 hrs/month downtime
    processing_time_p95: 500ms
    error_rate: <2%

  orchestrator:
    decision_time_p95: 1000ms
    workflow_success_rate: >98%

  execution:
    order_success_rate: >99%
    slippage_p95: <5bps
```

### SLI Queries

```promql
# Availability SLI
sum(rate(gateway_requests_total[5m])) - sum(rate(gateway_errors_total[5m]))
/ sum(rate(gateway_requests_total[5m]))

# Latency SLI (p95)
histogram_quantile(0.95,
  sum(rate(gateway_request_duration_seconds_bucket[5m])) by (le)
)

# Error Rate SLI
sum(rate(gateway_errors_total[5m]))
/ sum(rate(gateway_requests_total[5m]))
```

### Error Budget Tracking

```python
def calculate_error_budget(slo_target: float, actual_performance: float,
                          time_window_days: int = 30) -> dict:
    """Calculate remaining error budget."""
    allowed_downtime_minutes = (1 - slo_target) * time_window_days * 24 * 60
    actual_downtime_minutes = (1 - actual_performance) * time_window_days * 24 * 60
    remaining_budget_minutes = allowed_downtime_minutes - actual_downtime_minutes

    return {
        "slo_target": slo_target,
        "actual_performance": actual_performance,
        "allowed_downtime_minutes": allowed_downtime_minutes,
        "actual_downtime_minutes": actual_downtime_minutes,
        "remaining_budget_minutes": remaining_budget_minutes,
        "budget_consumed_percent": (actual_downtime_minutes / allowed_downtime_minutes) * 100
    }
```

## Observability Maturity Model

### Level 1: Basic (Current)
- ✅ Metrics exposed from all services
- ✅ Basic dashboards for each service
- ✅ Critical alerts defined
- ✅ Structured JSON logging

### Level 2: Intermediate (Next 3 months)
- ⏳ Centralized log aggregation
- ⏳ Custom business metrics
- ⏳ SLO dashboards and tracking
- ⏳ Automated runbooks

### Level 3: Advanced (Next 6 months)
- ⏳ Full distributed tracing
- ⏳ ML-based anomaly detection
- ⏳ Predictive alerting
- ⏳ Automated remediation

### Level 4: Expert (Future)
- ⏳ Chaos engineering integration
- ⏳ Real-time cost attribution
- ⏳ Business impact correlation
- ⏳ Self-healing systems

---

**Next Steps**: Configure Prometheus with [prometheus.yml](prometheus.yml) and import dashboards from [grafana_dashboards/](grafana_dashboards/).
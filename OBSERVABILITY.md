# Observability Guide

Comprehensive monitoring, logging, and tracing for the Agentic Trading Architecture.

## Overview

Our observability stack follows the **Three Pillars** approach:
1. **Metrics** - What is happening (Prometheus)
2. **Logging** - Why it's happening (Structured JSON)
3. **Tracing** - How requests flow (OpenTelemetry - planned)

## Metrics with Prometheus

### Key Metrics by Service

#### Gateway Metrics
```python
# Request metrics
gateway_webhooks_received_total{source, status}  # Total webhooks processed
gateway_validation_errors_total{type}            # Validation failures
gateway_request_duration_seconds{endpoint}       # Request latency
gateway_rate_limit_exceeded_total{client}        # Rate limit hits

# HMAC metrics
gateway_hmac_validation_duration_seconds         # Auth processing time
gateway_replay_attacks_blocked_total             # Security events
```

#### Agent Metrics
```python
# Signal processing
agent_signals_received_total{signal_type}        # Incoming signals
agent_decisions_made_total{strategy}             # Trading decisions
agent_decision_latency_seconds{strategy}         # Decision time
agent_risk_checks_failed_total{reason}           # Risk rejections

# Strategy performance
agent_strategy_signals_total{strategy, action}   # Buy/sell signals
agent_strategy_confidence{strategy}              # Signal confidence
```

#### Execution Simulator Metrics
```python
# Order processing
exec_sim_orders_received_total{status}           # Order validation
exec_sim_fills_generated_total{fill_type, instrument}  # Executions
exec_sim_simulation_duration_seconds             # Processing time
exec_sim_slippage_bps{instrument}               # Execution quality

# Unknown fields tracking
exec_sim_unknown_fields_total{field_name}        # Schema evolution

# Consumer health
exec_sim_fetch_calls_total                       # NATS fetch attempts
exec_sim_fetch_empty_total                       # Empty fetches
```

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'gateway'
    static_configs:
      - targets: ['gateway:8001']
    metrics_path: /metrics

  - job_name: 'agent'
    static_configs:
      - targets: ['agent:8002']
    metrics_path: /metrics

  - job_name: 'exec-sim'
    static_configs:
      - targets: ['exec:8004']
    metrics_path: /metrics

  - job_name: 'nats'
    static_configs:
      - targets: ['nats-exporter:7777']
```

### Key Queries (PromQL)

```promql
# Request rate (per second)
rate(gateway_webhooks_received_total[5m])

# Error rate percentage
100 * rate(gateway_validation_errors_total[5m])
  / rate(gateway_webhooks_received_total[5m])

# P95 latency
histogram_quantile(0.95,
  rate(gateway_request_duration_seconds_bucket[5m]))

# Orders per minute by instrument
sum by (instrument) (
  rate(exec_sim_orders_received_total[1m]) * 60
)

# NATS consumer lag
exec_sim_pending_events_count

# System health score (custom)
min(
  up{job=~"gateway|agent|exec-sim"},
  1 - (rate(gateway_validation_errors_total[5m]) > 0.1),
  exec_sim_pending_events_count < 100
)
```

## Logging with Structured JSON

### Log Levels and When to Use Them

| Level | Use Case | Example |
|-------|----------|---------|
| DEBUG | Detailed diagnostic info | Message contents, intermediate values |
| INFO | Normal operations | Order processed, signal received |
| WARNING | Recoverable issues | Retry attempted, degraded performance |
| ERROR | Failures requiring attention | Connection lost, validation failed |
| CRITICAL | System-threatening issues | Out of memory, data corruption |

### Structured Logging Format

```python
# Configure structured logging
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Usage
logger = structlog.get_logger()

logger.info("Order processed",
    corr_id="req_abc123",
    instrument="AAPL",
    side="buy",
    quantity=100,
    fill_price=150.25,
    slippage_bps=2.5,
    duration_ms=45
)
```

### Log Output Example
```json
{
  "event": "Order processed",
  "level": "info",
  "timestamp": "2025-01-15T10:30:00.123Z",
  "logger": "at_exec_sim.processor",
  "corr_id": "req_abc123",
  "instrument": "AAPL",
  "side": "buy",
  "quantity": 100,
  "fill_price": 150.25,
  "slippage_bps": 2.5,
  "duration_ms": 45
}
```

### Correlation ID Standards

Every log entry MUST include correlation ID:
```python
# Bad
logger.info("Processing order")

# Good
logger.info("Processing order", corr_id=corr_id)

# Better - with context
logger = logger.bind(corr_id=corr_id)
logger.info("Processing order")
logger.info("Order validated")
logger.info("Fill generated")
```

### Log Aggregation with ELK/Loki

#### Loki Configuration
```yaml
# loki-config.yml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  filesystem:
    directory: /loki/chunks
```

#### Promtail Configuration
```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: containers
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
```

## Health Checks

### Standard Health Endpoint

All services MUST implement `/healthz`:

```python
@app.get("/healthz")
async def health_check():
    checks = {
        "nats": await check_nats_connection(),
        "database": await check_database(),
        "consumer": await check_consumer_health()
    }

    is_healthy = all(checks.values())
    status_code = 200 if is_healthy else 503

    return {
        "ok": is_healthy,
        "uptime_s": get_uptime(),
        "version": "1.0.0",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Health Check Aggregation
```bash
# Check all services
for port in 8001 8002 8004 8005; do
    echo "Service on port $port:"
    curl -s localhost:$port/healthz | jq '.ok'
done

# Kubernetes liveness probe
livenessProbe:
  httpGet:
    path: /healthz
    port: 8001
  initialDelaySeconds: 10
  periodSeconds: 10

# Kubernetes readiness probe
readinessProbe:
  httpGet:
    path: /healthz
    port: 8001
  initialDelaySeconds: 5
  periodSeconds: 5
```

## Grafana Dashboards

### System Overview Dashboard
```json
{
  "dashboard": {
    "title": "Trading System Overview",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [{
          "expr": "sum(rate(gateway_webhooks_received_total[5m]))"
        }]
      },
      {
        "title": "Error Rate",
        "targets": [{
          "expr": "sum(rate(gateway_validation_errors_total[5m]))"
        }]
      },
      {
        "title": "Order Processing",
        "targets": [{
          "expr": "rate(exec_sim_orders_received_total[5m])"
        }]
      },
      {
        "title": "P95 Latency",
        "targets": [{
          "expr": "histogram_quantile(0.95, rate(gateway_request_duration_seconds_bucket[5m]))"
        }]
      }
    ]
  }
}
```

### Service-Specific Dashboards

#### Gateway Dashboard
- Webhook reception rate
- Authentication success/failure
- Rate limiting metrics
- Request latency distribution
- Error breakdown by type

#### Agent Dashboard
- Signals processed
- Decisions by strategy
- Risk check failures
- Strategy performance metrics
- Decision latency

#### Execution Dashboard
- Orders received/processed
- Fill rates by instrument
- Slippage analysis
- Partial fill statistics
- Queue depth

## Alerting Rules

### Prometheus Alert Configuration

```yaml
# alerts.yml
groups:
  - name: service_health
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"

      - alert: HighErrorRate
        expr: |
          rate(gateway_validation_errors_total[5m])
          / rate(gateway_webhooks_received_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Error rate above 5%"

      - alert: NATSConsumerLag
        expr: exec_sim_pending_events_count > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "NATS consumer lag high"

      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(gateway_request_duration_seconds_bucket[5m])
          ) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency above 500ms"
```

### Alert Routing (AlertManager)

```yaml
# alertmanager.yml
route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
    - match:
        severity: warning
      receiver: 'slack'

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://localhost:5001/webhook'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '<SERVICE_KEY>'

  - name: 'slack'
    slack_configs:
      - api_url: '<WEBHOOK_URL>'
        channel: '#alerts'
```

## Distributed Tracing (Future)

### OpenTelemetry Integration

```python
# Planned implementation
from opentelemetry import trace
from opentelemetry.exporter.jaeger import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Create exporter
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger",
    agent_port=6831,
)

# Add span processor
span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Usage
async def process_order(order, corr_id):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("corr_id", corr_id)
        span.set_attribute("instrument", order["instrument"])

        # Process order
        result = await validate_and_execute(order)

        span.set_attribute("status", result.status)
        return result
```

## Performance Monitoring

### Key Performance Indicators (KPIs)

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Availability | 99.9% | < 99.5% |
| P95 Latency | < 100ms | > 200ms |
| Error Rate | < 1% | > 5% |
| Throughput | 1000 req/s | < 500 req/s |
| NATS Lag | < 100 msgs | > 1000 msgs |

### Performance Dashboard Queries

```promql
# Throughput
sum(rate(gateway_webhooks_received_total[1m])) * 60

# Availability (last hour)
avg_over_time(up[1h]) * 100

# Error budget remaining (monthly)
1 - (
  sum(increase(gateway_validation_errors_total[30d]))
  / sum(increase(gateway_webhooks_received_total[30d]))
) * 100

# Resource usage
container_memory_usage_bytes{name="gateway"} / 1024 / 1024
```

## Debugging Production Issues

### Log Searching with Loki/LogQL

```logql
# Find all errors for a correlation ID
{job="gateway"} |= "corr_id=req_abc123" |= "error"

# Find slow requests
{job="gateway"} |= "duration_ms" | json | duration_ms > 1000

# Count errors by type
sum by (error_type) (
  count_over_time(
    {job="gateway"} |= "error" | json | __error__="" [5m]
  )
)

# Find related logs across services
{job=~"gateway|agent|exec-sim"} |= "req_abc123"
```

### Common Issues and Metrics

| Issue | Metrics to Check | Logs to Search |
|-------|------------------|----------------|
| High latency | `request_duration_seconds`, CPU/memory usage | "duration_ms > 500" |
| Order failures | `orders_received_total{status="invalid"}` | "validation failed" |
| NATS issues | `pending_events_count`, `nats_disconnections` | "NATS disconnected" |
| Memory leak | `container_memory_usage_bytes` | "out of memory" |
| Rate limiting | `rate_limit_exceeded_total` | "rate limit" |

## Monitoring Checklist

### Daily Checks
- [ ] All services healthy (`/healthz` returning 200)
- [ ] No critical alerts firing
- [ ] Error rate below 1%
- [ ] NATS consumer lag < 100 messages
- [ ] No unusual memory growth

### Weekly Reviews
- [ ] Review error patterns
- [ ] Check performance trends
- [ ] Update alert thresholds if needed
- [ ] Review disk usage trends
- [ ] Check certificate expiration

### Monthly Analysis
- [ ] SLO compliance report
- [ ] Capacity planning review
- [ ] Alert noise reduction
- [ ] Dashboard optimization
- [ ] Runbook updates

## Tools and Resources

### Monitoring Stack
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **AlertManager**: Alert routing and management
- **Loki/Promtail**: Log aggregation
- **Jaeger**: Distributed tracing (planned)

### Useful Commands
```bash
# Check metrics for a service
curl -s localhost:8001/metrics | grep -i error

# Watch logs in real-time
docker logs -f agentic-trading-architecture-full-gateway-1

# Query Prometheus
curl -g 'http://localhost:9090/api/v1/query?query=up'

# Test alert
curl -H "Content-Type: application/json" -d \
  '[{"labels":{"alertname":"test"}}]' \
  http://localhost:9093/api/v1/alerts
```

### References
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Dashboard Guide](https://grafana.com/docs/grafana/latest/dashboards/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [SRE Book - Monitoring](https://sre.google/sre-book/monitoring-distributed-systems/)

---

*Remember: You can't fix what you can't measure. Instrument everything!*
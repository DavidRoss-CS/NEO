# Agentic Trading - Observability

**Unified monitoring, metrics, and alerting for the Agentic Trading Architecture.**

## Purpose

The `at-observability` repository provides a single-pane-of-glass view of the entire Agentic Trading Architecture. It unifies metrics collection, log aggregation, distributed tracing, and alerting across all services to ensure operational excellence and rapid incident response.

## Responsibilities

✅ **What we do**:
- Collect and aggregate metrics from all services via Prometheus
- Provide real-time dashboards through Grafana
- Define and manage alert rules for critical conditions
- Correlate events across services using correlation IDs
- Track SLO compliance and performance trends
- Enable distributed tracing for complex workflows
- Maintain runbook links for incident response

❌ **What we don't do**:
- Fix code issues (only observe and alert)
- Own service schemas or contracts
- Execute trades or make trading decisions
- Store business data or state
- Implement service logic

## Quick Start

### Prerequisites
```bash
# Required: Docker and Docker Compose
docker --version
docker compose version
```

### Start Observability Stack
```bash
# Start Prometheus and Grafana
docker compose -f docker-compose.dev.yml up -d prom grafana

# Wait for services to be ready
docker compose ps

# Access services
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

### Import Dashboards
```bash
# Import dashboards via Grafana UI
# 1. Navigate to http://localhost:3000
# 2. Go to Dashboards → Import
# 3. Upload JSON files from grafana_dashboards/
```

## Repository Layout

```
at-observability/
├── README.md                    # This file
├── OBSERVABILITY_MODEL.md       # Three pillars of observability
├── ALERTS.md                    # Alert rules and escalation
├── TEST_STRATEGY.md             # Testing approach
├── prometheus/
│   ├── prometheus.yml           # Prometheus configuration
│   ├── alerts/                  # Alert rule files
│   │   ├── gateway.yml
│   │   ├── agents.yml
│   │   └── infrastructure.yml
│   └── recording_rules/         # Pre-computed metrics
├── grafana/
│   ├── provisioning/
│   │   ├── dashboards/
│   │   └── datasources/
│   └── dashboards/              # Dashboard JSON files
│       ├── gateway.json
│       ├── agents.json
│       ├── orchestrator.json
│       └── overview.json
├── exporters/                   # Custom metric exporters
│   ├── nats_exporter/
│   └── trading_exporter/
├── docker-compose.dev.yml       # Development stack
└── docker-compose.prod.yml      # Production stack
```

## Metrics Overview

### Service Metrics

| Service | Port | Key Metrics |
|---------|------|-------------|
| at-gateway | 8001 | `gateway_webhooks_total`, `gateway_validation_errors_total` |
| at-agents | 9000-9010 | `agent_messages_processed_total`, `agent_processing_duration_seconds` |
| at-orchestrator | 9090 | `orchestrator_workflows_total`, `orchestrator_decision_latency_seconds` |
| at-mcp | 8003 | `mcp_tool_calls_total`, `mcp_tool_duration_seconds` |
| at-exec-sim | 8004 | `execution_orders_total`, `execution_slippage_bps` |

### Infrastructure Metrics

| Component | Exporter | Key Metrics |
|-----------|----------|-------------|
| NATS | nats_exporter | `nats_consumer_lag`, `nats_jetstream_messages_total` |
| Redis | redis_exporter | `redis_connected_clients`, `redis_used_memory_bytes` |
| Docker | cadvisor | `container_cpu_usage_seconds_total`, `container_memory_usage_bytes` |

## Dashboards

### Available Dashboards

1. **System Overview** - High-level health and KPIs
2. **Gateway Performance** - Webhook ingress and validation
3. **Agent Analytics** - Per-agent processing and errors
4. **Orchestration Flow** - Workflow coordination metrics
5. **Trading Execution** - Order flow and slippage
6. **Infrastructure** - NATS, Redis, containers

### Dashboard Conventions

- **Color scheme**: Green (healthy), Yellow (warning), Red (critical)
- **Time ranges**: Default 1h, options for 15m, 1h, 6h, 24h, 7d
- **Variables**: Environment, service, agent_type
- **Annotations**: Deployments, incidents, market events

## Alerting

### Alert Severity Levels

| Level | Response Time | Examples |
|-------|--------------|----------|
| Critical | <5 min | Gateway down, NATS disconnected |
| Warning | <30 min | High error rate, consumer lag |
| Info | Next day | Performance degradation, capacity planning |

### Key Alerts

```yaml
# Critical
- Gateway error rate >1% for 5 minutes
- NATS consumer lag >1000 for 2 minutes
- Any service down for >1 minute

# Warning
- Agent error rate >2% for 10 minutes
- Redis memory >80% capacity
- API latency p95 >500ms for 5 minutes

# Info
- Disk usage >70%
- Certificate expiry <30 days
```

## Correlation and Tracing

### Correlation ID Flow

```
Webhook → Gateway (assigns corr_id)
  ↓
NATS message (includes corr_id)
  ↓
Agent processing (logs with corr_id)
  ↓
Orchestrator (correlates by corr_id)
  ↓
Execution (completes with corr_id)
```

### Log Format Standard

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "at-gateway",
  "corr_id": "req_abc123",
  "message": "Webhook processed successfully",
  "duration_ms": 45,
  "metadata": {
    "instrument": "EURUSD",
    "action": "buy"
  }
}
```

## Development

### Adding New Metrics

1. **Define metric** in service code:
```python
from prometheus_client import Counter, Histogram

my_metric = Counter(
    'service_operation_total',
    'Total operations processed',
    ['operation_type', 'status']
)
```

2. **Update scrape config** in prometheus.yml
3. **Create dashboard panel** in Grafana
4. **Add alert rule** if needed

### Testing Dashboards

```bash
# Validate Prometheus config
promtool check config prometheus/prometheus.yml

# Lint dashboard JSON
jq . grafana/dashboards/*.json

# Test with sample data
docker compose -f docker-compose.test.yml up
```

## Production Deployment

### High Availability Setup

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:v2.45.0
    volumes:
      - prometheus_data:/prometheus
      - ./prometheus:/etc/prometheus
    command:
      - '--storage.tsdb.retention.time=90d'
      - '--storage.tsdb.path=/prometheus'
      - '--config.file=/etc/prometheus/prometheus.yml'
    restart: always

  grafana:
    image: grafana/grafana:10.0.0
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=redis-datasource
    restart: always

  alertmanager:
    image: prom/alertmanager:v0.26.0
    volumes:
      - ./alertmanager:/etc/alertmanager
    restart: always

volumes:
  prometheus_data:
  grafana_data:
```

### Backup Strategy

- **Prometheus**: Snapshot API for TSDB backup
- **Grafana**: Database backup + dashboard exports
- **Alert rules**: Version controlled in Git

## Integration with Services

### Service Requirements

Each service must:
1. Expose `/metrics` endpoint (Prometheus format)
2. Expose `/healthz` endpoint (JSON health status)
3. Include `corr_id` in all log entries
4. Use standardized metric names
5. Implement proper error tracking

### Metric Naming Conventions

```
<service>_<component>_<action>_<unit>

Examples:
gateway_webhooks_received_total
agent_processing_duration_seconds
orchestrator_workflows_active
```

## Troubleshooting

### Common Issues

1. **Metrics not appearing**
   - Check service is running: `curl http://service:port/metrics`
   - Verify Prometheus target: http://localhost:9090/targets
   - Check network connectivity

2. **Dashboard shows "No Data"**
   - Verify datasource configuration
   - Check metric names match
   - Confirm time range includes data

3. **Alerts not firing**
   - Check alert rules syntax: `promtool check rules alerts.yml`
   - Verify alertmanager connection
   - Review threshold values

## Support

- **Questions**: #observability Slack channel
- **Issues**: GitHub issues with dashboard screenshots
- **Emergencies**: Follow escalation in ALERTS.md

---

**Next Steps**: Review [OBSERVABILITY_MODEL.md](OBSERVABILITY_MODEL.md) for detailed architecture and [ALERTS.md](ALERTS.md) for alert configuration.
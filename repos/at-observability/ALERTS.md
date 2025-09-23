# Alert Rules and Escalation

**Comprehensive alerting strategy for the Agentic Trading Architecture.**

## Overview

This document defines alert rules, severity levels, escalation policies, and runbook procedures for the Agentic Trading Architecture. Alerts are designed to provide early warning of issues while minimizing false positives.

## Alert Severity Levels

### Critical (P0) - Response: <5 minutes
**Impact**: Service outage or severe degradation affecting trading operations

Examples:
- Gateway completely down
- NATS cluster unavailable
- Redis master down
- Multiple agents failing simultaneously

**Escalation**: Immediate PagerDuty → Primary oncall → Secondary oncall (if no ack in 10min)

### High (P1) - Response: <15 minutes
**Impact**: Significant service degradation but partial functionality remains

Examples:
- High error rate (>1% for >5min)
- High latency (>500ms p95 for >5min)
- Single agent down
- Consumer lag building up

**Escalation**: PagerDuty → Primary oncall → Manager (if no ack in 30min)

### Warning (P2) - Response: <30 minutes
**Impact**: Potential future issues or minor degradation

Examples:
- Moderate error rate (>0.5% for >10min)
- Resource usage above thresholds
- Certificate expiry warnings
- Slow performance trends

**Escalation**: Slack notification → Primary oncall → Ticket created

### Info (P3) - Response: Next business day
**Impact**: Information only, no immediate action required

Examples:
- Capacity planning alerts
- Performance trends
- Non-critical configuration drift
- Maintenance reminders

**Escalation**: Slack notification → Ticket created

## Alert Rules Configuration

### Gateway Service Alerts

#### Critical Alerts

```yaml
groups:
  - name: gateway.critical
    rules:
      - alert: GatewayDown
        expr: up{job="gateway"} == 0
        for: 1m
        labels:
          severity: critical
          service: gateway
          team: platform
        annotations:
          summary: "Gateway service is down"
          description: "Gateway service has been down for more than 1 minute"
          runbook_url: "https://wiki.company.com/runbooks/gateway-down"
          dashboard_url: "https://grafana.company.com/d/gateway-001"

      - alert: GatewayHighErrorRate
        expr: |
          (
            sum(rate(gateway_validation_errors_total[5m]))
            / sum(rate(gateway_webhooks_total[5m]))
          ) * 100 > 1
        for: 5m
        labels:
          severity: critical
          service: gateway
          team: platform
        annotations:
          summary: "Gateway error rate is {{ $value | humanizePercentage }}"
          description: "Gateway validation error rate has been above 1% for 5 minutes"
          runbook_url: "https://wiki.company.com/runbooks/gateway-errors"

      - alert: GatewayNATSPublishFailure
        expr: |
          sum(rate(gateway_nats_publish_failures_total[5m])) > 0.1
        for: 2m
        labels:
          severity: critical
          service: gateway
          team: platform
        annotations:
          summary: "Gateway failing to publish to NATS"
          description: "Gateway NATS publish failures detected: {{ $value }} failures/sec"
          runbook_url: "https://wiki.company.com/runbooks/nats-publish-failure"
```

#### High Priority Alerts

```yaml
      - alert: GatewayHighLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(gateway_nats_publish_duration_seconds_bucket[5m])) by (le)
          ) * 1000 > 500
        for: 5m
        labels:
          severity: high
          service: gateway
          team: platform
        annotations:
          summary: "Gateway NATS publish latency is high"
          description: "Gateway p95 NATS publish latency is {{ $value }}ms"
          runbook_url: "https://wiki.company.com/runbooks/gateway-latency"

      - alert: GatewayRateLimitHit
        expr: |
          sum(rate(gateway_http_responses_total{status_code="429"}[5m])) > 1
        for: 3m
        labels:
          severity: high
          service: gateway
          team: platform
        annotations:
          summary: "Gateway hitting rate limits"
          description: "Gateway receiving {{ $value }} 429 responses per second"
          runbook_url: "https://wiki.company.com/runbooks/rate-limiting"
```

### Agent Service Alerts

#### Critical Alerts

```yaml
  - name: agents.critical
    rules:
      - alert: AgentDown
        expr: up{job="agents"} == 0
        for: 2m
        labels:
          severity: critical
          service: agents
          team: trading
        annotations:
          summary: "Agent {{ $labels.instance }} is down"
          description: "Agent {{ $labels.agent_type }} has been down for more than 2 minutes"
          runbook_url: "https://wiki.company.com/runbooks/agent-down"

      - alert: AllAgentsDown
        expr: count(up{job="agents"} == 1) == 0
        for: 1m
        labels:
          severity: critical
          service: agents
          team: trading
        annotations:
          summary: "All trading agents are down"
          description: "No trading agents are responding"
          runbook_url: "https://wiki.company.com/runbooks/all-agents-down"

      - alert: AgentHighErrorRate
        expr: |
          (
            sum(rate(agent_errors_total[5m])) by (agent_type)
            / sum(rate(agent_messages_processed_total[5m])) by (agent_type)
          ) * 100 > 5
        for: 5m
        labels:
          severity: critical
          service: agents
          team: trading
        annotations:
          summary: "Agent {{ $labels.agent_type }} error rate is {{ $value | humanizePercentage }}"
          description: "Agent error rate has been above 5% for 5 minutes"
          runbook_url: "https://wiki.company.com/runbooks/agent-errors"
```

#### High Priority Alerts

```yaml
      - alert: AgentProcessingLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(agent_processing_duration_seconds_bucket[5m])) by (agent_type, le)
          ) * 1000 > 1000
        for: 5m
        labels:
          severity: high
          service: agents
          team: trading
        annotations:
          summary: "Agent {{ $labels.agent_type }} processing latency is high"
          description: "Agent p95 processing time is {{ $value }}ms"
          runbook_url: "https://wiki.company.com/runbooks/agent-latency"

      - alert: AgentLowConfidence
        expr: |
          avg(agent_confidence_score) by (agent_type) < 0.5
        for: 10m
        labels:
          severity: high
          service: agents
          team: trading
        annotations:
          summary: "Agent {{ $labels.agent_type }} confidence is low"
          description: "Agent confidence score is {{ $value | humanizePercentage }}"
          runbook_url: "https://wiki.company.com/runbooks/agent-confidence"
```

### Infrastructure Alerts

#### Critical Alerts

```yaml
  - name: infrastructure.critical
    rules:
      - alert: NATSDown
        expr: up{job="nats"} == 0
        for: 1m
        labels:
          severity: critical
          service: nats
          team: platform
        annotations:
          summary: "NATS server is down"
          description: "NATS message broker is unavailable"
          runbook_url: "https://wiki.company.com/runbooks/nats-down"

      - alert: NATSConsumerLag
        expr: |
          sum(nats_consumer_pending_messages) by (consumer) > 1000
        for: 2m
        labels:
          severity: critical
          service: nats
          team: platform
        annotations:
          summary: "NATS consumer {{ $labels.consumer }} lag is high"
          description: "Consumer has {{ $value }} pending messages"
          runbook_url: "https://wiki.company.com/runbooks/nats-lag"

      - alert: RedisDown
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: critical
          service: redis
          team: platform
        annotations:
          summary: "Redis server is down"
          description: "Redis cache/state store is unavailable"
          runbook_url: "https://wiki.company.com/runbooks/redis-down"

      - alert: HighMemoryUsage
        expr: |
          (
            container_memory_usage_bytes{name!=""}
            / container_spec_memory_limit_bytes{name!=""}
          ) * 100 > 90
        for: 5m
        labels:
          severity: critical
          service: infrastructure
          team: platform
        annotations:
          summary: "Container {{ $labels.name }} memory usage is {{ $value | humanizePercentage }}"
          description: "Container memory usage has been above 90% for 5 minutes"
          runbook_url: "https://wiki.company.com/runbooks/memory-usage"
```

#### Warning Alerts

```yaml
      - alert: HighCPUUsage
        expr: |
          rate(container_cpu_usage_seconds_total{name!=""}[5m]) * 100 > 80
        for: 10m
        labels:
          severity: warning
          service: infrastructure
          team: platform
        annotations:
          summary: "Container {{ $labels.name }} CPU usage is {{ $value | humanizePercentage }}"
          description: "Container CPU usage has been above 80% for 10 minutes"
          runbook_url: "https://wiki.company.com/runbooks/cpu-usage"

      - alert: DiskSpaceUsage
        expr: |
          (
            node_filesystem_size_bytes{fstype!="tmpfs"}
            - node_filesystem_avail_bytes{fstype!="tmpfs"}
          ) / node_filesystem_size_bytes{fstype!="tmpfs"} * 100 > 75
        for: 5m
        labels:
          severity: warning
          service: infrastructure
          team: platform
        annotations:
          summary: "Disk usage on {{ $labels.device }} is {{ $value | humanizePercentage }}"
          description: "Disk space usage is above 75%"
          runbook_url: "https://wiki.company.com/runbooks/disk-space"

      - alert: RedisMemoryUsage
        expr: |
          redis_memory_used_bytes / redis_memory_max_bytes * 100 > 80
        for: 5m
        labels:
          severity: warning
          service: redis
          team: platform
        annotations:
          summary: "Redis memory usage is {{ $value | humanizePercentage }}"
          description: "Redis memory usage is above 80%"
          runbook_url: "https://wiki.company.com/runbooks/redis-memory"
```

## Escalation Policies

### Primary Escalation Chain

```
Incident Triggered
        ↓
   PagerDuty Alert
        ↓
  Primary On-call (immediate)
        ↓
Secondary On-call (5min timeout)
        ↓
Engineering Manager (15min timeout)
        ↓
    Engineering Director (30min timeout)
```

### Team Assignments

| Service Area | Primary Team | Secondary Team |
|--------------|--------------|----------------|
| Gateway | Platform Team | Trading Team |
| Agents | Trading Team | Platform Team |
| Orchestrator | Trading Team | Platform Team |
| Infrastructure | Platform Team | SRE Team |
| NATS/Redis | Platform Team | SRE Team |

### Notification Channels

#### Critical & High Priority
- **PagerDuty**: Immediate phone/SMS to on-call
- **Slack**: #alerts-critical channel
- **Email**: team-distribution-lists

#### Warning & Info
- **Slack**: #alerts-warning channel
- **Email**: Daily digest to team leads

## Runbook Procedures

### Gateway Down Runbook

**Symptoms**: Gateway health check failing, no webhook processing

**Immediate Actions**:
1. Check gateway service status: `docker ps | grep gateway`
2. Check logs: `docker logs at-gateway --tail 100`
3. Verify NATS connectivity: `curl http://nats:8222/varz`
4. Check resource usage: `docker stats at-gateway`

**Recovery Steps**:
1. Restart gateway service: `docker restart at-gateway`
2. Verify webhook endpoints: `curl http://gateway:8001/healthz`
3. Test webhook processing with sample payload
4. Monitor error rates for 10 minutes

**Escalation**: If restart doesn't resolve, escalate to Platform Team lead

### Agent Down Runbook

**Symptoms**: Agent not processing messages, high consumer lag

**Immediate Actions**:
1. Identify affected agent: Check Grafana agent dashboard
2. Check agent logs: `docker logs at-agent-{type} --tail 100`
3. Verify NATS subscription: Check consumer status
4. Check memory/CPU usage

**Recovery Steps**:
1. Restart affected agent: `docker restart at-agent-{type}`
2. Clear any stuck messages in queue
3. Verify processing resumes: Monitor metrics
4. Check for pattern in failures

**Escalation**: If multiple agents affected, escalate to Trading Team lead

### NATS Connectivity Issues

**Symptoms**: NATS publish failures, consumer lag building

**Immediate Actions**:
1. Check NATS server status: `curl http://nats:8222/varz`
2. Verify JetStream status: `curl http://nats:8222/jsz`
3. Check consumer states: `nats consumer ls`
4. Review NATS server logs

**Recovery Steps**:
1. Restart NATS if needed: `docker restart nats`
2. Recreate streams if corrupted: `nats stream add`
3. Reset consumer positions if required
4. Verify all services reconnect

**Escalation**: If data loss suspected, escalate to Engineering Manager

## Alert Testing

### Test Schedule

- **Weekly**: Test critical alerts with synthetic failures
- **Monthly**: Test escalation chains end-to-end
- **Quarterly**: Review and update alert thresholds

### Test Procedures

```bash
# Test gateway alerts
docker stop at-gateway
# Wait for alert to fire, verify notifications
docker start at-gateway

# Test high latency alerts
# Inject artificial delay in gateway
curl -X POST http://gateway:8001/test/inject-delay

# Test NATS alerts
docker stop nats
# Verify consumer lag alerts fire
docker start nats
```

### Alert Tuning

#### Threshold Guidelines

- **Error Rate**: Start with 1%, tune based on baseline
- **Latency**: Set at 2x normal p95, adjust for SLA requirements
- **Resource Usage**: 80% for warning, 90% for critical
- **Consumer Lag**: Based on message processing rate

#### False Positive Reduction

1. **Multiple conditions**: Combine metrics (error rate AND latency)
2. **Time windows**: Require sustained issues (for: 5m)
3. **Business context**: Suppress during maintenance windows
4. **Rate limiting**: Prevent alert storms

## Incident Response

### Incident Classification

#### SEV-1 (Critical)
- Complete service outage
- Data loss or corruption
- Security breach
- Multiple critical alerts

**Response**: All hands, immediate bridge

#### SEV-2 (High)
- Significant degradation
- Single service outage
- High error rates

**Response**: On-call team, manager notification

#### SEV-3 (Medium)
- Minor degradation
- Non-critical service issues
- Performance warnings

**Response**: On-call investigation during business hours

### Post-Incident Review

**Required for SEV-1 and SEV-2 incidents**

1. **Timeline**: Chronological event sequence
2. **Root Cause**: Technical and process failures
3. **Impact**: Business and technical impact assessment
4. **Action Items**: Specific improvements with owners
5. **Alert Review**: Were alerts appropriate and timely?

## Monitoring Coverage

### Service Coverage Matrix

| Service | Health Check | Metrics | Logs | Alerts |
|---------|--------------|---------|------|--------|
| Gateway | ✅ /healthz | ✅ /metrics | ✅ JSON | ✅ Rules |
| Agents | ✅ /healthz | ✅ /metrics | ✅ JSON | ✅ Rules |
| Orchestrator | ✅ /healthz | ✅ /metrics | ✅ JSON | ✅ Rules |
| MCP | ✅ /health | ✅ /metrics | ✅ JSON | ⏳ Rules |
| Execution | ✅ /healthz | ✅ /metrics | ✅ JSON | ⏳ Rules |
| NATS | ✅ Monitor | ✅ Exporter | ✅ Native | ✅ Rules |
| Redis | ✅ Monitor | ✅ Exporter | ✅ Native | ✅ Rules |

### Gap Analysis

**Missing Coverage**:
- MCP service alert rules
- Execution simulator alerts
- Cross-service correlation alerts
- Business metric alerts (PnL, trading performance)

**Improvement Areas**:
- Predictive alerting based on trends
- Anomaly detection for unusual patterns
- Automated remediation for known issues
- Better alert context and suggested actions

---

**Next Steps**: Configure Alertmanager with these rules and test escalation policies with the team.
# Gateway Service Runbook

## Service Summary

**What it does**: Ingests external market data via HTTP webhooks, validates authentication, normalizes payloads, and publishes events to NATS.

**Inbound**: HTTP POST webhooks from TradingView, custom systems
**Outbound**: NATS events on `signals.raw` and `signals.normalized` subjects

**Critical dependencies**:
- NATS JetStream (required for operation)
- System clock (for replay protection)

**Service criticality**: High - all market data flows through this service

## What Healthy Looks Like

### Health Checklist
- ✅ `/healthz` returns `{"ok":true,"nats":"connected"}` within <50ms
- ✅ Grafana panels show: request rate steady, 4xx/5xx <0.5%, p95 latency <100ms
- ✅ Prometheus counters increasing: `gateway_webhooks_received_total`, `gateway_nats_publish_total{status="success"}`
- ✅ NATS consumer lag <100 messages
- ✅ Resource usage: CPU <80%, memory RSS stable
- ✅ No critical alerts firing (GW-005, high error rate, consumer lag)

### Quick Verification
```bash
# Health check
curl -f http://localhost:8001/healthz | jq '.ok and (.nats == "connected")'

# Recent successful webhooks
curl -s http://localhost:8001/metrics | grep 'gateway_webhooks_received_total.*2xx' | tail -1

# NATS publish success
curl -s http://localhost:8001/metrics | grep 'gateway_nats_publish_total.*success' | tail -1

# Error rate check (should be low)
curl -s http://localhost:8001/metrics | grep 'gateway_webhooks_received_total.*[45]xx' | awk '{sum+=$2} END {print "Error count:", sum+0}'

# Consumer lag
nats consumer info trading-events gateway-consumer | grep "Num Pending" | awk '{print $3}'
```

## Health Checks

### /healthz Endpoint
```bash
curl http://localhost:8001/healthz
```

**Response Fields**:
- `ok: true` - Service is operational
- `uptime_s` - Seconds since service start
- `nats: "connected"` - NATS connection status
- `version` - Service version

**NATS Status Values**:
- `connected`: Normal operation, publishing successfully
- `degraded`: Connected but high latency or intermittent errors
- `disconnected`: Cannot reach NATS, service will return 503

## Replay Cache & Idempotency Tuning

### Configuration
- **Default TTL**: `IDEMPOTENCY_TTL_SEC=3600` (1 hour)
- **Memory profile**: ~200 bytes per cached key (includes hash + metadata)
- **Eviction**: LRU with TTL expiration
- **Storage**: In-memory by default; persistent store planned

### Tuning Guide

| Symptom | Investigation | Action |
|---------|---------------|--------|
| High 409 GW-006 errors | Check client key reuse patterns | Increase `IDEMPOTENCY_TTL_SEC` or fix client key generation |
| Excessive memory usage | Monitor cache size and growth | Decrease TTL or enable persistent store |
| Unexpected duplicate acceptance | Verify key derivation logic | Ensure `hash(source\|instrument\|timestamp)` uniqueness |
| Memory leaks | Check cache cleanup | Restart service, monitor for growth pattern |

### Monitoring Commands
```bash
# Idempotency conflict rate
curl -s http://localhost:8001/metrics | grep gateway_idempotency_conflicts_total

# Memory usage (RSS)
ps -o pid,rss,vsz,comm -p $(pgrep -f at_gateway) | tail -1

# Cache hit/miss patterns (if implemented)
curl -s http://localhost:8001/metrics | grep idempotency_cache
```

## Maintenance Mode Operations

### Enable Maintenance Mode
```bash
# 1. Set maintenance flag
export MAINTENANCE_MODE=true

# 2. Restart service
sudo systemctl restart at-gateway

# 3. Verify 503 responses
curl -v http://localhost:8001/webhook/tradingview -d '{}' -H "Content-Type: application/json"
# Expected: 503 GW-011 with Retry-After header
```

### Disable Maintenance Mode
```bash
# 1. Unset maintenance flag
unset MAINTENANCE_MODE

# 2. Restart service
sudo systemctl restart at-gateway

# 3. Verify normal operation
curl -f http://localhost:8001/healthz
```

### Pre/Post Maintenance Checklist
**Pre-maintenance**:
- [ ] Announce maintenance window to stakeholders
- [ ] Verify `Retry-After` header in 503 responses
- [ ] Confirm no critical market events expected
- [ ] Backup current configuration

**Post-maintenance**:
- [ ] Health check passes
- [ ] Test webhook with valid signature
- [ ] Verify NATS events publishing
- [ ] Monitor error rates for 15 minutes
- [ ] Announce maintenance completion

**Announcement Template**:
```
Gateway Maintenance: [START_TIME] - [END_TIME]
Impact: Webhooks will receive 503 responses during window
Action: Clients should retry after window using Retry-After header
Contact: [ON_CALL_CONTACT]
```

## Backpressure & NATS Outage Handling

### Fail-Closed Policy
- **Buffer size**: 1000 messages in memory (30-second window)
- **Behavior**: Return 503 GW-005 when NATS unavailable
- **Rationale**: Better to reject than lose market signals

### NATS Health Verification
```bash
# Check NATS server status
nats server ping

# List streams
nats stream ls

# Check consumer status
nats consumer info trading-events gateway-consumer

# View consumer lag
nats consumer info trading-events gateway-consumer | grep "Num Pending"
```

### Recovery Procedure
```bash
# 1. Check NATS connectivity
telnet nats-server 4222

# 2. Restart NATS if needed
sudo systemctl restart nats-server

# 3. Verify stream exists
nats stream info trading-events

# 4. Recreate consumer if needed
nats consumer rm trading-events gateway-consumer
nats consumer add trading-events gateway-consumer \
  --pull --deliver=all --max-inflight=10 --ack-wait=30s

# 5. Restart gateway
sudo systemctl restart at-gateway

# 6. Verify recovery
curl -f http://localhost:8001/healthz | jq .nats
```

## Rate Limiting Operations

### Adjust Rate Limits
```bash
# Temporary increase (requires restart)
export RATE_LIMIT_RPS=200
sudo systemctl restart at-gateway

# Verify new limit
echo $RATE_LIMIT_RPS

# Test rate limiting
for i in {1..250}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/healthz; done | sort | uniq -c
```

### Rate Limiting Verification
```bash
# Check 429 responses
curl -s http://localhost:8001/metrics | grep 'gateway_rate_limit_exceeded_total'

# Sample 429 response
curl -v http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{}' # (after exceeding limit)
# Expected: 429 with Retry-After header
```

### Per-Source Rate Limits (Future)
```bash
# Configuration format (when implemented)
# RATE_LIMIT_SOURCES="tradingview:100,custom:50"
# RATE_LIMIT_DEFAULT=25
```

## Security & Key Rotation

### Dual-Key Rotation Procedure
```bash
# 1. Deploy with both keys accepted
export API_KEY_HMAC_SECRET="old-secret,new-secret"
sudo systemctl restart at-gateway

# 2. Test both keys work
echo "Testing old key..."
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  -H "X-Nonce: $(uuidgen)" \
  -H "X-Signature: sha256=$(echo -n '{}' | openssl dgst -sha256 -hmac 'old-secret' | cut -d' ' -f2)" \
  -d '{}'

echo "Testing new key..."
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  -H "X-Nonce: $(uuidgen)" \
  -H "X-Signature: sha256=$(echo -n '{}' | openssl dgst -sha256 -hmac 'new-secret' | cut -d' ' -f2)" \
  -d '{}'

# 3. Update clients to new key
# 4. Remove old key
export API_KEY_HMAC_SECRET="new-secret"
sudo systemctl restart at-gateway

# 5. Verify old key rejected
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  -H "X-Nonce: $(uuidgen)" \
  -H "X-Signature: sha256=$(echo -n '{}' | openssl dgst -sha256 -hmac 'old-secret' | cut -d' ' -f2)" \
  -d '{}'
# Expected: 401 GW-001
```

### Rollback Plan
```bash
# Emergency rollback to old key
export API_KEY_HMAC_SECRET="old-secret"
sudo systemctl restart at-gateway

# Verify service operational
curl -f http://localhost:8001/healthz
```

## Dashboards and Alerts

### Primary Dashboard Panels

**Request Rate**:
```promql
sum(rate(gateway_webhooks_received_total[5m])) by (source, status)
```

**Error Rate**:
```promql
sum(rate(gateway_webhooks_received_total{status=~"[45].*"}[5m])) / sum(rate(gateway_webhooks_received_total[5m]))
```

**Latency Percentiles**:
```promql
histogram_quantile(0.95, sum(rate(gateway_webhook_duration_seconds_bucket[5m])) by (le))
histogram_quantile(0.99, sum(rate(gateway_webhook_duration_seconds_bucket[5m])) by (le))
```

**NATS Publish Success**:
```promql
sum(rate(gateway_nats_publish_total{status="success"}[5m]))
```

**Backpressure Events**:
```promql
increase(gateway_backpressure_total[5m])
```

### Alert Rules

**Critical Alerts** (immediate response):
- Service down: `up{job="at-gateway"} == 0` for >2 minutes
- High error rate: error rate >5% for >5 minutes
- NATS disconnected: `gateway_nats_errors_total` increasing
- Consumer lag critical: lag >1000 messages for >1 minute

**Warning Alerts** (business hours):
- High latency: p95 >200ms for >5 minutes
- Rate limiting active: `gateway_rate_limit_exceeded_total` increasing
- Authentication failures: `gateway_validation_errors_total{type="signature"}` spike

### Error Code to Alert Mapping
- **GW-001 spike** → "Authentication Failure Surge" alert
- **GW-004 increase** → "Rate Limiting Active" alert
- **GW-005 any** → "NATS Unavailable" critical alert
- **GW-011 enabled** → "Maintenance Mode" informational

## On-Call Drills

### Quarterly Drill Schedule

| Quarter | Scenario | Goal | Success Criteria |
|---------|----------|------|-------------------|
| Q1 | Invalid signature spike | Detect and investigate within 5 minutes | Identify root cause, no service restart needed |
| Q2 | NATS outage (60 seconds) | Service recovers within 60s of NATS restore | No crashes, <5% error rate post-recovery |
| Q3 | Rate limit breach | Proper 429 responses, stable p95 | Rate limiting active, no performance degradation |
| Q4 | Maintenance window | Clean maintenance mode operation | Correct 503 GW-011 responses, clean exit |

### Drill Scripts

**Invalid Signature Spike**:
```bash
# Simulate bad signatures
for i in {1..50}; do
  curl -s -X POST http://localhost:8001/webhook/tradingview \
    -H "Content-Type: application/json" \
    -H "X-Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    -H "X-Nonce: $(uuidgen)" \
    -H "X-Signature: sha256=invalid-signature" \
    -d '{}' &
done
wait

# Check metrics
curl -s http://localhost:8001/metrics | grep 'gateway_validation_errors_total.*signature'
```

**NATS Outage Simulation**:
```bash
# Stop NATS
docker stop nats-container

# Send requests (should get 503)
curl -v http://localhost:8001/webhook/tradingview -d '{}' -H "Content-Type: application/json"

# Wait 60 seconds, restart NATS
sleep 60
docker start nats-container

# Verify recovery
curl -f http://localhost:8001/healthz
```

**Rate Limit Test**:
```bash
# Generate traffic exceeding limit
RATE_LIMIT=$(echo $RATE_LIMIT_RPS)
for i in $(seq 1 $((RATE_LIMIT * 2))); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/healthz &
done | sort | uniq -c
# Should see mix of 200 and 429 responses
```

**Maintenance Mode Test**:
```bash
# Enable maintenance
export MAINTENANCE_MODE=true
sudo systemctl restart at-gateway

# Verify 503 responses
curl -v http://localhost:8001/webhook/tradingview -d '{}' -H "Content-Type: application/json"

# Disable maintenance
unset MAINTENANCE_MODE
sudo systemctl restart at-gateway

# Verify normal operation
curl -f http://localhost:8001/healthz
```

## Troubleshooting Playbooks

### GW-001: Invalid Signature

**Symptoms**: High 401 error rate, client complaints about rejected webhooks

**Investigation**:
```bash
# Check signature error rate
curl -s http://localhost:8001/metrics | grep 'gateway_validation_errors_total.*signature'

# Review recent signature failures
journalctl -u at-gateway --since "5 minutes ago" | grep GW-001 | jq .

# Check client IPs with signature issues
journalctl -u at-gateway --since "5 minutes ago" | grep signature | jq -r .client_ip | sort | uniq -c
```

**Likely Causes**:
- API key rotation without client update
- Client clock skew >30 seconds
- Client HMAC implementation bug

**Fix Steps**:
1. Verify current secret: `echo $API_KEY_HMAC_SECRET | wc -c` (should be >32)
2. Check for recent key rotation announcements
3. Test signature generation manually
4. Coordinate with client teams if needed

### GW-002: Replay Window Exceeded

**Symptoms**: 401 errors with timestamp/nonce issues

**Investigation**:
```bash
# Check replay errors
curl -s http://localhost:8001/metrics | grep 'gateway_validation_errors_total.*replay'

# Review timestamp issues
journalctl -u at-gateway --since "5 minutes ago" | grep GW-002 | jq '{corr_id, timestamp_provided, window_sec}'
```

**Fix Steps**:
1. Check client clock synchronization
2. Consider increasing `REPLAY_WINDOW_SEC` temporarily
3. Verify nonce uniqueness in client implementation

### GW-004: Rate Limit Exceeded

**Symptoms**: 429 responses, client timeout complaints

**Investigation**:
```bash
# Check rate limiting activity
curl -s http://localhost:8001/metrics | grep gateway_rate_limit_exceeded_total

# Review rate limit violations by source
journalctl -u at-gateway --since "5 minutes ago" | grep GW-004 | jq '{source, current_rate, limit}'
```

**Fix Steps**:
1. Determine if traffic increase is legitimate
2. Adjust `RATE_LIMIT_RPS` if needed
3. Implement per-source limits for specific clients
4. Consider burst capacity enhancements

### GW-005: NATS Unavailable

**Symptoms**: 503 errors, webhook processing failures

**Investigation**:
```bash
# Check NATS connection errors
curl -s http://localhost:8001/metrics | grep 'gateway_nats_errors_total.*connection'

# Review NATS status in logs
journalctl -u at-gateway --since "5 minutes ago" | grep GW-005 | jq '{nats_status, last_success}'

# Check NATS server health
nats server ping
nats stream ls
```

**Fix Steps**:
1. Restart NATS server if needed
2. Check network connectivity
3. Verify JetStream configuration
4. Recreate consumer if corrupted
5. Restart gateway service

### GW-011: Maintenance Mode

**Symptoms**: All requests receiving 503 responses

**Investigation**:
```bash
# Check maintenance mode status
echo $MAINTENANCE_MODE

# Verify maintenance responses
curl -v http://localhost:8001/webhook/tradingview -d '{}' -H "Content-Type: application/json"
```

**Fix Steps**:
1. Check if maintenance window is scheduled
2. Disable maintenance mode if unintentional
3. Verify proper Retry-After headers
4. Communicate status to stakeholders

## SLOs & Reporting

### Service Level Objectives

**Availability**:
- Target: 99.9% uptime (8.76 hours downtime/year)
- Measurement: Successful responses to `/healthz`
- Alerting: <99.5% over 5-minute window

**Latency**:
- Target: p95 webhook processing <100ms, p99 <500ms
- Measurement: `gateway_webhook_duration_seconds`
- Alerting: p95 >200ms over 2-minute window

**Consumer Lag**:
- Target: NATS consumer lag <100 messages
- Measurement: JetStream consumer info
- Alerting: Lag >1000 messages for >1 minute

**Error Rate**:
- Target: <0.5% error rate for valid requests
- Measurement: 5xx responses / total responses
- Alerting: >1% error rate over 5-minute window

### Monthly Review Checklist
- [ ] Review SLO compliance (availability, latency, error rate)
- [ ] Analyze top error codes and frequencies
- [ ] Check capacity trends (request volume, memory usage)
- [ ] Review security events (authentication failures)
- [ ] Update runbook based on recent incidents
- [ ] Validate alert thresholds and escalation paths

### Post-Incident Report Template
```
# Gateway Incident Report

## Timeline
- **Start**: [TIMESTAMP] - First alert/detection
- **Escalation**: [TIMESTAMP] - On-call engaged
- **Mitigation**: [TIMESTAMP] - Issue contained
- **Resolution**: [TIMESTAMP] - Full service restored

## Impact
- **Duration**: [MINUTES] total, [MINUTES] customer-facing
- **Error Rate**: [PERCENTAGE] peak, [COUNT] failed requests
- **Affected Sources**: [LIST]

## Root Cause
[DETAILED EXPLANATION]

## Metrics Before/After
- Request Rate: [BEFORE] → [AFTER] RPS
- Error Rate: [BEFORE] → [AFTER] %
- Latency p95: [BEFORE] → [AFTER] ms

## Configuration Changes
[LIST ANY CONFIG MODIFICATIONS]

## Lessons Learned
1. [LESSON 1]
2. [LESSON 2]

## Action Items
- [ ] [ACTION 1] - [OWNER] - [DUE DATE]
- [ ] [ACTION 2] - [OWNER] - [DUE DATE]
```

## Appendix

### Common Curl Commands

**Signed TradingView Request**:
```bash
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
NONCE=$(uuidgen)
BODY='{"ticker":"EURUSD","action":"buy","price":1.0945,"time":"'$TIMESTAMP'"}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$API_KEY_HMAC_SECRET" | cut -d' ' -f2)

curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json; charset=utf-8" \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-Nonce: $NONCE" \
  -H "X-Signature: sha256=$SIGNATURE" \
  -d "$BODY"
```

**Generic Webhook**:
```bash
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
NONCE=$(uuidgen)
BODY='{"source":"test","instrument":"BTCUSD","timestamp":"'$TIMESTAMP'","payload":{"price":45000}}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$API_KEY_HMAC_SECRET" | cut -d' ' -f2)

curl -X POST http://localhost:8001/webhook/generic \
  -H "Content-Type: application/json; charset=utf-8" \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-Nonce: $NONCE" \
  -H "X-Signature: sha256=$SIGNATURE" \
  -d "$BODY"
```

### NATS CLI Cheatsheet

```bash
# Basic connectivity
nats server ping
nats server info

# Stream management
nats stream ls
nats stream info trading-events
nats stream purge trading-events

# Consumer management
nats consumer ls trading-events
nats consumer info trading-events gateway-consumer
nats consumer rm trading-events gateway-consumer

# Create consumer
nats consumer add trading-events gateway-consumer \
  --pull --deliver=all --max-inflight=10 --ack-wait=30s

# Monitor messages
nats sub "signals.*"
nats pub signals.raw "test message"

# Stream statistics
nats stream report
nats consumer report trading-events
```

### Environment Reference

**Sample .env.production** (non-secrets):
```bash
# Service Configuration
PORT=8001
LOG_LEVEL=INFO
SERVICE_NAME=at-gateway
ENV=production

# NATS Configuration
NATS_URL=nats://nats-cluster:4222
NATS_STREAM=trading-events
NATS_SUBJECT_SIGNALS_RAW=signals.raw
NATS_SUBJECT_SIGNALS_NORMALIZED=signals.normalized
NATS_DURABLE=gateway-consumer

# Rate Limiting
RATE_LIMIT_RPS=100
ALLOWED_SOURCES=tradingview,custom,partner

# Security
REPLAY_WINDOW_SEC=300
IDEMPOTENCY_TTL_SEC=3600

# Monitoring
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus

# Maintenance
MAINTENANCE_MODE=false

# Secrets (set separately)
# API_KEY_HMAC_SECRET=<from-secrets-manager>
```

## Escalation

**Primary contact**: Platform Engineering team
**Secondary**: Trading Operations team
**Escalation path**: Platform → Trading → CTO

**Critical incidents** (immediate escalation):
- Service down >5 minutes
- Data loss or corruption
- Security breach (invalid signatures bypassed)
- Regulatory compliance impact

**Contact Information**:
- Platform Team: [SLACK_CHANNEL] / [PAGERDUTY_SERVICE]
- Trading Ops: [SLACK_CHANNEL] / [PHONE]
- Executive: [ESCALATION_PROCEDURE]

**Communication Channels**:
- **Internal**: #trading-platform-alerts
- **External**: [CLIENT_STATUS_PAGE]
- **Regulatory**: [COMPLIANCE_CONTACT]
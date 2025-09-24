# Execution Simulator Service Runbook

## Service Summary

**What it does**: Consumes order intent decisions from agents via NATS, simulates realistic execution fills with delays and slippage, then publishes execution confirmations and reconciliation events.

**Inbound**: NATS events on `decisions.order_intent` subject
**Outbound**: NATS events on `executions.fill` and `executions.reconcile` subjects

**Critical dependencies**:
- NATS JetStream (required for operation)
- at-core schemas (for event validation)

**Service criticality**: Medium - affects trading strategy testing but not production execution

## What Healthy Looks Like

### Health Checklist
- ✅ `/healthz` returns `{"ok":true,"nats":"connected","processor_status":"active"}` within <50ms
- ✅ Grafana panels show: processing rate steady, validation errors <1%, simulation latency <2s
- ✅ Prometheus counters increasing: `exec_sim_orders_received_total{status="success"}`, `exec_sim_fills_generated_total`
- ✅ NATS consumer lag <100 messages on `decisions.order_intent` subject
- ✅ Resource usage: CPU <70%, memory RSS stable
- ✅ No critical alerts firing (NATS disconnected, high error rate, buffer overflow)

### Quick Verification
```bash
# Health check
curl -f http://localhost:8004/healthz | jq '.ok and (.nats == "connected") and (.processor_status == "active")'

# Recent successful order processing
curl -s http://localhost:8004/metrics | grep 'exec_sim_orders_received_total.*success' | tail -1

# Fill generation rate
curl -s http://localhost:8004/metrics | grep 'exec_sim_fills_generated_total' | awk '{sum+=$2} END {print "Fills generated:", sum+0}'

# Validation error rate (should be low)
curl -s http://localhost:8004/metrics | grep 'exec_sim_validation_errors_total' | awk '{sum+=$2} END {print "Validation errors:", sum+0}'

# Consumer lag check
nats consumer info trading-events exec-sim-consumer | grep "Num Pending" | awk '{print $3}'

# Buffer status
curl -s http://localhost:8004/metrics | grep 'exec_sim_pending_events_count' | awk '{print "Pending events:", $2}'
```

## Health Checks

### /healthz Endpoint
```bash
curl http://localhost:8004/healthz
```

**Response Fields**:
- `ok: true` - Service is operational
- `uptime_s` - Seconds since service start
- `nats: "connected"` - NATS connection status
- `processor_status: "active"` - Event processor status
- `pending_events` - Number of buffered events
- `version` - Service version

**NATS Status Values**:
- `connected`: Normal operation, consuming and publishing successfully
- `degraded`: Connected but high latency or intermittent errors
- `disconnected`: Cannot reach NATS, service buffering events

**Processor Status Values**:
- `active`: Processing events normally
- `stopped`: Event processing halted (usually due to NATS failure)
- `degraded`: Processing with errors or reduced capacity

## Simulation Parameter Tuning

### Configuration
- **Execution delay**: `SIMULATION_MIN_DELAY_MS=100`, `SIMULATION_MAX_DELAY_MS=2000`
- **Partial fills**: `SIMULATION_PARTIAL_FILL_CHANCE=0.1` (10% probability)
- **Slippage**: `SIMULATION_SLIPPAGE_BPS=2` (2 basis points maximum)
- **Buffer size**: 1000 events maximum during NATS outages

### Tuning Guide

| Symptom | Investigation | Action |
|---------|---------------|--------|
| Unrealistic execution speed | Check simulation delay configuration | Increase `SIMULATION_MIN_DELAY_MS` and `SIMULATION_MAX_DELAY_MS` |
| Too many partial fills | Monitor `exec_sim_fills_generated_total{fill_type="partial"}` | Decrease `SIMULATION_PARTIAL_FILL_CHANCE` |
| Insufficient execution realism | Review agent feedback on execution quality | Increase `SIMULATION_SLIPPAGE_BPS` for more realistic slippage |
| High memory usage | Monitor pending events gauge | Decrease buffer size or improve NATS stability |

### Monitoring Commands
```bash
# Simulation timing distribution
curl -s http://localhost:8004/metrics | grep exec_sim_simulation_duration_seconds

# Fill type distribution
curl -s http://localhost:8004/metrics | grep 'exec_sim_fills_generated_total{fill_type'

# Slippage impact
curl -s http://localhost:8004/metrics | grep 'exec_sim_simulation_results_total'

# Buffer utilization
curl -s http://localhost:8004/metrics | grep exec_sim_pending_events_count
```

## Event Processing Monitoring

### Processing Pipeline Health
```bash
# Event consumption rate
curl -s http://localhost:8004/metrics | grep 'exec_sim_orders_received_total{status="success"}'

# Processing duration
curl -s http://localhost:8004/metrics | grep exec_sim_simulation_duration_seconds_bucket

# Publishing success rate
curl -s http://localhost:8004/metrics | grep 'exec_sim_nats_publish_errors_total'

# Schema validation errors
curl -s http://localhost:8004/metrics | grep exec_sim_validation_errors_total
```

### NATS Consumer Management
```bash
# Check consumer status
nats consumer info trading-events exec-sim-consumer

# Monitor consumer lag
watch 'nats consumer info trading-events exec-sim-consumer | grep "Num Pending"'

# Reset consumer if needed (caution: may cause reprocessing)
nats consumer rm trading-events exec-sim-consumer
# Service will recreate consumer on restart
```

## Failure Modes & Recovery

### NATS Unavailable (Fail-Stop Mode)
**Symptoms**:
- Health check shows `nats: "disconnected"`, `ok: false`
- `exec_sim_pending_events_count` increasing
- No fill events being published

**Recovery Actions**:
1. Check NATS server status: `nats server check`
2. Verify NATS connectivity: `nats ping`
3. Restart NATS if needed: `docker compose restart nats`
4. Monitor service recovery: watch pending events decrease
5. If buffer overflow (>1000 events), restart service

### Schema Validation Failures
**Symptoms**:
- Increasing `exec_sim_validation_errors_total` metrics
- No fill events for certain order intents
- Error logs showing schema validation failures

**Recovery Actions**:
1. Check at-core schema versions for compatibility
2. Review recent agent deployments for schema changes
3. Update service if schema version mismatch
4. Monitor validation error rate after fixes

### High Processing Latency
**Symptoms**:
- `exec_sim_simulation_duration_seconds` p95 >5 seconds
- Consumer lag increasing on `decisions.order_intent`
- Agents reporting slow execution feedback

**Recovery Actions**:
1. Check system resource usage (CPU, memory)
2. Review simulation delay configuration
3. Scale service horizontally if needed
4. Optimize simulation algorithm if latency excessive

### Memory Buffer Overflow
**Symptoms**:
- `exec_sim_pending_events_count` approaching 1000
- Service log warnings about buffer capacity
- Health check showing high pending_events

**Recovery Actions**:
1. Restore NATS connectivity immediately
2. Monitor buffer drain rate
3. If buffer full, restart service (events may be lost)
4. Consider increasing buffer size if frequent occurrence

## Performance Optimization

### Throughput Tuning
```bash
# Monitor processing rate
curl -s http://localhost:8004/metrics | grep rate_total | grep success

# Check for bottlenecks
top -p $(pgrep -f at_exec_sim)

# NATS publishing performance
curl -s http://localhost:8004/metrics | grep nats_publish_errors_total
```

### Resource Management
- **Memory**: Service should use <500MB RSS under normal load
- **CPU**: Sustained usage should remain <70% of allocated capacity
- **Network**: NATS publishing rate limited by network bandwidth

### Scaling Considerations
- **Horizontal scaling**: Multiple instances can consume from same NATS subject
- **Load balancing**: NATS JetStream provides automatic load balancing
- **Partitioning**: Consider instrument-based partitioning for high volume

## Alerting and SLOs

### Critical Alerts (Immediate Response)
- **Service down**: Health check failing for >2 minutes
- **NATS disconnected**: nats status "disconnected" for >5 minutes
- **Buffer overflow**: pending_events >900 (approaching limit)
- **High error rate**: Validation errors >5% for >10 minutes

### Warning Alerts (Business Hours Response)
- **High processing latency**: p95 simulation duration >3 seconds
- **Consumer lag**: NATS consumer lag >500 messages
- **Memory usage**: RSS >80% of allocated memory
- **Low throughput**: Processing rate <50% of historical average

### Service Level Objectives (SLOs)
- **Availability**: 99.9% uptime during market hours
- **Processing latency**: p95 <2 seconds end-to-end
- **Event loss**: <0.01% during NATS outages
- **Error rate**: <1% validation failures under normal conditions

## Troubleshooting Guide

### Common Issues

#### "No fill events generated"
1. Check NATS consumer subscription: `nats consumer info trading-events exec-sim-consumer`
2. Verify order intent events are published: `nats sub decisions.order_intent`
3. Check schema validation errors in logs
4. Verify correlation ID presence in order intents

#### "Simulation taking too long"
1. Check simulation delay configuration
2. Monitor system resource usage
3. Review simulation algorithm complexity
4. Consider async processing improvements

#### "High memory usage"
1. Check pending events buffer size
2. Monitor for memory leaks in simulation logic
3. Review event processing efficiency
4. Consider garbage collection tuning

#### "NATS publishing failures"
1. Verify NATS JetStream configuration
2. Check network connectivity to NATS
3. Monitor NATS server resource usage
4. Review publishing retry logic

### Log Analysis
```bash
# Recent errors
journalctl -u at-exec-sim --since "1 hour ago" --grep ERROR

# Schema validation failures
journalctl -u at-exec-sim --since "1 hour ago" --grep "validation_error"

# NATS connection issues
journalctl -u at-exec-sim --since "1 hour ago" --grep "nats"

# Simulation performance
journalctl -u at-exec-sim --since "1 hour ago" --grep "simulation_duration"
```

## Maintenance Procedures

### Service Restart
```bash
# Graceful restart (allows pending events to process)
sudo systemctl reload at-exec-sim

# Full restart (if graceful fails)
sudo systemctl restart at-exec-sim

# Verify restart success
curl http://localhost:8004/healthz
```

### Configuration Updates
1. Update environment variables in service configuration
2. Validate new configuration with test order
3. Reload service to apply changes
4. Monitor metrics for expected behavior changes

### Schema Updates
1. Deploy new at-core schemas to shared location
2. Update service dependencies
3. Test schema validation with sample events
4. Deploy service update with backward compatibility
5. Monitor validation error rates post-deployment

## Rollback Procedures

### Service Rollback
1. Stop current service: `sudo systemctl stop at-exec-sim`
2. Deploy previous service version
3. Restore previous configuration
4. Start service: `sudo systemctl start at-exec-sim`
5. Verify health and processing resumption

### Configuration Rollback
1. Restore previous environment configuration
2. Reload service: `sudo systemctl reload at-exec-sim`
3. Monitor service behavior for stability
4. Verify simulation parameters working correctly

### Emergency Shutdown
```bash
# Stop processing new events (keeps service alive for monitoring)
# This requires implementing a maintenance mode flag
export MAINTENANCE_MODE=true
sudo systemctl reload at-exec-sim

# Complete shutdown if necessary
sudo systemctl stop at-exec-sim
```
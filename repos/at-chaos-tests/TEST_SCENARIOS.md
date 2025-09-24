# Chaos Testing Scenarios

This document describes the chaos testing scenarios available for the agentic trading system.

## Quick Start

```bash
# Start the system with chaos testing
docker compose -f docker-compose.dev.yml up -d

# Check chaos service
curl localhost:8008/healthz

# List available experiment templates
curl localhost:8008/templates

# Run a basic chaos experiment
curl -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{"type": "nats_latency", "delay_ms": 100, "duration_s": 60}'
```

## Test Categories

### 1. NATS Latency Injection Tests

Test system resilience to network latency in the message bus.

#### Mild Latency Test
```bash
curl -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "type": "nats_latency",
    "delay_ms": 50,
    "duration_s": 120,
    "jitter_pct": 0.2
  }'
```

#### Severe Latency Test
```bash
curl -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "type": "nats_latency",
    "delay_ms": 500,
    "duration_s": 180,
    "jitter_pct": 0.3
  }'
```

**Expected Behavior:**
- System should continue operating with higher latency
- Timeouts may increase but no data loss
- Processing rates should decrease proportionally

### 2. Service Failure Tests

Simulate various service failure scenarios.

#### Agent Crash Test
```bash
curl -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "type": "service_failure",
    "service": "agent",
    "failure_type": "crash",
    "duration_s": 30
  }'
```

#### Gateway Hang Test
```bash
curl -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "type": "service_failure",
    "service": "gateway",
    "failure_type": "hang",
    "duration_s": 45
  }'
```

**Expected Behavior:**
- Other services should continue operating
- Messages should queue during service downtime
- Recovery should process queued messages
- Health checks should report service failures

### 3. Backpressure Tests

Test system behavior under high message volume.

#### 10x Load Test
```bash
curl -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "type": "backpressure",
    "rate_multiplier": 10,
    "duration_s": 300
  }'
```

#### Consumer Crash Scenario
```bash
curl -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "type": "backpressure",
    "rate_multiplier": 50,
    "duration_s": 180
  }'
```

**Expected Behavior:**
- NATS should buffer messages effectively
- Consumers should not crash under load
- Processing should catch up after load decreases
- Metrics should show increased latency but stable throughput

### 4. Load Testing

Stress test individual service endpoints.

#### High RPS Test
```bash
curl -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "type": "load_test",
    "rps": 200,
    "duration_s": 600,
    "payload_size": 4096
  }'
```

**Expected Behavior:**
- Gateway should handle sustained load
- Response times should remain reasonable (<1s)
- No dropped requests or errors
- Auto-scaling should engage if configured

### 5. Duplicate Message Tests

Test idempotency and duplicate handling.

#### 20% Duplicate Rate
```bash
curl -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "type": "duplicate_messages",
    "duplicate_rate": 0.2,
    "duration_s": 240
  }'
```

**Expected Behavior:**
- System should detect and ignore duplicates
- Processing should remain consistent
- No double-execution of trading decisions
- Metrics should track duplicate detection

## Combined Scenarios

### Chaos Engineering Suite

Run multiple chaos experiments simultaneously:

```bash
# Start latency injection
LATENCY_EXP=$(curl -s -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{"type": "nats_latency", "delay_ms": 100, "duration_s": 300}' | jq -r .experiment_id)

# Start backpressure after 1 minute
sleep 60
BACKPRESSURE_EXP=$(curl -s -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{"type": "backpressure", "rate_multiplier": 5, "duration_s": 180}' | jq -r .experiment_id)

# Add duplicates after another minute
sleep 60
DUPLICATE_EXP=$(curl -s -X POST localhost:8008/experiments \
  -H "Content-Type: application/json" \
  -d '{"type": "duplicate_messages", "duplicate_rate": 0.1, "duration_s": 120}' | jq -r .experiment_id)

# Monitor all experiments
curl localhost:8008/experiments
```

### Production Readiness Test

Comprehensive test simulating production conditions:

```bash
# 1. Baseline load
curl -X POST localhost:8008/experiments \
  -d '{"type": "load_test", "rps": 50, "duration_s": 1800}'

# 2. Add network issues (after 5 minutes)
curl -X POST localhost:8008/experiments \
  -d '{"type": "nats_latency", "delay_ms": 200, "duration_s": 600}'

# 3. Service failure (after 10 minutes)
curl -X POST localhost:8008/experiments \
  -d '{"type": "service_failure", "service": "agent", "failure_type": "crash", "duration_s": 60}'

# 4. Recovery validation (after 15 minutes)
curl -X POST localhost:8008/experiments \
  -d '{"type": "backpressure", "rate_multiplier": 3, "duration_s": 300}'
```

## Monitoring During Tests

### Key Metrics to Watch

1. **Message Processing Rates**
   ```promql
   rate(gateway_webhooks_received_total[5m])
   rate(mcp_signals_received_total[5m])
   rate(mcp_decisions_generated_total[5m])
   ```

2. **Processing Latency**
   ```promql
   histogram_quantile(0.95, rate(mcp_processing_duration_seconds_bucket[5m]))
   ```

3. **Error Rates**
   ```promql
   rate(gateway_validation_errors_total[5m])
   rate(mcp_errors_total[5m])
   ```

4. **System Resources**
   ```promql
   rate(container_cpu_usage_seconds_total[5m])
   container_memory_usage_bytes
   ```

### Grafana Dashboards

- **Golden Path Dashboard**: Real-time flow monitoring
- **Chaos Testing Dashboard**: Experiment tracking and impact
- **System Health Dashboard**: Resource utilization

### Log Correlation

During chaos tests, logs are tagged with `_chaos_*` fields for easy filtering:

```bash
# View chaos-related logs
docker compose logs | grep "_chaos_"

# Monitor specific experiment impact
docker compose logs | grep "chaos_backpressure_123456"
```

## Success Criteria

### System Should:
- ✅ Continue processing messages during chaos events
- ✅ Recover gracefully after chaos events end
- ✅ Maintain data consistency (no lost or duplicate processing)
- ✅ Show appropriate error rates in metrics
- ✅ Auto-heal when possible

### System Should NOT:
- ❌ Crash permanently
- ❌ Lose messages
- ❌ Process duplicates
- ❌ Generate invalid trading decisions
- ❌ Exceed 5% error rate under normal chaos

## Cleanup

```bash
# Stop all active experiments
for exp_id in $(curl -s localhost:8008/experiments | jq -r '.experiments[].experiment_id'); do
  curl -X DELETE localhost:8008/experiments/$exp_id
done

# Check system recovery
curl localhost:8008/healthz
curl localhost:8001/healthz
curl localhost:8002/healthz
```
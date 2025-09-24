#!/bin/bash
# CI Smoke Test - Comprehensive end-to-end validation
# Exit on first error
set -e

echo "==================================================="
echo "CI SMOKE TEST - Trading Architecture"
echo "==================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
RETRY_COUNT=0
MAX_RETRIES=30
TEST_FAILURES=0

log_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_fail() {
    echo -e "${RED}❌ $1${NC}"
    TEST_FAILURES=$((TEST_FAILURES + 1))
}

log_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

wait_for_service() {
    local url=$1
    local service=$2
    local max_wait=60
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            log_pass "$service is ready"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done

    log_fail "$service failed to start within $max_wait seconds"
    return 1
}

# Start services
log_info "Starting services..."
docker compose -f docker-compose.dev.yml up -d

# Wait for critical services
log_info "Waiting for services to be ready..."
wait_for_service "http://localhost:8001/healthz" "Gateway"
wait_for_service "http://localhost:8002/healthz" "Agent"
wait_for_service "http://localhost:8004/healthz" "Exec-Sim"

# Verify NATS JetStream consumer exists
log_info "Verifying JetStream consumer configuration..."
CONSUMER_INFO=$(docker run --rm --network agentic-trading-architecture-full_default \
    natsio/nats-box:latest \
    nats -s nats://nats:4222 con info trading-events exec-sim-consumer --json 2>/dev/null || echo "{}")

if echo "$CONSUMER_INFO" | jq -e '.config.durable_name' > /dev/null 2>&1; then
    log_pass "Consumer 'exec-sim-consumer' exists"
    echo "  Filter subject: $(echo "$CONSUMER_INFO" | jq -r '.config.filter_subject')"
    echo "  Pending messages: $(echo "$CONSUMER_INFO" | jq -r '.num_pending')"
else
    log_fail "Consumer 'exec-sim-consumer' not found"
fi

# Check health endpoints
log_info "Checking service health..."
for port in 8001 8002 8004; do
    HEALTH=$(curl -s "http://localhost:$port/healthz" | jq -r '.ok')
    if [ "$HEALTH" = "true" ]; then
        log_pass "Service on port $port is healthy"
    else
        log_fail "Service on port $port is unhealthy"
        curl -s "http://localhost:$port/healthz" | jq '.'
    fi
done

# Verify exec-sim consumer health
log_info "Checking exec-sim consumer configuration health..."
EXEC_HEALTH=$(curl -s "http://localhost:8004/healthz" | jq '.consumer')
if [ "$(echo "$EXEC_HEALTH" | jq -r '.status')" = "healthy" ]; then
    log_pass "Exec-sim consumer configuration is healthy"
else
    log_fail "Exec-sim consumer configuration is degraded"
    echo "$EXEC_HEALTH" | jq '.'
fi

# Get initial metrics
log_info "Recording initial metrics..."
GATEWAY_WEBHOOKS_BEFORE=$(curl -s localhost:8001/metrics | grep 'gateway_webhooks_received_total{source="test",status="success"}' | awk '{print $2}' | cut -d'.' -f1 || echo 0)
EXEC_ORDERS_BEFORE=$(curl -s localhost:8004/metrics | grep 'exec_sim_orders_received_total{status="valid"}' | awk '{print $2}' | cut -d'.' -f1 || echo 0)

log_info "Initial metrics:"
echo "  Gateway webhooks: ${GATEWAY_WEBHOOKS_BEFORE:-0}"
echo "  Exec-sim orders: ${EXEC_ORDERS_BEFORE:-0}"

# Test 1: Direct NATS publish
log_info "Test 1: Direct NATS message publishing..."
DIRECT_MSG='{"corr_id":"ci_test_direct_'$(date +%s)'","agent_id":"ci_test","instrument":"AAPL","side":"buy","quantity":100,"order_type":"market","timestamp":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}'

docker run --rm --network agentic-trading-architecture-full_default \
    natsio/nats-box:latest \
    nats -s nats://nats:4222 pub decisions.order_intent "$DIRECT_MSG"

sleep 2

EXEC_ORDERS_AFTER_DIRECT=$(curl -s localhost:8004/metrics | grep 'exec_sim_orders_received_total{status="valid"}' | awk '{print $2}' | cut -d'.' -f1 || echo 0)
if [ "$EXEC_ORDERS_AFTER_DIRECT" -gt "$EXEC_ORDERS_BEFORE" ]; then
    log_pass "Direct NATS publish successful (orders: $EXEC_ORDERS_BEFORE → $EXEC_ORDERS_AFTER_DIRECT)"
else
    log_fail "Direct NATS publish failed (orders unchanged: $EXEC_ORDERS_BEFORE)"
fi

# Test 2: End-to-end webhook with HMAC
log_info "Test 2: End-to-end webhook flow with HMAC authentication..."
SECRET="test-secret"
TIMESTAMP=$(date +%s)
NONCE="ci-test-$(date +%s%N)"
BODY='{"instrument":"TSLA","price":850.00,"signal":"buy","strength":0.95}'
MESSAGE="${TIMESTAMP}.${NONCE}.${BODY}"
SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$SECRET" -hex | cut -d' ' -f2)

HTTP_STATUS=$(curl -X POST http://localhost:8001/webhook/test \
    -H "Content-Type: application/json" \
    -H "X-Timestamp: $TIMESTAMP" \
    -H "X-Nonce: $NONCE" \
    -H "X-Signature: $SIGNATURE" \
    -d "$BODY" \
    -s -w "%{http_code}" -o /tmp/webhook_response.json)

if [ "$HTTP_STATUS" = "200" ]; then
    log_pass "Webhook accepted with valid HMAC (HTTP $HTTP_STATUS)"
    cat /tmp/webhook_response.json | jq '.'
else
    log_fail "Webhook failed (HTTP $HTTP_STATUS)"
    cat /tmp/webhook_response.json
fi

sleep 5  # Wait for async processing

# Check final metrics
log_info "Validating metric changes..."
GATEWAY_WEBHOOKS_AFTER=$(curl -s localhost:8001/metrics | grep 'gateway_webhooks_received_total{source="test",status="success"}' | awk '{print $2}' | cut -d'.' -f1 || echo 0)
EXEC_ORDERS_AFTER=$(curl -s localhost:8004/metrics | grep 'exec_sim_orders_received_total{status="valid"}' | awk '{print $2}' | cut -d'.' -f1 || echo 0)

log_info "Final metrics:"
echo "  Gateway webhooks: ${GATEWAY_WEBHOOKS_BEFORE:-0} → ${GATEWAY_WEBHOOKS_AFTER:-0}"
echo "  Exec-sim orders: ${EXEC_ORDERS_BEFORE:-0} → ${EXEC_ORDERS_AFTER:-0}"

# Validate increments
if [ "$GATEWAY_WEBHOOKS_AFTER" -gt "$GATEWAY_WEBHOOKS_BEFORE" ]; then
    log_pass "Gateway webhook counter incremented"
else
    log_fail "Gateway webhook counter did not increment"
fi

if [ "$EXEC_ORDERS_AFTER" -gt "$EXEC_ORDERS_BEFORE" ]; then
    log_pass "Exec-sim order counter incremented"
else
    log_fail "Exec-sim order counter did not increment"
fi

# Test 3: Idempotency check
log_info "Test 3: Idempotency validation..."
IDEM_KEY="ci-idem-$(date +%s)"
IDEM_BODY='{"instrument":"GOOG","price":140.00,"signal":"sell","strength":0.60}'
TIMESTAMP2=$(date +%s)
NONCE2="ci-idem-$(date +%s%N)"
MESSAGE2="${TIMESTAMP2}.${NONCE2}.${IDEM_BODY}"
SIGNATURE2=$(echo -n "$MESSAGE2" | openssl dgst -sha256 -hmac "$SECRET" -hex | cut -d' ' -f2)

# Send first request
RESPONSE1=$(curl -X POST http://localhost:8001/webhook/test \
    -H "Content-Type: application/json" \
    -H "X-Timestamp: $TIMESTAMP2" \
    -H "X-Nonce: $NONCE2" \
    -H "X-Signature: $SIGNATURE2" \
    -H "X-Idempotency-Key: $IDEM_KEY" \
    -d "$IDEM_BODY" -s)

# Send duplicate with same idempotency key
TIMESTAMP3=$(date +%s)
NONCE3="ci-idem2-$(date +%s%N)"
MESSAGE3="${TIMESTAMP3}.${NONCE3}.${IDEM_BODY}"
SIGNATURE3=$(echo -n "$MESSAGE3" | openssl dgst -sha256 -hmac "$SECRET" -hex | cut -d' ' -f2)

RESPONSE2=$(curl -X POST http://localhost:8001/webhook/test \
    -H "Content-Type: application/json" \
    -H "X-Timestamp: $TIMESTAMP3" \
    -H "X-Nonce: $NONCE3" \
    -H "X-Signature: $SIGNATURE3" \
    -H "X-Idempotency-Key: $IDEM_KEY" \
    -d "$IDEM_BODY" -s)

if [ "$(echo "$RESPONSE1" | jq -r '.corr_id')" = "$(echo "$RESPONSE2" | jq -r '.corr_id')" ]; then
    log_pass "Idempotency working: same corr_id returned"
else
    log_fail "Idempotency failed: different corr_ids"
fi

# Test 4: Schema validation with unknown fields
log_info "Test 4: Schema validation with unknown fields..."
SCHEMA_MSG='{"corr_id":"ci_schema_'$(date +%s)'","agent_id":"ci","instrument":"MSFT","side":"buy","quantity":50,"order_type":"limit","price_limit":300,"timestamp":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'","unknown_field1":"test","custom_metadata":{"key":"value"}}'

docker run --rm --network agentic-trading-architecture-full_default \
    natsio/nats-box:latest \
    nats -s nats://nats:4222 pub decisions.order_intent "$SCHEMA_MSG"

sleep 2

# Check for unknown field metrics
UNKNOWN_FIELDS=$(curl -s localhost:8004/metrics | grep 'exec_sim_unknown_fields_total' | wc -l)
if [ "$UNKNOWN_FIELDS" -gt 0 ]; then
    log_pass "Unknown field tracking is working"
else
    log_info "No unknown fields tracked (may be expected)"
fi

# Summary
echo ""
echo "==================================================="
echo "SMOKE TEST SUMMARY"
echo "==================================================="

if [ $TEST_FAILURES -eq 0 ]; then
    log_pass "All tests passed! ✨"
    exit 0
else
    log_fail "$TEST_FAILURES test(s) failed"
    exit 1
fi
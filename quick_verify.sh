#!/bin/bash
# One-liner verification as suggested
echo "Quick verification: Publishing test order and checking metrics..."

# Publish test order
nats pub decisions.order_intent '{"corr_id":"quick_'$(date +%s)'","agent_id":"verify","instrument":"ES","side":"buy","quantity":1,"price_limit":4800.25,"order_type":"limit","timestamp":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}' 2>/dev/null || \
docker run --rm --network agentic-trading-architecture-full_default natsio/nats-box:latest \
  nats -s nats://nats:4222 pub decisions.order_intent '{"corr_id":"quick_'$(date +%s)'","agent_id":"verify","instrument":"ES","side":"buy","quantity":1,"price_limit":4800.25,"order_type":"limit","timestamp":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}'

sleep 1

echo "Metrics after publishing:"
curl -s localhost:8004/metrics | grep -E 'orders_received_total|fills_generated_total' | grep -v "#"
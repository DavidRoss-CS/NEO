#!/bin/bash

echo "🚀 NEO v1.0.0 Real-World Trading Pipeline Demo"
echo "=" | tr ' ' '='
echo "=" | tr ' ' '=' | head -c 50
echo

# Configuration
GATEWAY_URL="http://localhost:8001"
GRAFANA_URL="http://localhost:3000"
PROMETHEUS_URL="http://localhost:9090"
HMAC_SECRET="test-secret"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to generate HMAC signature
generate_signature() {
    local body="$1"
    echo -n "$body" | openssl dgst -sha256 -hmac "$HMAC_SECRET" | cut -d' ' -f2
}

# Function to check service health
check_health() {
    echo -e "${BLUE}📊 Checking NEO Service Health...${NC}"

    # Check Gateway
    if curl -s -f "$GATEWAY_URL/healthz" > /dev/null; then
        echo -e "   ✅ Gateway: healthy ($GATEWAY_URL)"
    else
        echo -e "   ❌ Gateway: unhealthy"
        return 1
    fi

    # Check Prometheus
    if curl -s -f "$PROMETHEUS_URL/-/healthy" > /dev/null; then
        echo -e "   ✅ Prometheus: healthy ($PROMETHEUS_URL)"
    else
        echo -e "   ⚠️  Prometheus: not available"
    fi

    # Check Grafana
    if curl -s -f "$GRAFANA_URL/api/health" > /dev/null; then
        echo -e "   ✅ Grafana: healthy ($GRAFANA_URL)"
    else
        echo -e "   ⚠️  Grafana: not available"
    fi

    return 0
}

# Function to get current metrics
get_metrics() {
    echo -e "\n${BLUE}📊 Current Gateway Metrics:${NC}"

    local metrics_output=$(curl -s "$GATEWAY_URL/metrics")

    # Extract key metrics
    local webhooks_received=$(echo "$metrics_output" | grep "^gateway_webhooks_received_total" | tail -1 | awk '{print $NF}')
    local webhooks_processed=$(echo "$metrics_output" | grep "^gateway_webhook_duration_seconds_count" | tail -1 | awk '{print $NF}')
    local validation_errors=$(echo "$metrics_output" | grep "gateway_validation_errors_total" | tail -1 | awk '{print $NF}')

    echo "   webhooks_received: ${webhooks_received:-0}"
    echo "   webhooks_processed: ${webhooks_processed:-0}"
    echo "   validation_errors: ${validation_errors:-0}"
}

# Function to send trading signal
send_signal() {
    local signal_name="$1"
    local body="$2"
    local endpoint="${3:-tradingview}"

    echo -e "\n📡 ${signal_name}"

    # Generate HMAC signature
    local signature="sha256=$(generate_signature "$body")"

    # Send webhook
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-Signature: $signature" \
        -H "User-Agent: NEO-Demo/1.0" \
        -d "$body" \
        "$GATEWAY_URL/webhook/$endpoint")

    local http_status=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    local response_body=$(echo "$response" | sed -e 's/HTTPSTATUS:.*//g')

    if [ "$http_status" -eq 200 ]; then
        echo -e "   ✅ Successfully processed (HTTP $http_status)"
    else
        echo -e "   ❌ Failed (HTTP $http_status): $response_body"
    fi

    return $([[ "$http_status" == "200" ]])
}

# Main demo function
main() {
    # Check service health
    if ! check_health; then
        echo -e "\n${RED}⚠️  Gateway service not available. Please start the NEO infrastructure first.${NC}"
        echo "   Run: docker run --network neo_minimal_default -p 8001:8001 -e NATS_URL=nats://nats:4222 neo_gateway"
        exit 1
    fi

    echo -e "\n${GREEN}🎯 Gateway available - ready for trading signals!${NC}"

    # Get initial metrics
    get_metrics

    echo -e "\n${YELLOW}💹 Sending Real-World Trading Signals...${NC}"

    # Signal 1: Bitcoin Long Signal
    local signal1=$(cat <<EOF
{
  "time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "ticker": "BTCUSD",
  "strategy": {
    "market_position": "long",
    "market_position_size": "0.5",
    "strategy_name": "Momentum Breakout"
  },
  "order": {
    "action": "buy",
    "contracts": 0.25,
    "price": 65000,
    "stop_loss": 62000,
    "take_profit": 70000
  },
  "analysis": {
    "rsi": 68.5,
    "macd_signal": "bullish_cross",
    "confidence": 0.82
  }
}
EOF
)

    send_signal "Signal 1/3: Bitcoin Long - Strong Bullish Momentum" "$signal1" "test"
    sleep 2

    # Signal 2: Ethereum Short Signal
    local signal2=$(cat <<EOF
{
  "time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "ticker": "ETHUSDT",
  "strategy": {
    "market_position": "short",
    "market_position_size": "0.3",
    "strategy_name": "Resistance Trade"
  },
  "order": {
    "action": "sell",
    "contracts": 1.5,
    "price": 3200,
    "stop_loss": 3300,
    "take_profit": 3000
  },
  "analysis": {
    "rsi": 78.2,
    "resistance_level": 3250,
    "confidence": 0.75
  }
}
EOF
)

    send_signal "Signal 2/3: Ethereum Short - Resistance Rejection" "$signal2" "test"
    sleep 2

    # Signal 3: BNB Long Signal
    local signal3=$(cat <<EOF
{
  "time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "ticker": "BNBUSD",
  "strategy": {
    "market_position": "long",
    "market_position_size": "0.2",
    "strategy_name": "Support Bounce"
  },
  "order": {
    "action": "buy",
    "contracts": 10,
    "price": 520,
    "stop_loss": 500,
    "take_profit": 550
  },
  "analysis": {
    "support_level": 515,
    "bounce_strength": "strong",
    "confidence": 0.68
  }
}
EOF
)

    send_signal "Signal 3/3: BNB Long - Support Bounce" "$signal3" "test"

    # Get final metrics
    get_metrics

    echo -e "\n${GREEN}🎉 Demo Complete! Real-world trading signals processed by NEO Gateway${NC}"

    echo -e "\n${BLUE}📊 Next Steps:${NC}"
    echo "   • Open Grafana dashboards: $GRAFANA_URL"
    echo "   • Check Prometheus metrics: $PROMETHEUS_URL"
    echo "   • View live performance data in monitoring interface"
    echo "   • All webhook data is flowing through NATS for agent processing"

    echo -e "\n${YELLOW}🔗 Quick Access Links:${NC}"
    echo "   Gateway Health: $GATEWAY_URL/healthz"
    echo "   Gateway Metrics: $GATEWAY_URL/metrics"
    echo "   Prometheus Targets: $PROMETHEUS_URL/targets"
    echo "   Grafana Login: admin / admin123"
}

# Run the demo
main "$@"
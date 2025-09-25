# NEO v1.0.0 Dashboard Testing Playbook

Practical testing scenarios and commands for validating dashboard functionality during development and testing phases.

## 🎯 Quick Start Testing

### **Prerequisites**
```bash
# Ensure monitoring stack is running
docker-compose -f docker-compose.production.yml ps | grep -E "(prometheus|grafana)"

# Verify dashboards are imported
curl -s -u admin:admin123 "http://localhost:3000/api/search?type=dash-db" | jq -r '.[] | .title'
```

### **Access Dashboard URLs**
```bash
# Set base URL
GRAFANA_URL="http://localhost:3000"

# Dashboard direct links
echo "📊 Gateway Performance: $GRAFANA_URL/d/gateway-001/gateway-performance"
echo "🤖 Agent Orchestrator: $GRAFANA_URL/d/neo-agent-orchestrator-v1/neo-agent-orchestrator-v1-0-0"
echo "📲 Output Manager: $GRAFANA_URL/d/neo-output-manager-v1/neo-output-manager-v1-0-0"
echo "🔄 Trading Flow: $GRAFANA_URL/d/neo-trading-flow-v1/neo-v1-0-0-real-time-trading-flow"
```

---

## 🚪 Gateway Performance Dashboard Testing

### **Test Scenario 1: Basic Webhook Processing**
```bash
# Start gateway service
docker-compose -f docker-compose.minimal.yml up -d gateway

# Wait for service to be ready
sleep 30

# Test basic webhook
curl -X POST http://localhost:8001/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"test": "data", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}'

# Expected Dashboard Changes:
# - Request rate increases
# - Processing latency updates
# - Success/error counters increment
```

### **Test Scenario 2: Schema Validation**
```bash
# Test valid TradingView webhook
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Signature: test-signature" \
  -d '{
    "time": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "ticker": "BTCUSD",
    "strategy": {"market_position": "long"},
    "order": {"action": "buy", "price": 45000}
  }'

# Test invalid webhook (should trigger validation error)
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{"invalid": "structure"}'

# Expected Dashboard Changes:
# - Validation error counter increases
# - Error rate percentage updates
# - Error breakdown by type
```

### **Test Scenario 3: Load Testing**
```bash
# Install artillery for load testing
npm install -g artillery

# Create load test configuration
cat > artillery-gateway.yml << EOF
config:
  target: 'http://localhost:8001'
  phases:
    - duration: 60
      arrivalRate: 5
scenarios:
  - name: "Webhook Load Test"
    requests:
      - post:
          url: "/webhook/test"
          headers:
            Content-Type: "application/json"
          json:
            timestamp: "{{ \$timestamp }}"
            ticker: "BTCUSD"
            price: "{{ \$randomNumber(40000, 50000) }}"
EOF

# Run load test
artillery run artillery-gateway.yml

# Expected Dashboard Changes:
# - Request rate spikes to ~5 RPS
# - Latency metrics update under load
# - Error rates remain low (<1%)
# - NATS publish rates increase
```

---

## 🤖 Agent Orchestrator Dashboard Testing

### **Test Scenario 1: Agent Request Processing**
```bash
# Start agent orchestrator
docker-compose -f docker-compose.minimal.yml up -d agent-orchestrator redis

# Test agent processing endpoint
curl -X POST http://localhost:8010/process \
  -H "Content-Type: application/json" \
  -d '{
    "signal_type": "trend_analysis",
    "agent_type": "gpt_trend_analyzer",
    "data": {
      "ticker": "BTCUSD",
      "action": "buy",
      "confidence": 0.85
    },
    "correlation_id": "test-'$(date +%s)'"
  }'

# Expected Dashboard Changes:
# - Agent request counter increases
# - Active agents gauge updates
# - Processing duration histogram updates
# - Success rate percentage calculated
```

### **Test Scenario 2: Multiple Agent Types**
```bash
# Test different agent types
AGENT_TYPES=("gpt_trend_analyzer" "claude_strategy" "momentum_scanner")

for agent in "${AGENT_TYPES[@]}"; do
  echo "Testing agent: $agent"
  curl -X POST http://localhost:8010/process \
    -H "Content-Type: application/json" \
    -d '{
      "agent_type": "'$agent'",
      "signal_type": "market_analysis",
      "data": {"ticker": "ETHUSDT", "action": "sell"}
    }'
  sleep 2
done

# Expected Dashboard Changes:
# - Agent type breakdown in pie chart
# - Per-agent success rates in table
# - Agent-specific latency metrics
```

### **Test Scenario 3: Context Store Testing**
```bash
# Test context creation and retrieval
curl -X POST http://localhost:8010/context \
  -H "Content-Type: application/json" \
  -d '{
    "context_id": "test-context-123",
    "data": {"strategy": "momentum", "risk_level": 0.02},
    "ttl": 3600
  }'

# Test context retrieval
curl http://localhost:8010/context/test-context-123

# Expected Dashboard Changes:
# - Active contexts count increases
# - Context creation rate updates
# - Redis memory usage increases
# - Cache hit/miss ratios update
```

---

## 📲 Output Manager Dashboard Testing

### **Test Scenario 1: Multi-Channel Notification**
```bash
# Start output manager
docker-compose -f docker-compose.minimal.yml up -d output-manager

# Test Slack notification (mock)
curl -X POST http://localhost:8008/notify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "slack",
    "agent_output": {
      "agent_id": "gpt_trend_123",
      "agent_type": "gpt_trend_analyzer",
      "analysis": "Strong bullish momentum detected",
      "confidence": 0.89,
      "orders": [
        {
          "action": "buy",
          "symbol": "BTCUSD",
          "quantity": 0.1,
          "price": 45000
        }
      ]
    }
  }'

# Expected Dashboard Changes:
# - Notification delivery counter increases
# - Channel-specific success rates update
# - Delivery latency metrics recorded
```

### **Test Scenario 2: Paper Trading Execution**
```bash
# Test paper trading execution
curl -X POST http://localhost:8008/trade \
  -H "Content-Type: application/json" \
  -d '{
    "order": {
      "symbol": "BTCUSD",
      "side": "buy",
      "type": "market",
      "quantity": 0.05
    },
    "agent_output": {
      "agent_id": "test_agent",
      "confidence": 0.85
    }
  }'

# Check trading status
curl http://localhost:8008/trading/status

# Expected Dashboard Changes:
# - Paper trading balance updates
# - Portfolio value changes
# - Trade execution counter increases
# - P&L calculations update
```

### **Test Scenario 3: Channel Error Handling**
```bash
# Test with invalid Slack webhook (should fail gracefully)
curl -X POST http://localhost:8008/notify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "slack",
    "webhook_url": "https://invalid.webhook.url",
    "agent_output": {"agent_id": "test", "analysis": "test"}
  }'

# Expected Dashboard Changes:
# - Error counter for Slack channel increases
# - Retry attempts counter updates
# - Overall success rate percentage decreases
# - Error rate by channel updates
```

---

## 🔄 Real-Time Trading Flow Dashboard Testing

### **Test Scenario 1: End-to-End Pipeline**
```bash
# Start complete minimal stack
docker-compose -f docker-compose.minimal.yml up -d

# Wait for all services
sleep 60

# Send end-to-end test
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Signature: test-signature" \
  -d '{
    "time": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "ticker": "BTCUSD",
    "strategy": {"market_position": "long"},
    "order": {"action": "buy", "price": 45000}
  }'

# Expected Dashboard Changes:
# - All flow lines update (webhook → agent → output)
# - End-to-end latency gauge updates
# - Service status table shows healthy services
# - NATS message flow visualization updates
```

### **Test Scenario 2: Pipeline Performance Testing**
```bash
# Test pipeline under load
for i in {1..20}; do
  curl -X POST http://localhost:8001/webhook/tradingview \
    -H "Content-Type: application/json" \
    -H "X-Signature: test-signature" \
    -d '{
      "time": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
      "ticker": "SYMBOL'$i'",
      "order": {"action": "buy", "price": '$((40000 + RANDOM % 10000))'}
    }' &

  if (( i % 5 == 0 )); then
    wait  # Wait for batch to complete
  fi
done

# Expected Dashboard Changes:
# - Request rates spike across all services
# - Latency gauges show real-time performance
# - Message queue depths increase temporarily
# - Error rates remain low under load
```

### **Test Scenario 3: Service Failure Simulation**
```bash
# Stop one service to test error handling
docker-compose -f docker-compose.minimal.yml stop output-manager

# Send requests (should show partial pipeline failure)
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Signature: test-signature" \
  -d '{"time": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'", "ticker": "TEST"}'

# Restart service
docker-compose -f docker-compose.minimal.yml start output-manager

# Expected Dashboard Changes:
# - Service status table shows output-manager as down
# - Error rates increase temporarily
# - Pipeline flow shows incomplete processing
# - Recovery shows service returning to healthy state
```

---

## 📊 Dashboard Validation Checklist

### **Visual Elements Working**
- [ ] Time series charts display data
- [ ] Gauges show current values
- [ ] Pie charts render correctly
- [ ] Tables populate with metrics
- [ ] Color coding works (green/yellow/red)

### **Data Accuracy**
- [ ] Metrics match Prometheus queries
- [ ] Time ranges update correctly
- [ ] Refresh rates work as expected
- [ ] Historical data persists
- [ ] Real-time updates visible

### **Interactive Features**
- [ ] Dashboard variables work
- [ ] Time range picker functions
- [ ] Zoom and pan work on charts
- [ ] Tooltip information accurate
- [ ] Legend toggling works

### **Performance**
- [ ] Dashboard loads within 5 seconds
- [ ] No browser console errors
- [ ] Memory usage remains stable
- [ ] Refresh doesn't cause lag
- [ ] Works on mobile devices

---

## 🔧 Troubleshooting Common Issues

### **Dashboard Shows "No Data"**
```bash
# Check Prometheus targets
curl -s "http://localhost:9090/api/v1/targets" | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Check if services expose metrics
curl http://localhost:8001/metrics | head -10  # Gateway
curl http://localhost:8008/metrics | head -10  # Output Manager
curl http://localhost:8010/metrics | head -10  # Agent Orchestrator

# Verify time range in dashboard (may need recent data)
```

### **Metrics Not Updating**
```bash
# Check Prometheus scrape interval
curl -s "http://localhost:9090/api/v1/query?query=up" | jq '.data.result[]'

# Verify dashboard refresh rate
# Check if auto-refresh is enabled in Grafana

# Test manual metric generation
curl -X POST http://localhost:8001/webhook/test -d '{"test": "data"}'
```

### **Dashboard Import Errors**
```bash
# Re-import dashboards
./import_dashboards.sh

# Check Grafana logs
docker-compose -f docker-compose.production.yml logs grafana | tail -20

# Verify dashboard JSON syntax
jq . repos/at-observability/grafana_dashboards/agent_orchestrator.json
```

---

## 🎯 Testing by Development Phase

### **Unit Testing (Individual Services)**
1. Start single service
2. Use service-specific dashboard
3. Test isolated functionality
4. Validate metrics accuracy

### **Integration Testing (Service Pairs)**
1. Start dependent services
2. Use Real-Time Trading Flow dashboard
3. Test service communication
4. Monitor end-to-end latency

### **System Testing (Full Stack)**
1. Start complete stack
2. Use all dashboards
3. Test realistic scenarios
4. Validate SLA compliance

### **Load Testing (Performance)**
1. Generate high volume requests
2. Monitor all dashboards simultaneously
3. Identify bottlenecks
4. Validate scaling behavior

---

## 📈 Metrics to Monitor During Testing

### **Performance Metrics**
- Request rates (RPS)
- Response times (P50, P95, P99)
- Error rates (%)
- Resource utilization (CPU, Memory)

### **Business Metrics**
- Trading signals processed
- Agent decisions generated
- Notifications delivered
- Paper trades executed

### **Reliability Metrics**
- Service uptime
- Success rates
- Error recovery times
- Message delivery guarantees

---

## 🎉 Testing Success Criteria

### **Dashboard Functionality**
- ✅ All 4 dashboards load and display data
- ✅ Real-time updates work with <10 second latency
- ✅ Historical data is preserved
- ✅ Responsive design works on mobile

### **Metrics Accuracy**
- ✅ Counters increment correctly
- ✅ Gauges reflect current state
- ✅ Histograms show distribution
- ✅ Time series show trends

### **System Performance**
- ✅ <500ms gateway processing (P95)
- ✅ <5s agent processing (P95)
- ✅ <2s notification delivery (P95)
- ✅ <900ms end-to-end latency (P95)

**Use this playbook to systematically test and validate your NEO dashboard implementation!** 📊🧪
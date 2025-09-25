# NEO v1.0.0 Real-World Testing Guide

Comprehensive guide to test the complete NEO system with monitoring, GUI, and real-world data.

## 🎯 Testing Overview

This guide walks through testing the complete NEO v1.0.0 stack:
- Core trading services (Gateway, Agent Orchestrator, Output Manager)
- Monitoring stack (Prometheus, Grafana, exporters)
- GUI interfaces (Control Center, dashboards)
- Real-world webhook data and AI processing

## 🚀 Phase 1: Start the Complete Stack

### Step 1: Launch Production Environment
```bash
# Start the complete NEO v1.0.0 production stack
docker compose -f docker-compose.production.yml up -d

# Monitor startup progress
docker compose -f docker-compose.production.yml logs -f

# Wait for all services to be healthy (2-3 minutes)
watch 'docker compose -f docker-compose.production.yml ps'
```

### Step 2: Verify Service Health
```bash
# Check all services are running
docker compose -f docker-compose.production.yml ps

# Test health endpoints
curl -s http://localhost:8001/healthz | jq  # Gateway
curl -s http://localhost:8008/healthz | jq  # Output Manager
curl -s http://localhost:8010/healthz | jq  # Agent Orchestrator
curl -s http://localhost:3000/api/health    # Grafana
curl -s http://localhost:3001/api/health    # Control Center
curl -s http://localhost:9090/-/healthy     # Prometheus
```

## 📊 Phase 2: Test Monitoring Interfaces

### Step 1: Access Grafana Dashboards
```bash
# Open Grafana (admin/admin123)
open http://localhost:3000

# Navigate to dashboards:
# 1. NEO System Overview
# 2. NEO Agent Orchestrator v1.0.0
# 3. NEO Output Manager v1.0.0
# 4. NEO v1.0.0 - Real-Time Trading Flow
# 5. Gateway Performance
```

**Visual Verification:**
- [ ] All dashboards load without errors
- [ ] Service health indicators show green
- [ ] Metrics are populated with data
- [ ] Time series graphs show activity
- [ ] No "No Data" panels

### Step 2: Access NEO Control Center
```bash
# Open the modern web interface
open http://localhost:3001
```

**Visual Verification:**
- [ ] Modern dashboard loads successfully
- [ ] System overview cards show live data
- [ ] Service status indicators are green
- [ ] Real-time metrics are updating
- [ ] Trading balance shows $10,000 initial
- [ ] Feature flags section displays correctly

### Step 3: Verify Prometheus Metrics
```bash
# Open Prometheus interface
open http://localhost:9090

# Test key metrics queries:
# - up{job="gateway"}
# - rate(gateway_webhooks_processed_total[1m])
# - orchestrator_active_agents
# - paper_trading_balance
```

## 🔄 Phase 3: Test Real-World Data Flow

### Step 1: Send Test Webhook (TradingView Format)
```bash
# Send a realistic TradingView webhook
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Signature: test-signature" \
  -d '{
    "time": "2025-09-24T15:30:00Z",
    "exchange": "BINANCE",
    "ticker": "BTCUSDT",
    "strategy": {
      "market_position": "long",
      "market_position_size": "0.1",
      "prev_market_position": "flat"
    },
    "order": {
      "action": "buy",
      "contracts": "0.1",
      "price": "45000.00"
    }
  }'
```

**Visual Verification in Control Center:**
- [ ] Request rate increases in system overview
- [ ] Gateway metrics show new webhook
- [ ] Real-time alerts show processing activity
- [ ] Trading flow visualization updates

### Step 2: Monitor Agent Processing
Watch in the Control Center and Grafana:

**Agent Orchestrator Dashboard:**
- [ ] Agent request rate increases
- [ ] Processing latency metrics update
- [ ] Active agents counter increments
- [ ] Success rate remains high

**Control Center:**
- [ ] Agent analytics section updates
- [ ] AI processing indicators activate
- [ ] Context store usage increases

### Step 3: Verify Output Delivery
**Output Manager Dashboard:**
- [ ] Notification delivery rate increases
- [ ] Paper trading execution occurs
- [ ] Success rates remain high
- [ ] Channel performance updates

**Control Center Trading Section:**
- [ ] Paper trading balance changes
- [ ] Portfolio value updates
- [ ] Trade execution appears in history
- [ ] P&L calculations update

## 📱 Phase 4: Test GUI Responsiveness

### Step 1: Real-Time Updates
```bash
# Send multiple webhooks to generate activity
for i in {1..10}; do
  curl -X POST http://localhost:8001/webhook/tradingview \
    -H "Content-Type: application/json" \
    -H "X-Signature: test-signature" \
    -d '{"time":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","exchange":"BINANCE","ticker":"BTCUSDT","order":{"action":"buy","contracts":"0.1","price":"'$((45000 + RANDOM % 1000))'"}}'
  sleep 2
done
```

**Visual Verification:**
- [ ] Real-time metrics update every 5-10 seconds
- [ ] Charts and graphs show live data
- [ ] WebSocket connection maintains activity
- [ ] No lag or freezing in interface
- [ ] Mobile/responsive design works

### Step 2: Service Management Features
In the Control Center:
- [ ] Service status section shows all services
- [ ] Health indicators update in real-time
- [ ] Log viewing functionality works
- [ ] Configuration management accessible
- [ ] Restart controls function properly

## 🚨 Phase 5: Test Error Handling & Alerts

### Step 1: Simulate Service Issues
```bash
# Stop a service to trigger alerts
docker compose -f docker-compose.production.yml stop output-manager

# Wait 1-2 minutes and check:
```

**Visual Verification:**
- [ ] System health changes to "warning" or "critical"
- [ ] Service status indicators turn red
- [ ] Alert notifications appear
- [ ] Error rates increase in dashboards
- [ ] Grafana alerts trigger (if configured)

### Step 2: Recovery Testing
```bash
# Restart the service
docker compose -f docker-compose.production.yml start output-manager

# Wait for health recovery
```

**Visual Verification:**
- [ ] System health returns to "healthy"
- [ ] Service indicators turn green
- [ ] Error rates decrease
- [ ] Normal operation resumes

## 📈 Phase 6: Load Testing & Performance

### Step 1: High-Volume Webhook Testing
```bash
# Install load testing tool
npm install -g artillery

# Create load test config
cat > artillery-test.yml << EOF
config:
  target: 'http://localhost:8001'
  phases:
    - duration: 60
      arrivalRate: 10
scenarios:
  - name: "Webhook Load Test"
    requests:
      - post:
          url: "/webhook/tradingview"
          headers:
            Content-Type: "application/json"
            X-Signature: "test-signature"
          json:
            time: "{{ \$timestamp }}"
            exchange: "BINANCE"
            ticker: "BTCUSDT"
            order:
              action: "buy"
              contracts: "0.1"
              price: "45000"
EOF

# Run load test
artillery run artillery-test.yml
```

**Visual Verification During Load:**
- [ ] Request rates scale appropriately
- [ ] Latency metrics remain acceptable (<900ms)
- [ ] Success rates stay above 99%
- [ ] No memory/CPU resource exhaustion
- [ ] All dashboards remain responsive

### Step 2: Resource Monitoring
**In Grafana Infrastructure Dashboard:**
- [ ] CPU usage across containers
- [ ] Memory utilization tracking
- [ ] Disk I/O monitoring
- [ ] Network traffic visualization
- [ ] Redis memory usage

## 🎛️ Phase 7: Advanced Features Testing

### Step 1: Feature Flag Management
```bash
# Test feature flag toggling
curl -X POST http://localhost:8001/admin/feature-flags \
  -H "Content-Type: application/json" \
  -d '{"FF_OUTPUT_SLACK": false}'
```

**Visual Verification:**
- [ ] Feature flag status updates in Control Center
- [ ] Service behavior changes accordingly
- [ ] Metrics reflect feature flag state
- [ ] No system instability from changes

### Step 2: Multi-Channel Output Testing
```bash
# Configure Slack webhook (optional)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"

# Configure Telegram bot (optional)
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# Restart with real credentials
docker compose -f docker-compose.production.yml restart output-manager
```

**Visual Verification with Real Integrations:**
- [ ] Slack notifications delivered
- [ ] Telegram messages sent
- [ ] Paper trades executed
- [ ] Multi-channel metrics update

## ✅ Success Criteria Checklist

### System Health
- [ ] All 15+ services running and healthy
- [ ] System uptime >99.9% during testing
- [ ] No critical errors in logs
- [ ] Resource usage within acceptable limits

### Performance Metrics
- [ ] Webhook processing <500ms P95
- [ ] Agent processing <5s P95
- [ ] Notification delivery <2s P95
- [ ] End-to-end latency <900ms P95

### GUI Functionality
- [ ] All dashboards load and display data
- [ ] Real-time updates working smoothly
- [ ] Mobile responsiveness verified
- [ ] Service management features functional

### Monitoring Coverage
- [ ] 100+ metrics being collected
- [ ] All services instrumented
- [ ] Alert rules configured and tested
- [ ] Historical data retention working

### Trading Pipeline
- [ ] Webhooks processed successfully
- [ ] AI agents analyze and respond
- [ ] Notifications delivered reliably
- [ ] Paper trades executed accurately

## 🎉 Final Validation

If all checkboxes above are complete, your NEO v1.0.0 system is:

✅ **PRODUCTION-READY** with enterprise monitoring
✅ **GUI-ENABLED** with modern interfaces
✅ **PERFORMANCE-VALIDATED** under real-world conditions
✅ **OPERATIONALLY-SOUND** with comprehensive observability

## 📞 Troubleshooting Quick Reference

**Services won't start:**
```bash
docker compose -f docker-compose.production.yml logs [service-name]
```

**Dashboards show no data:**
```bash
curl http://localhost:9090/api/v1/targets  # Check Prometheus targets
```

**Control Center won't connect:**
```bash
curl http://localhost:8001/healthz  # Test API connectivity
docker compose -f docker-compose.production.yml logs control-center
```

**Missing metrics:**
```bash
curl http://localhost:8001/metrics  # Check service metrics endpoint
```

## 🚀 Ready for Production!

Your NEO v1.0.0 Real-Time Trading Intelligence System is now fully tested and ready for production deployment with comprehensive monitoring and beautiful GUI interfaces!
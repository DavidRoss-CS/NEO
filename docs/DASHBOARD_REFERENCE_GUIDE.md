# NEO v1.0.0 Dashboard Reference Guide

Complete documentation of all monitoring dashboards, their purpose, metrics, and usage scenarios for building and testing NEO system components.

## 📊 Dashboard Overview

The NEO v1.0.0 monitoring system includes **4 specialized dashboards** designed to monitor different aspects of the real-time trading intelligence pipeline:

1. **Gateway Performance** - Webhook ingestion and signal processing
2. **Agent Orchestrator v1.0.0** - AI agent performance and orchestration
3. **Output Manager v1.0.0** - Multi-channel delivery and paper trading
4. **Real-Time Trading Flow** - End-to-end pipeline visualization

---

## 🚪 1. Gateway Performance Dashboard

### **Access Information**
- **URL**: http://localhost:3000/d/gateway-001/gateway-performance
- **Purpose**: Monitor webhook ingestion, signal validation, and NATS routing
- **Service**: `at-gateway` (Port 8001)

### **Key Metrics Displayed**

#### **Request Processing**
- `gateway_webhooks_processed_total` - Total webhooks received
- `rate(gateway_webhooks_processed_total[1m])` - Webhooks per second
- `gateway_webhook_processing_duration_seconds` - Processing latency (P95)

#### **Validation & Routing**
- `gateway_validation_errors_total` - Schema validation failures
- `gateway_hmac_verification_total` - HMAC signature validation
- `gateway_signal_categorization_total` - Signal type classification

#### **NATS Integration**
- `gateway_nats_publish_total` - Messages published to NATS
- `gateway_nats_publish_duration_seconds` - NATS publish latency

#### **Error Tracking**
- `gateway_errors_total{error_type}` - Categorized error rates
- `gateway_circuit_breaker_state` - Circuit breaker status

### **When to Use This Dashboard**

#### **During Development**
- **Webhook Integration**: Verify TradingView/external webhooks are received correctly
- **Schema Validation**: Test new signal formats and validation rules
- **Performance Testing**: Ensure <500ms P95 processing latency
- **Security Testing**: Validate HMAC signature verification

#### **During Testing**
```bash
# Test webhook processing
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Signature: test-signature" \
  -d '{"time":"2025-09-24T10:30:00Z","ticker":"BTCUSD","action":"buy"}'

# Watch metrics update in dashboard
```

#### **Production Monitoring**
- **Traffic Patterns**: Monitor webhook volume and peak times
- **Error Rates**: Alert on >1% error rates for 5+ minutes
- **Performance SLA**: Ensure P95 latency stays <500ms

### **Alert Thresholds**
- 🔴 **Critical**: Gateway down >1 minute
- 🟡 **Warning**: Error rate >1% for 5 minutes
- 🟡 **Warning**: P95 latency >500ms for 5 minutes

---

## 🤖 2. Agent Orchestrator v1.0.0 Dashboard

### **Access Information**
- **URL**: http://localhost:3000/d/neo-agent-orchestrator-v1/neo-agent-orchestrator-v1-0-0
- **Purpose**: Monitor AI agent performance, MCP integration, and context management
- **Service**: `at-agent-orchestrator` (Port 8010)

### **Key Metrics Displayed**

#### **Agent Performance**
- `orchestrator_agent_requests_total{agent_type}` - Requests per agent type
- `orchestrator_agent_processing_duration_seconds` - Agent response latency
- `orchestrator_active_agents{agent_type}` - Currently active agents
- `orchestrator_agent_responses_total{status}` - Success/failure rates

#### **MCP Integration**
- `orchestrator_mcp_calls_total{agent_type}` - Model Context Protocol calls
- `orchestrator_mcp_call_duration_seconds` - MCP call latency
- `orchestrator_mcp_errors_total{error_type}` - MCP integration errors

#### **Context Management**
- `orchestrator_active_contexts` - Active trading contexts
- `orchestrator_context_created_total` - New contexts per minute
- `orchestrator_context_expired_total` - Expired contexts
- `orchestrator_context_misses_total` - Cache misses

#### **Resource Utilization**
- `redis_memory_used_bytes` - Context store memory usage
- `orchestrator_concurrent_agents` - Concurrent agent processing
- `orchestrator_queue_depth` - Pending agent requests

### **Dashboard Panels**

#### **Agent Request Rate** (Time Series)
Shows real-time agent activity by type:
- GPT Trend Analyzer requests/sec
- Claude Strategy requests/sec
- MCP calls/sec per agent

#### **Processing Latency Gauge** (P95)
Target: <5 seconds for agent processing

#### **Active Agents Pie Chart**
Distribution of active agents by type

#### **Agent Performance Summary Table**
- Agent Type | Requests/sec | Success Rate | Avg Latency
- Real-time performance metrics per agent

### **When to Use This Dashboard**

#### **During Agent Development**
- **New Agent Integration**: Verify new AI agents are registered and responding
- **Performance Optimization**: Monitor processing times for different agent types
- **MCP Testing**: Validate Model Context Protocol integration
- **Context Store Testing**: Monitor Redis usage and context lifecycle

#### **Testing Scenarios**
```bash
# Test agent processing with different signal types
curl -X POST http://localhost:8010/process \
  -H "Content-Type: application/json" \
  -d '{
    "signal_type": "trend_analysis",
    "agent_type": "gpt_trend_analyzer",
    "data": {"ticker": "BTCUSD", "action": "buy"}
  }'

# Monitor dashboard for:
# - Agent activation
# - Processing latency
# - Success rates
# - Context creation
```

#### **Load Testing**
- **Concurrent Agents**: Test multiple agents processing simultaneously
- **Context Scaling**: Monitor Redis memory usage under load
- **Performance Degradation**: Watch for latency increases
- **Error Rates**: Validate graceful degradation

#### **Production Monitoring**
- **Agent Health**: Ensure all configured agents are active
- **Performance SLA**: P95 <5 seconds processing time
- **Context Store**: Monitor Redis memory usage <80%
- **Error Tracking**: Alert on agent failures

### **Alert Thresholds**
- 🔴 **Critical**: Agent orchestrator down >1 minute
- 🔴 **Critical**: Agent success rate <95% for 10 minutes
- 🟡 **Warning**: P95 processing >5 seconds for 10 minutes
- 🟡 **Warning**: Redis memory >80% usage

---

## 📲 3. Output Manager v1.0.0 Dashboard

### **Access Information**
- **URL**: http://localhost:3000/d/neo-output-manager-v1/neo-output-manager-v1-0-0
- **Purpose**: Monitor multi-channel notifications, paper trading, and delivery performance
- **Service**: `at-output-manager` (Port 8008)

### **Key Metrics Displayed**

#### **Notification Delivery**
- `output_notifications_delivered_total{channel}` - Deliveries per channel
- `output_notification_delivery_duration_seconds` - Delivery latency
- `output_delivery_errors_total{channel}` - Channel-specific errors
- `output_retry_attempts_total{channel}` - Retry attempts per channel

#### **Channel Performance**
- **Slack**: `output_slack_deliveries_total`, `output_slack_webhook_errors`
- **Telegram**: `output_telegram_messages_total`, `output_telegram_api_errors`
- **Paper Trading**: `output_trades_executed_total`, `paper_trading_balance`

#### **Paper Trading Metrics**
- `paper_trading_balance` - Current trading balance
- `paper_trading_portfolio_value` - Total portfolio value
- `paper_trading_realized_pnl` - Realized profit/loss
- `paper_trading_trades_total{status}` - Trade execution counts

#### **Delivery Performance**
- `output_processing_duration_seconds` - End-to-end processing time
- `output_message_queue_depth` - Pending notifications
- `output_concurrent_deliveries` - Parallel delivery operations

### **Dashboard Panels**

#### **Output Delivery Rate** (Time Series)
- Slack deliveries/sec
- Telegram deliveries/sec
- Paper trades/sec

#### **Delivery Latency Gauge** (P95)
Target: <2 seconds for notification delivery

#### **Notifications by Channel** (Pie Chart)
Distribution of notifications across channels

#### **Paper Trading Performance** (Time Series)
- Balance over time
- Portfolio value tracking
- Realized P&L

#### **Channel Performance Summary** (Table)
- Channel | Deliveries/sec | Success Rate | Avg Latency

### **When to Use This Dashboard**

#### **During Integration Development**
- **Slack Integration**: Test webhook delivery and message formatting
- **Telegram Bot**: Verify bot API integration and inline keyboards
- **Paper Trading**: Validate trade execution and portfolio tracking
- **Multi-Channel**: Test simultaneous delivery across channels

#### **Testing Scenarios**
```bash
# Test manual notification delivery
curl -X POST http://localhost:8008/notify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "slack",
    "agent_output": {
      "agent_id": "test_agent",
      "analysis": "Test notification",
      "confidence": 0.85,
      "orders": [{"action": "buy", "symbol": "BTCUSD"}]
    }
  }'

# Monitor dashboard for:
# - Delivery success
# - Response times
# - Error rates
# - Retry attempts
```

#### **Feature Flag Testing**
Test different channel combinations:
```bash
# Enable/disable channels via feature flags
FF_OUTPUT_SLACK=true
FF_OUTPUT_TELEGRAM=false
FF_EXEC_PAPER=true
```

#### **Performance Testing**
- **High Volume**: Test notification bursts during market volatility
- **Channel Failures**: Test graceful degradation when channels fail
- **Paper Trading**: Validate portfolio calculations under load
- **Retry Logic**: Test retry mechanisms for failed deliveries

#### **Production Monitoring**
- **Delivery SLA**: P95 <2 seconds delivery time
- **Success Rates**: >98% delivery success per channel
- **Portfolio Tracking**: Monitor paper trading performance
- **Error Alerting**: Channel-specific failure alerts

### **Alert Thresholds**
- 🔴 **Critical**: Output manager down >1 minute
- 🔴 **Critical**: Any channel success rate <95% for 10 minutes
- 🟡 **Warning**: P95 delivery latency >2 seconds for 5 minutes
- 🟡 **Warning**: Paper trading balance deviation >10%

---

## 🔄 4. Real-Time Trading Flow Dashboard

### **Access Information**
- **URL**: http://localhost:3000/d/neo-trading-flow-v1/neo-v1-0-0-real-time-trading-flow
- **Purpose**: End-to-end pipeline monitoring and performance SLA tracking
- **Scope**: Complete NEO system (all services)

### **Key Metrics Displayed**

#### **End-to-End Pipeline**
- `rate(gateway_webhooks_processed_total[1m])` - Webhooks in
- `rate(orchestrator_agent_requests_total[1m])` - Agent processing
- `rate(output_notifications_delivered_total[1m])` - Notifications out
- Combined flow visualization

#### **Latency Breakdown**
- **Gateway P95**: `histogram_quantile(0.95, gateway_webhook_processing_duration_seconds_bucket)`
- **Agent P95**: `histogram_quantile(0.95, orchestrator_agent_processing_duration_seconds_bucket)`
- **Delivery P95**: `histogram_quantile(0.95, output_notification_delivery_duration_seconds_bucket)`
- **End-to-End P95**: Combined latency calculation

#### **NATS Message Flow**
- `nats_jetstream_stream_messages` - Stream message count
- `nats_consumer_pending_messages` - Consumer lag
- `rate(nats_consumer_delivered_total[1m])` - Message throughput

#### **System Health Overview**
- `up{job}` - Service availability
- Error rates across all services
- Success rates for complete pipeline

### **Dashboard Panels**

#### **End-to-End Trading Flow** (Time Series)
Complete pipeline visualization:
- Blue line: Webhooks In
- Purple line: Agent Processing
- Green line: Notifications Out
- Orange line: Trades Executed

#### **Latency Gauges** (4 Gauges)
- Gateway Latency (Target: <500ms)
- Agent Processing (Target: <5s)
- Delivery Latency (Target: <2s)
- **End-to-End Total** (Target: <900ms)

#### **NATS Message Flow** (Time Series)
- Stream messages
- Pending messages per consumer
- Message delivery rates

#### **Service Status Summary** (Table)
Real-time service health with:
- Service | Health | Requests/sec | Success Rate

### **When to Use This Dashboard**

#### **During System Integration**
- **End-to-End Testing**: Verify complete webhook-to-notification flow
- **Performance Validation**: Ensure <900ms P95 end-to-end latency
- **Bottleneck Identification**: Find slowest component in pipeline
- **Message Flow**: Monitor NATS message routing

#### **Integration Testing Scenarios**
```bash
# Full pipeline test
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Signature: valid-signature" \
  -d '{
    "time": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "ticker": "BTCUSD",
    "action": "buy",
    "price": 45000
  }'

# Watch end-to-end flow:
# 1. Webhook received (Gateway)
# 2. Agent processing triggered (Orchestrator)
# 3. Notifications delivered (Output Manager)
# 4. Total latency measured
```

#### **Performance Testing**
- **Load Testing**: Monitor pipeline under high webhook volume
- **Stress Testing**: Identify breaking points for each service
- **SLA Validation**: Ensure 99.9% of requests meet <900ms target
- **Scalability**: Test horizontal scaling requirements

#### **Production Operations**
- **Golden Path Monitoring**: Primary dashboard for operations team
- **Incident Response**: Quickly identify failing components
- **Performance Trends**: Monitor degradation over time
- **Capacity Planning**: Identify scaling needs

#### **Troubleshooting Workflows**
1. **High Latency**: Check individual service gauges to isolate bottleneck
2. **Low Throughput**: Compare input vs output rates to find constraints
3. **Message Backlog**: Monitor NATS consumer lag for processing delays
4. **Service Failures**: Use status table to identify down services

### **Alert Thresholds**
- 🔴 **Critical**: End-to-end latency P95 >900ms for 5 minutes
- 🔴 **Critical**: Any service down >1 minute
- 🔴 **Critical**: Message consumer lag >1000 for 2 minutes
- 🟡 **Warning**: Pipeline success rate <99% for 5 minutes

---

## 🎯 Usage Guidelines by Development Phase

### **Phase 1: Component Development**
Focus on individual service dashboards:
- **Gateway Dashboard**: Webhook integration and validation
- **Agent Dashboard**: AI agent development and testing
- **Output Dashboard**: Channel integration and formatting

### **Phase 2: Integration Testing**
Use **Real-Time Trading Flow Dashboard** for:
- End-to-end pipeline validation
- Performance bottleneck identification
- Message flow verification

### **Phase 3: Load Testing**
Monitor all dashboards simultaneously:
- Individual service performance under load
- End-to-end latency degradation
- Resource utilization scaling

### **Phase 4: Production Operations**
Primary dashboard: **Real-Time Trading Flow**
Secondary dashboards: Service-specific for troubleshooting

---

## 📊 Dashboard Navigation Tips

### **Quick Access Methods**
1. **Bookmarks**: Save direct URLs for frequent dashboards
2. **Search**: Type "NEO" in Grafana search to filter
3. **Folders**: Navigate via Dashboards → Browse

### **Time Range Selection**
- **Development**: Last 15 minutes for quick feedback
- **Testing**: Last 1 hour for test session analysis
- **Operations**: Last 24 hours for trend analysis

### **Refresh Rates**
- **Real-time monitoring**: 5-10 seconds
- **Historical analysis**: 1-5 minutes
- **Report generation**: Manual refresh

---

## 🚨 Alerting Integration

Each dashboard includes metrics suitable for alerting:

### **Prometheus Alert Rules**
```yaml
# Gateway Performance
- alert: GatewayHighLatency
  expr: histogram_quantile(0.95, gateway_webhook_processing_duration_seconds_bucket) > 0.5
  for: 5m

# Agent Performance
- alert: AgentProcessingSlow
  expr: histogram_quantile(0.95, orchestrator_agent_processing_duration_seconds_bucket) > 5
  for: 10m

# Output Delivery
- alert: DeliveryFailureRate
  expr: rate(output_delivery_errors_total[5m]) / rate(output_notifications_delivered_total[5m]) > 0.02
  for: 5m

# End-to-End SLA
- alert: EndToEndLatencyBreach
  expr: (histogram_quantile(0.95, gateway_webhook_processing_duration_seconds_bucket) +
        histogram_quantile(0.95, orchestrator_agent_processing_duration_seconds_bucket) +
        histogram_quantile(0.95, output_notification_delivery_duration_seconds_bucket)) > 0.9
  for: 5m
```

### **Grafana Alerting**
Each dashboard can be configured with Grafana native alerting for:
- Slack notifications
- Email alerts
- PagerDuty integration
- Webhook notifications

---

## 📚 Additional Resources

### **Metric Documentation**
- **Gateway Metrics**: `repos/at-gateway/METRICS.md`
- **Agent Metrics**: `repos/at-agent-orchestrator/METRICS.md`
- **Output Metrics**: `repos/at-output-manager/METRICS.md`

### **Dashboard Customization**
- **JSON Sources**: `repos/at-observability/grafana_dashboards/`
- **Provisioning**: `repos/at-observability/grafana-provisioning/`
- **Import/Export**: Via Grafana UI

### **Testing Tools**
- **Load Testing**: `artillery` for webhook load tests
- **Metrics Testing**: Custom Python scripts for metric generation
- **Integration Testing**: cURL commands for API testing

---

## 🎉 Summary

The NEO v1.0.0 dashboard system provides comprehensive monitoring for:

- ✅ **4 Specialized Dashboards** covering every aspect of the trading pipeline
- ✅ **50+ Metrics** tracking performance, errors, and business KPIs
- ✅ **Real-time Visualization** with <10 second refresh rates
- ✅ **SLA Monitoring** with performance targets and thresholds
- ✅ **Development Support** for component testing and integration
- ✅ **Production Operations** for incident response and capacity planning

**Use this guide as your reference for monitoring, testing, and operating the NEO trading intelligence system!** 📊🚀
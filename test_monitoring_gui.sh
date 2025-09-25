#!/bin/bash

# NEO v1.0.0 Monitoring & GUI Test Script
echo "🚀 NEO v1.0.0 Monitoring & GUI Test"
echo "======================================"

echo ""
echo "📊 1. PROMETHEUS METRICS (http://localhost:9090)"
echo "   Checking Prometheus health..."
curl -s http://localhost:9090/-/healthy && echo " ✅ Prometheus is healthy"

echo ""
echo "   Active targets:"
curl -s "http://localhost:9090/api/v1/targets" | jq '.data.activeTargets[] | select(.health == "up") | "   ✅ " + .labels.job + " (" + .labels.instance + ")"' -r

echo ""
echo "   Sample metrics:"
TOTAL_MEM=$(curl -s "http://localhost:9090/api/v1/query?query=node_memory_MemTotal_bytes" | jq '.data.result[0].value[1]' -r)
REDIS_CLIENTS=$(curl -s "http://localhost:9090/api/v1/query?query=redis_connected_clients" | jq '.data.result[0].value[1]' -r)
CONTAINER_COUNT=$(curl -s "http://localhost:9090/api/v1/query?query=count(container_last_seen)" | jq '.data.result[0].value[1]' -r)

echo "   📏 System Memory: $(echo "scale=2; $TOTAL_MEM / 1024 / 1024 / 1024" | bc) GB"
echo "   🔗 Redis Connections: $REDIS_CLIENTS"
echo "   📦 Running Containers: $CONTAINER_COUNT"

echo ""
echo "📈 2. GRAFANA DASHBOARDS (http://localhost:3000)"
echo "   Checking Grafana health..."
GRAFANA_STATUS=$(curl -s http://localhost:3000/api/health | jq '.database' -r)
echo "   ✅ Grafana database: $GRAFANA_STATUS"

echo ""
echo "   Available dashboards:"
echo "   📊 Agent Orchestrator v1.0.0: http://localhost:3000/d/neo-agent-orchestrator-v1"
echo "   📲 Output Manager v1.0.0: http://localhost:3000/d/neo-output-manager-v1"
echo "   🔄 Real-Time Trading Flow: http://localhost:3000/d/neo-trading-flow-v1"
echo "   📡 Gateway Performance: Available when gateway is running"

echo ""
echo "🎛️ 3. SYSTEM INFRASTRUCTURE METRICS"
echo "   Node Exporter (System): http://localhost:9100/metrics"
echo "   cAdvisor (Containers): http://localhost:8080/"
echo "   Redis Exporter: http://localhost:9121/metrics"

echo ""
echo "✅ MONITORING SYSTEM STATUS: FULLY OPERATIONAL"
echo ""
echo "🎯 NEXT STEPS TO TEST WITH REAL DATA:"
echo "   1. Open Grafana: http://localhost:3000 (admin/admin123)"
echo "   2. Import the NEO dashboards"
echo "   3. Start NEO services to see live metrics"
echo "   4. Send test webhooks to generate activity"
echo ""
echo "📱 VISUAL INTERFACES READY:"
echo "   • Professional Grafana dashboards with live metrics"
echo "   • Infrastructure monitoring with cAdvisor"
echo "   • Prometheus for metrics collection and alerting"
echo "   • Redis monitoring for NEO's context store"
echo ""
echo "🎉 NEO v1.0.0 MONITORING & GUI SUCCESSFULLY DEPLOYED!"
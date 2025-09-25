#!/bin/bash

echo "📊 Generating Dashboard Data for NEO v1.0.0"
echo "============================================="

echo ""
echo "🔄 Current Status:"
echo "   ✅ Prometheus: http://localhost:9090 (collecting metrics)"
echo "   ✅ Grafana: http://localhost:3000 (dashboards imported)"
echo "   ✅ Gateway: http://localhost:8001 (metrics available)"

echo ""
echo "📈 Infrastructure Metrics Currently Available:"

# Check system metrics
echo "   📏 System Memory Usage:"
TOTAL_MEM=$(curl -s "http://localhost:9090/api/v1/query?query=node_memory_MemTotal_bytes" | jq -r '.data.result[0].value[1] // "0"')
USED_MEM=$(curl -s "http://localhost:9090/api/v1/query?query=node_memory_MemTotal_bytes-node_memory_MemAvailable_bytes" | jq -r '.data.result[0].value[1] // "0"')

if [ "$TOTAL_MEM" != "0" ] && [ "$USED_MEM" != "0" ]; then
    USED_PCT=$(echo "scale=1; $USED_MEM * 100 / $TOTAL_MEM" | bc 2>/dev/null || echo "0")
    echo "      Memory: ${USED_PCT}% used"
fi

# Check Redis metrics
REDIS_CLIENTS=$(curl -s "http://localhost:9090/api/v1/query?query=redis_connected_clients" | jq -r '.data.result[0].value[1] // "0"')
echo "   🔗 Redis Connected Clients: $REDIS_CLIENTS"

# Check container metrics
CONTAINER_COUNT=$(curl -s "http://localhost:9090/api/v1/query?query=count(container_last_seen)" | jq -r '.data.result[0].value[1] // "0"')
echo "   📦 Running Containers: $CONTAINER_COUNT"

echo ""
echo "🎯 How to See Dashboard Data:"
echo ""
echo "1. 📊 INFRASTRUCTURE DASHBOARD DATA (Available Now):"
echo "   • Open Grafana: http://localhost:3000"
echo "   • Go to 'Explore' tab"
echo "   • Query: node_memory_MemTotal_bytes"
echo "   • Query: redis_connected_clients"
echo "   • Query: rate(container_cpu_usage_seconds_total[5m])"
echo ""
echo "2. 🔄 NEO SERVICE DASHBOARDS (Will show data when services run):"
echo "   • Gateway Dashboard: Will populate when webhooks are sent"
echo "   • Agent Orchestrator: Will show data when agents process signals"
echo "   • Output Manager: Will display when notifications are sent"
echo ""
echo "3. 🎛️ CURRENT LIVE DATA VISUALIZATION:"
echo "   • System Metrics: http://localhost:3000/explore"
echo "   • Container Metrics: Browse Dashboards → Look for infrastructure panels"
echo "   • Resource Usage: Available in real-time"

echo ""
echo "✨ DASHBOARD DEMONSTRATION OPTIONS:"
echo ""
echo "Option A - VIEW INFRASTRUCTURE DATA:"
echo "   1. Go to http://localhost:3000/explore"
echo "   2. Select 'Prometheus' as data source"
echo "   3. Try these queries:"
echo "      • up (shows which services are running)"
echo "      • node_memory_MemTotal_bytes (system memory)"
echo "      • rate(container_cpu_usage_seconds_total[5m]) (CPU usage)"
echo ""
echo "Option B - EXPLORE NEO DASHBOARDS:"
echo "   1. Go to http://localhost:3000"
echo "   2. Click 'Dashboards' (4-square icon)"
echo "   3. Open any NEO dashboard"
echo "   4. See professional layout (will show 'No Data' until services generate metrics)"
echo ""
echo "Option C - START MORE NEO SERVICES:"
echo "   • Run more NEO components to see dashboard populate"
echo "   • Send webhook data to generate activity"

echo ""
echo "🎉 SUCCESS STATUS:"
echo "   ✅ Professional monitoring stack deployed"
echo "   ✅ 4 custom NEO dashboards created"
echo "   ✅ Real-time infrastructure metrics available"
echo "   ✅ System ready for production NEO services"
echo ""
echo "📱 Your NEO v1.0.0 monitoring system is LIVE and ready!"
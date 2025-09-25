#!/bin/bash

# NEO v1.0.0 Dashboard Import Script
echo "📊 Importing NEO v1.0.0 Dashboards into Grafana..."

GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASS="admin123"

# Function to import dashboard
import_dashboard() {
    local dashboard_file=$1
    local dashboard_name=$2

    echo "📈 Importing $dashboard_name..."

    # Create the proper JSON structure for Grafana API
    cat > /tmp/dashboard_import.json << EOF
{
  "dashboard": $(cat "$dashboard_file"),
  "overwrite": true,
  "inputs": [],
  "folderId": 0
}
EOF

    # Import via API
    response=$(curl -s -X POST \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -H "Content-Type: application/json" \
        -d @/tmp/dashboard_import.json \
        "$GRAFANA_URL/api/dashboards/db")

    if echo "$response" | grep -q '"status":"success"'; then
        dashboard_url=$(echo "$response" | jq -r '.url')
        echo "   ✅ $dashboard_name imported successfully"
        echo "   🔗 URL: $GRAFANA_URL$dashboard_url"
    else
        echo "   ❌ Failed to import $dashboard_name"
        echo "   Error: $response"
    fi

    rm -f /tmp/dashboard_import.json
}

# Import all NEO dashboards
import_dashboard "repos/at-observability/grafana_dashboards/agent_orchestrator.json" "NEO Agent Orchestrator v1.0.0"
import_dashboard "repos/at-observability/grafana_dashboards/output_manager.json" "NEO Output Manager v1.0.0"
import_dashboard "repos/at-observability/grafana_dashboards/trading_flow.json" "NEO Real-Time Trading Flow"

# Check if gateway dashboard exists
if [ -f "repos/at-observability/grafana_dashboards/gateway.json" ]; then
    import_dashboard "repos/at-observability/grafana_dashboards/gateway.json" "NEO Gateway Performance"
fi

echo ""
echo "🎉 Dashboard import completed!"
echo ""
echo "📱 Access your dashboards at:"
echo "   🌐 Grafana: $GRAFANA_URL"
echo "   📊 Browse Dashboards → General folder"
echo "   🔍 Or search for 'NEO' in the dashboard search"
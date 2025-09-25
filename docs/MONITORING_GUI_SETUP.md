# NEO v1.0.0 Monitoring & GUI Setup Guide

Complete guide for setting up the NEO Trading Intelligence System's monitoring, visualization, and graphical user interfaces.

## 🎯 Overview

NEO v1.0.0 includes a comprehensive monitoring and GUI stack:

- **Grafana Dashboards** - Professional metrics visualization
- **Prometheus Monitoring** - Time-series metrics collection
- **NEO Control Center** - Modern web-based control panel
- **Real-time Analytics** - WebSocket-powered live updates
- **Service Management** - Administrative interfaces

## 📊 Monitoring Stack Components

### 1. Prometheus (Metrics Collection)
- **Port**: `9090`
- **Purpose**: Scrapes metrics from all NEO services
- **Retention**: 30 days of historical data
- **Config**: `repos/at-observability/prometheus.yml`

### 2. Grafana (Visualization)
- **Port**: `3000`
- **Purpose**: Rich dashboards and alerting
- **Login**: `admin` / `admin123` (configurable)
- **Dashboards**: Auto-provisioned from `repos/at-observability/grafana_dashboards/`

### 3. NEO Control Center (Web GUI)
- **Port**: `3001`
- **Purpose**: Real-time system control and monitoring
- **Tech**: Next.js 14 + React + TypeScript + Tailwind CSS
- **Features**: Live metrics, service control, trading interface

## 🚀 Quick Start

### Option 1: Full Production Stack
```bash
# Start everything including monitoring
docker compose -f docker-compose.production.yml up -d

# Wait for services to initialize (2-3 minutes)
docker compose ps

# Access interfaces
open http://localhost:3000  # Grafana
open http://localhost:3001  # NEO Control Center
open http://localhost:9090  # Prometheus
```

### Option 2: Minimal Stack + Monitoring
```bash
# Start core services with monitoring
docker compose -f docker-compose.minimal.yml up -d
docker compose -f docker-compose.production.yml up -d prometheus grafana control-center

# Access interfaces
open http://localhost:3000  # Grafana
open http://localhost:3001  # NEO Control Center
```

### Option 3: Development Mode
```bash
# Start just monitoring for development
docker compose -f docker-compose.production.yml up -d prometheus grafana node-exporter redis-exporter

# Run Control Center in development mode
cd repos/at-control-center
npm install
npm run dev

open http://localhost:3001  # NEO Control Center (dev)
open http://localhost:3000  # Grafana
```

## 📈 Available Dashboards

### 1. NEO System Overview
- **File**: `neo-system-overview.json`
- **URL**: http://localhost:3000/d/neo-overview
- **Content**: High-level system health, KPIs, service status

### 2. Agent Orchestrator v1.0.0
- **File**: `agent_orchestrator.json`
- **URL**: http://localhost:3000/d/neo-agent-orchestrator-v1
- **Content**: AI agent performance, MCP calls, context management

### 3. Output Manager v1.0.0
- **File**: `output_manager.json`
- **URL**: http://localhost:3000/d/neo-output-manager-v1
- **Content**: Notification delivery, paper trading, channel performance

### 4. Real-Time Trading Flow
- **File**: `trading_flow.json`
- **URL**: http://localhost:3000/d/neo-trading-flow-v1
- **Content**: End-to-end pipeline visualization, latency tracking

### 5. Gateway Performance
- **File**: `gateway.json`
- **URL**: http://localhost:3000/d/neo-gateway
- **Content**: Webhook processing, validation, routing metrics

### 6. Infrastructure Metrics
- **URL**: http://localhost:3000/d/infrastructure
- **Content**: Docker containers, Redis, NATS, system resources

## 🎛️ NEO Control Center Features

### Real-Time Dashboard
- Live system health indicators
- Performance metrics and KPIs
- Service status monitoring
- Alert notifications

### Trading Command Center
- Paper trading portfolio overview
- Live P&L tracking
- Trade execution monitoring
- Risk metrics display

### Service Management
- Start/stop/restart services
- Configuration management
- Log viewing and search
- Health check monitoring

### Agent Analytics
- AI agent performance tracking
- Decision confidence scoring
- Context utilization metrics
- Error rate monitoring

## 🔧 Configuration

### Environment Variables
```bash
# NEO Control Center
NEXT_PUBLIC_API_BASE_URL=http://gateway:8001
NEXT_PUBLIC_GRAFANA_URL=http://grafana:3000
NEXT_PUBLIC_PROMETHEUS_URL=http://prometheus:9090
NEXT_PUBLIC_WS_URL=ws://gateway:8001

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=secure_password_here

# Monitoring
PROMETHEUS_RETENTION=30d
```

### Grafana Provisioning
Dashboards are automatically provisioned from:
```
repos/at-observability/
├── grafana_dashboards/          # Dashboard JSON files
├── grafana-provisioning/
│   ├── dashboards/             # Dashboard config
│   └── datasources/            # Prometheus datasource
└── prometheus.yml              # Metrics collection config
```

## 🚨 Alerting Setup

### Prometheus Alert Rules
```yaml
# Gateway down
- alert: GatewayDown
  expr: up{job="gateway"} == 0
  for: 1m
  labels:
    severity: critical

# High error rate
- alert: HighErrorRate
  expr: rate(gateway_webhooks_processed_total{status="error"}[5m]) > 0.01
  for: 5m
  labels:
    severity: warning

# Agent processing slow
- alert: AgentProcessingSlow
  expr: histogram_quantile(0.95, rate(orchestrator_agent_processing_duration_seconds_bucket[5m])) > 5
  for: 10m
  labels:
    severity: warning
```

### Notification Channels
Configure in Grafana:
- **Slack**: Webhook integration for alerts
- **Email**: SMTP configuration for notifications
- **PagerDuty**: Critical incident escalation
- **Discord**: Development team notifications

## 📱 Mobile & Responsive Design

The NEO Control Center is fully responsive and mobile-optimized:
- **Desktop**: Full feature set with multi-panel layouts
- **Tablet**: Responsive grid system with touch interactions
- **Mobile**: Condensed views with essential metrics
- **PWA**: Progressive Web App capabilities for offline access

## 🔐 Security & Authentication

### Production Security
```bash
# Change default passwords
export GRAFANA_ADMIN_PASSWORD="your_secure_password"

# Enable HTTPS
export GRAFANA_PROTOCOL=https
export GRAFANA_CERT_FILE=/path/to/cert.pem
export GRAFANA_CERT_KEY=/path/to/key.pem

# Configure OAuth
export GF_AUTH_GOOGLE_ENABLED=true
export GF_AUTH_GOOGLE_CLIENT_ID="your_client_id"
export GF_AUTH_GOOGLE_CLIENT_SECRET="your_client_secret"
```

### Access Control
- **Admin**: Full system control and configuration
- **Operator**: Service management and monitoring
- **Viewer**: Read-only dashboard access
- **API**: Programmatic access with API keys

## 🛠️ Troubleshooting

### Common Issues

#### Dashboards Not Loading
```bash
# Check Grafana provisioning
docker compose logs grafana

# Verify dashboard files
ls -la repos/at-observability/grafana_dashboards/

# Restart Grafana
docker compose restart grafana
```

#### Metrics Missing
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify service metrics endpoints
curl http://localhost:8001/metrics  # Gateway
curl http://localhost:8008/metrics  # Output Manager
curl http://localhost:8010/metrics  # Agent Orchestrator
```

#### Control Center Connection Issues
```bash
# Check API connectivity
curl http://localhost:8001/healthz

# Verify WebSocket connection
docker compose logs control-center

# Check environment variables
docker compose config | grep NEXT_PUBLIC
```

### Performance Tuning

#### Prometheus Optimization
```yaml
# prometheus.yml
global:
  scrape_interval: 15s          # Balance between freshness and load
  evaluation_interval: 15s      # Rule evaluation frequency

# Storage optimization
storage.tsdb.retention.time: 30d    # Adjust based on disk space
storage.tsdb.retention.size: 10GB   # Set maximum disk usage
```

#### Grafana Optimization
```ini
# grafana.ini
[dashboards]
min_refresh_interval = 5s       # Minimum dashboard refresh

[database]
max_open_conn = 100            # Database connection pool
max_idle_conn = 10             # Idle connections
```

## 📚 API Reference

### NEO Control Center API
```typescript
// Get system health
GET /api/health

// Get real-time metrics
GET /api/metrics/system
GET /api/metrics/services
GET /api/metrics/trading

// Service management
POST /api/services/{service}/restart
GET /api/services/{service}/logs
PUT /api/services/{service}/config

// WebSocket events
ws://localhost:3001/ws
- system.health.updated
- metrics.real_time
- alerts.new
- trading.portfolio.updated
```

### Prometheus Query Examples
```promql
# Request rate per service
rate(gateway_webhooks_processed_total[5m])

# Error percentage
rate(gateway_webhooks_processed_total{status="error"}[5m]) / rate(gateway_webhooks_processed_total[5m]) * 100

# P95 latency
histogram_quantile(0.95, rate(gateway_webhook_processing_duration_seconds_bucket[5m]))

# Agent success rate
rate(orchestrator_agent_requests_total{status="success"}[5m]) / rate(orchestrator_agent_requests_total[5m])
```

## 🎯 Next Steps

1. **Customize Dashboards**: Modify JSON files in `grafana_dashboards/`
2. **Set Up Alerting**: Configure notification channels in Grafana
3. **Enable Authentication**: Set up OAuth or LDAP integration
4. **Add Custom Metrics**: Extend Prometheus configuration
5. **Mobile App**: Consider native mobile app development
6. **Integration**: Connect with external monitoring tools (DataDog, New Relic)

## 📞 Support

- **Documentation**: `/docs/` directory
- **Issues**: GitHub Issues with monitoring/gui labels
- **Slack**: #neo-monitoring channel
- **Emergency**: Follow escalation in `ALERTS.md`

---

**🎉 Your NEO v1.0.0 system now has enterprise-grade monitoring and beautiful graphical interfaces!**
# 🎛️ NEO v1.0.0 Monitoring Quick Access

## 📊 **Primary Interfaces**

### **Grafana Dashboards** (Main Monitoring Interface)
- 🌐 **URL**: http://localhost:3000
- 👤 **Login**: admin / admin123
- 📊 **Dashboards**:
  - Gateway Performance
  - Agent Orchestrator v1.0.0
  - Output Manager v1.0.0
  - Real-Time Trading Flow

### **Prometheus** (Metrics & Queries)
- 🌐 **URL**: http://localhost:9090
- 🎯 **Targets**: http://localhost:9090/targets
- 📈 **Query**: http://localhost:9090/graph
- ⚠️ **Alerts**: http://localhost:9090/alerts

---

## 🏗️ **Infrastructure Monitoring**

### **cAdvisor** (Container Monitoring)
- 🌐 **URL**: http://localhost:8080
- 📦 **Purpose**: Real-time container resource usage
- 📊 **Features**: CPU, memory, network, filesystem per container

### **Node Exporter** (System Metrics)
- 🌐 **URL**: http://localhost:9100/metrics
- 💻 **Purpose**: System-level metrics (CPU, RAM, disk, network)
- 📈 **Data**: Raw Prometheus metrics format

### **Redis Exporter** (Database Monitoring)
- 🌐 **URL**: http://localhost:9121/metrics
- 🔴 **Purpose**: Redis performance and health
- 📊 **Metrics**: Connections, memory, commands, persistence

### **NATS Monitoring** (Message Broker)
- 🌐 **Health**: http://localhost:8222/healthz
- 📊 **Stats**: http://localhost:8222/monitoring
- 🔄 **JetStream**: http://localhost:8222/jsz

---

## 🔧 **NEO Service Endpoints** (When Running)

### **Gateway Service**
- 🌐 **Health**: http://localhost:8001/healthz
- 📊 **Metrics**: http://localhost:8001/metrics
- 📝 **API**: http://localhost:8001/docs

### **Agent Orchestrator**
- 🌐 **Health**: http://localhost:8010/healthz
- 📊 **Metrics**: http://localhost:8010/metrics
- 📝 **API**: http://localhost:8010/docs

### **Output Manager**
- 🌐 **Health**: http://localhost:8008/healthz
- 📊 **Metrics**: http://localhost:8008/metrics
- 📝 **API**: http://localhost:8008/docs

---

## ⚡ **Quick Commands**

### **Check All Services**
```bash
# Monitoring stack status
docker-compose -f docker-compose.production.yml ps

# Service health checks
curl http://localhost:3000/api/health    # Grafana
curl http://localhost:9090/-/healthy     # Prometheus
curl http://localhost:8080/healthz       # cAdvisor (if available)
```

### **View Live Metrics**
```bash
# System memory usage
curl -s "http://localhost:9090/api/v1/query?query=(node_memory_MemTotal_bytes-node_memory_MemAvailable_bytes)/node_memory_MemTotal_bytes*100" | jq '.data.result[0].value[1]'

# Container count
curl -s "http://localhost:9090/api/v1/query?query=count(container_last_seen)" | jq '.data.result[0].value[1]'

# Redis connections
curl -s "http://localhost:9090/api/v1/query?query=redis_connected_clients" | jq '.data.result[0].value[1]'
```

---

## 🎯 **Monitoring Workflow**

### **1. Start Here** 🚀
- **Grafana**: http://localhost:3000 (Main monitoring interface)

### **2. Deep Dive** 🔍
- **Prometheus**: http://localhost:9090 (Query specific metrics)
- **cAdvisor**: http://localhost:8080 (Container performance)

### **3. System Analysis** 💻
- **Node Metrics**: http://localhost:9100/metrics (System resources)
- **NATS Stats**: http://localhost:8222/monitoring (Message flow)

### **4. Troubleshooting** 🔧
- Check service health endpoints
- Query Prometheus for specific metrics
- Use cAdvisor for container analysis

---

## 📱 **Bookmark These URLs**

**Essential Bookmarks:**
- 📊 Grafana: http://localhost:3000
- 📈 Prometheus: http://localhost:9090
- 📦 cAdvisor: http://localhost:8080

**Quick Checks:**
- 🎯 Prometheus Targets: http://localhost:9090/targets
- ⚠️ Prometheus Alerts: http://localhost:9090/alerts
- 🔴 Redis Metrics: http://localhost:9121/metrics

**NEO Services (when running):**
- 🚪 Gateway: http://localhost:8001/healthz
- 🤖 Orchestrator: http://localhost:8010/healthz
- 📲 Output: http://localhost:8008/healthz

---

## 🎉 **You Now Have Complete Monitoring!**

✅ **4 Professional NEO Dashboards** in Grafana
✅ **5 Infrastructure Monitoring Services** running
✅ **Real-time System Monitoring** with web interfaces
✅ **Production-ready Alerting** capabilities
✅ **Complete Documentation** for all components

**Your NEO v1.0.0 system has enterprise-grade monitoring and visualization!** 🚀📊
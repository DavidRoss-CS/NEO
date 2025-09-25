# NEO v1.0.0 Infrastructure Monitoring Guide

Complete documentation of the underlying infrastructure monitoring services that power the NEO dashboard system.

## 🏗️ Infrastructure Monitoring Stack Overview

The NEO monitoring system includes **foundational infrastructure services** that collect system-level metrics, alongside the NEO-specific dashboards:

### **Core Infrastructure Services**
1. **Prometheus** (Port 9090) - Metrics collection and storage
2. **cAdvisor** (Port 8080) - Container monitoring
3. **Node Exporter** (Port 9100) - System metrics collection
4. **Redis Exporter** (Port 9121) - Redis database monitoring
5. **NATS Monitoring** (Port 8222) - Message broker monitoring

---

## 📊 1. Prometheus (Port 9090)

### **Access Information**
- **URL**: http://localhost:9090
- **Purpose**: Central metrics collection, storage, and querying
- **Service**: Core monitoring infrastructure

### **Key Features**

#### **Metrics Collection**
- Scrapes metrics from all NEO services every 15 seconds
- Stores time-series data with 30-day retention
- Provides PromQL query language for analysis

#### **Web Interface Sections**

##### **🎯 Targets Status** (http://localhost:9090/targets)
Shows health of all monitored services:
```bash
# Check all targets
curl -s "http://localhost:9090/api/v1/targets" | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastScrape: .lastScrape}'
```

**Expected Targets:**
- ✅ `prometheus` (localhost:9090) - Self-monitoring
- ✅ `node` (node-exporter:9100) - System metrics
- ✅ `redis` (redis-exporter:9121) - Redis metrics
- ✅ `cadvisor` (cadvisor:8080) - Container metrics
- ⏳ `gateway` (at-gateway:8001) - When NEO gateway running
- ⏳ `agent-orchestrator` (agent-orchestrator:8010) - When orchestrator running
- ⏳ `output-manager` (output-manager:8008) - When output manager running

##### **📈 Graph Explorer** (http://localhost:9090/graph)
Interactive query interface for exploring metrics:

**Common Infrastructure Queries:**
```promql
# System memory usage
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# CPU usage by core
rate(node_cpu_seconds_total{mode!="idle"}[5m]) * 100

# Container memory usage
container_memory_usage_bytes{name!=""}

# Redis connection count
redis_connected_clients

# NATS message rates
rate(nats_messages_in[5m])

# Services up/down status
up
```

##### **⚠️ Alerts** (http://localhost:9090/alerts)
Shows active alerts and alert rules:
```bash
# Check active alerts
curl -s "http://localhost:9090/api/v1/alerts" | jq '.data.alerts[] | {alertname: .labels.alertname, state: .state}'
```

### **Configuration**
- **Config File**: `repos/at-observability/prometheus.yml`
- **Scrape Interval**: 15 seconds
- **Retention**: 30 days
- **Storage**: Docker volume `prometheus-data`

### **Usage Scenarios**

#### **During Development**
- **Metric Discovery**: Explore available metrics for new dashboards
- **Query Testing**: Test PromQL queries before adding to Grafana
- **Target Debugging**: Verify services are exposing metrics correctly

#### **During Testing**
- **Performance Analysis**: Query historical performance data
- **Load Testing**: Monitor resource usage during tests
- **Bottleneck Identification**: Query slowest components

#### **In Production**
- **Alerting Backend**: Evaluates alert rules every 15 seconds
- **Data Source**: Primary data source for all Grafana dashboards
- **API Access**: External tools can query metrics via API

---

## 📦 2. cAdvisor (Port 8080)

### **Access Information**
- **URL**: http://localhost:8080
- **Purpose**: Container resource monitoring and web interface
- **Service**: Google cAdvisor (Container Advisor)

### **Web Interface Features**

#### **🏠 Overview Page** (http://localhost:8080/)
Real-time container resource usage:
- **CPU Usage**: Per-container CPU utilization
- **Memory Usage**: Container memory consumption
- **Network I/O**: Container network traffic
- **Filesystem**: Container disk usage

#### **📊 Container Details** (http://localhost:8080/containers/)
Detailed view for specific containers:
- **Resource Limits**: Configured CPU/memory limits
- **Usage History**: Historical resource consumption
- **Process Information**: Running processes in container
- **Performance Counters**: Detailed performance metrics

### **Key Metrics Exposed**
```promql
# Container CPU usage
rate(container_cpu_usage_seconds_total{name!=""}[5m])

# Container memory usage
container_memory_usage_bytes{name!=""}

# Container network I/O
rate(container_network_receive_bytes_total[5m])
rate(container_network_transmit_bytes_total[5m])

# Container filesystem usage
container_fs_usage_bytes{name!=""}

# Container restart count
container_start_time_seconds{name!=""}
```

### **Usage Scenarios**

#### **Container Performance Analysis**
```bash
# View all NEO containers
curl -s "http://localhost:8080/api/v1.3/containers" | jq '.[] | select(.spec.labels."com.docker.compose.project" == "neo")'
```

#### **Resource Planning**
- **Memory Usage Trends**: Plan container memory limits
- **CPU Scaling**: Identify CPU-intensive containers
- **Network Bottlenecks**: Monitor container network usage
- **Storage Growth**: Track container filesystem usage

#### **Troubleshooting**
- **High CPU**: Identify containers consuming excessive CPU
- **Memory Leaks**: Monitor memory usage growth patterns
- **I/O Issues**: Analyze network and disk I/O patterns
- **Container Crashes**: Monitor restart patterns

### **Integration with NEO Dashboards**
- **Infrastructure Panels**: Container metrics in Grafana dashboards
- **Service Health**: Container status affects NEO service health
- **Performance Correlation**: Container resources vs NEO performance

---

## 💻 3. Node Exporter (Port 9100)

### **Access Information**
- **URL**: http://localhost:9100/metrics
- **Purpose**: System-level metrics collection (CPU, memory, disk, network)
- **Service**: Prometheus Node Exporter

### **System Metrics Categories**

#### **🖥️ CPU Metrics**
```promql
# CPU usage by mode
rate(node_cpu_seconds_total[5m])

# CPU usage percentage (excluding idle)
(1 - rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100

# Load averages
node_load1
node_load5
node_load15
```

#### **🧠 Memory Metrics**
```promql
# Total system memory
node_memory_MemTotal_bytes

# Available memory
node_memory_MemAvailable_bytes

# Memory usage percentage
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100

# Swap usage
node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes
```

#### **💾 Disk Metrics**
```promql
# Disk space usage
(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100

# Disk I/O operations
rate(node_disk_reads_completed_total[5m])
rate(node_disk_writes_completed_total[5m])

# Disk I/O time
rate(node_disk_io_time_seconds_total[5m])
```

#### **🌐 Network Metrics**
```promql
# Network I/O bytes
rate(node_network_receive_bytes_total[5m])
rate(node_network_transmit_bytes_total[5m])

# Network errors
rate(node_network_receive_errs_total[5m])
rate(node_network_transmit_errs_total[5m])
```

### **Usage Scenarios**

#### **System Health Monitoring**
```bash
# Check system resource usage
curl -s "http://localhost:9090/api/v1/query?query=node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes*100" | jq '.data.result[0].value[1]'
```

#### **Capacity Planning**
- **Memory Trends**: Plan system memory upgrades
- **Disk Growth**: Monitor disk usage trends
- **CPU Scaling**: Identify CPU bottlenecks
- **Network Capacity**: Monitor bandwidth usage

#### **Performance Troubleshooting**
- **High Load**: Investigate system load spikes
- **Memory Pressure**: Analyze memory usage patterns
- **Disk I/O**: Identify storage bottlenecks
- **Network Issues**: Diagnose network problems

---

## 🔴 4. Redis Exporter (Port 9121)

### **Access Information**
- **URL**: http://localhost:9121/metrics
- **Purpose**: Redis database monitoring for NEO context store
- **Service**: Redis Exporter for Prometheus

### **Key Redis Metrics**

#### **📊 Connection Metrics**
```promql
# Connected clients
redis_connected_clients

# Client connections per second
rate(redis_total_connections_received_total[5m])

# Rejected connections
redis_rejected_connections_total
```

#### **🧠 Memory Metrics**
```promql
# Used memory
redis_memory_used_bytes

# Memory usage percentage
redis_memory_used_bytes / redis_config_maxmemory * 100

# Memory fragmentation
redis_mem_fragmentation_ratio
```

#### **⚡ Performance Metrics**
```promql
# Commands processed per second
rate(redis_total_commands_processed_total[5m])

# Keyspace hits vs misses
rate(redis_keyspace_hits_total[5m])
rate(redis_keyspace_misses_total[5m])

# Hit ratio percentage
rate(redis_keyspace_hits_total[5m]) / (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m])) * 100
```

#### **💾 Persistence Metrics**
```promql
# Last save time
redis_last_save_time

# RDB saves
redis_rdb_saves_since_last_save

# AOF size
redis_aof_current_size_bytes
```

### **Usage Scenarios**

#### **NEO Context Store Monitoring**
- **Agent Contexts**: Monitor active AI agent contexts
- **Memory Usage**: Track Redis memory consumption
- **Performance**: Monitor Redis response times
- **Persistence**: Ensure data durability

#### **Performance Optimization**
```bash
# Check Redis performance
curl -s "http://localhost:9090/api/v1/query?query=rate(redis_total_commands_processed_total[5m])" | jq '.data.result[0].value[1]'
```

#### **Troubleshooting**
- **High Memory**: Investigate memory usage patterns
- **Slow Queries**: Monitor command execution times
- **Connection Issues**: Track client connections
- **Persistence Problems**: Monitor save operations

---

## 📡 5. NATS Monitoring (Port 8222)

### **Access Information**
- **URL**: http://localhost:8222/monitoring
- **Purpose**: NATS JetStream message broker monitoring
- **Service**: NATS Server with monitoring enabled

### **NATS Monitoring Endpoints**

#### **📊 Server Status** (http://localhost:8222/healthz)
```bash
# Check NATS health
curl -s "http://localhost:8222/healthz" | jq
```

#### **📈 Monitoring Stats** (http://localhost:8222/monitoring)
JSON endpoint with server statistics:
```bash
# Get NATS stats
curl -s "http://localhost:8222/monitoring" | jq '{
  connections: .connections,
  messages: .in_msgs,
  bytes: .in_bytes,
  uptime: .uptime
}'
```

#### **🔄 JetStream Stats** (http://localhost:8222/jsz)
JetStream-specific metrics:
```bash
# Get JetStream stats
curl -s "http://localhost:8222/jsz" | jq '{
  streams: .streams,
  consumers: .consumers,
  messages: .messages,
  bytes: .bytes
}'
```

### **Key NATS Metrics**

#### **📨 Message Flow**
```promql
# Messages in/out per second
rate(nats_messages_in[5m])
rate(nats_messages_out[5m])

# Bytes in/out per second
rate(nats_bytes_in[5m])
rate(nats_bytes_out[5m])

# JetStream messages
nats_jetstream_stream_messages
```

#### **🔗 Connection Metrics**
```promql
# Active connections
nats_connections

# Subscriptions
nats_subscriptions

# Slow consumers
nats_slow_consumers
```

### **Usage Scenarios**

#### **NEO Message Flow Monitoring**
- **Trading Signals**: Monitor signal message flow
- **Agent Requests**: Track agent processing queues
- **Output Delivery**: Monitor notification delivery queues
- **Consumer Lag**: Ensure low-latency message processing

#### **Performance Analysis**
- **Throughput**: Monitor messages per second
- **Latency**: Track message processing delays
- **Consumer Health**: Monitor consumer lag
- **Resource Usage**: Track NATS memory/CPU usage

---

## 🎯 Infrastructure Dashboard Integration

### **Creating Infrastructure Dashboards**

#### **System Overview Dashboard**
```json
{
  "title": "NEO Infrastructure Overview",
  "panels": [
    {
      "title": "System CPU Usage",
      "targets": [{"expr": "(1 - rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100"}]
    },
    {
      "title": "Memory Usage",
      "targets": [{"expr": "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100"}]
    },
    {
      "title": "Container CPU",
      "targets": [{"expr": "rate(container_cpu_usage_seconds_total{name!=\"\"}[5m]) * 100"}]
    },
    {
      "title": "Redis Performance",
      "targets": [{"expr": "rate(redis_total_commands_processed_total[5m])"}]
    }
  ]
}
```

### **Adding Infrastructure Panels to NEO Dashboards**

#### **Resource Usage Panels**
Add to existing NEO dashboards:
- **System Resources**: CPU, memory, disk usage
- **Container Health**: Container-specific resource usage
- **Database Performance**: Redis metrics for context store
- **Message Broker**: NATS performance and queue depths

---

## 🚨 Infrastructure Alerting

### **Critical Infrastructure Alerts**

#### **System Resource Alerts**
```yaml
# High CPU usage
- alert: HighCPUUsage
  expr: (1 - rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100 > 80
  for: 5m
  labels:
    severity: warning

# High memory usage
- alert: HighMemoryUsage
  expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 85
  for: 5m
  labels:
    severity: warning

# Disk space low
- alert: DiskSpaceLow
  expr: (node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100 > 85
  for: 5m
  labels:
    severity: warning
```

#### **Container Resource Alerts**
```yaml
# Container high memory usage
- alert: ContainerHighMemory
  expr: container_memory_usage_bytes{name!=""} / container_spec_memory_limit_bytes > 0.9
  for: 5m
  labels:
    severity: warning

# Container restart
- alert: ContainerRestart
  expr: increase(container_last_seen[5m]) > 0
  for: 0m
  labels:
    severity: warning
```

#### **Redis Alerts**
```yaml
# Redis high memory usage
- alert: RedisHighMemory
  expr: redis_memory_used_bytes / redis_config_maxmemory > 0.8
  for: 5m
  labels:
    severity: warning

# Redis disconnected
- alert: RedisDown
  expr: up{job="redis"} == 0
  for: 1m
  labels:
    severity: critical
```

---

## 🔧 Infrastructure Troubleshooting Guide

### **Common Issues and Solutions**

#### **High CPU Usage**
```bash
# Identify CPU-intensive processes
curl -s "http://localhost:9090/api/v1/query?query=topk(5, rate(container_cpu_usage_seconds_total{name!=\"\"}[5m]))" | jq

# Check system load
curl -s "http://localhost:9090/api/v1/query?query=node_load5" | jq '.data.result[0].value[1]'
```

#### **Memory Issues**
```bash
# Check memory usage by container
curl -s "http://localhost:9090/api/v1/query?query=topk(5, container_memory_usage_bytes{name!=\"\"})" | jq

# System memory breakdown
curl -s "http://localhost:9090/api/v1/query?query=node_memory_MemTotal_bytes" | jq
```

#### **Disk Problems**
```bash
# Check disk usage
curl -s "http://localhost:9090/api/v1/query?query=(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100" | jq

# Disk I/O rates
curl -s "http://localhost:9090/api/v1/query?query=rate(node_disk_reads_completed_total[5m])" | jq
```

#### **Network Issues**
```bash
# Network utilization
curl -s "http://localhost:9090/api/v1/query?query=rate(node_network_receive_bytes_total[5m]) * 8" | jq

# Network errors
curl -s "http://localhost:9090/api/v1/query?query=rate(node_network_receive_errs_total[5m])" | jq
```

---

## 📊 Infrastructure Metrics Summary

### **Available Monitoring Services**
- ✅ **Prometheus** (9090): Central metrics and alerting
- ✅ **cAdvisor** (8080): Container monitoring and web UI
- ✅ **Node Exporter** (9100): System metrics collection
- ✅ **Redis Exporter** (9121): Database performance monitoring
- ✅ **NATS Monitoring** (8222): Message broker monitoring

### **Key Infrastructure Metrics**
- 📈 **500+ System Metrics**: CPU, memory, disk, network
- 📦 **100+ Container Metrics**: Resource usage per container
- 🔴 **50+ Redis Metrics**: Database performance and health
- 📡 **30+ NATS Metrics**: Message broker performance

### **Monitoring Coverage**
- ✅ **Hardware Resources**: CPU, RAM, storage, network
- ✅ **Container Runtime**: Docker container performance
- ✅ **Data Storage**: Redis context store monitoring
- ✅ **Message Broker**: NATS JetStream performance
- ✅ **Service Health**: All infrastructure components

## 🎉 Complete Infrastructure Monitoring

Your NEO v1.0.0 system now has **enterprise-grade infrastructure monitoring** with:

- 📊 **Real-time web interfaces** for all infrastructure components
- 📈 **Comprehensive metrics collection** from system to application level
- 🚨 **Production-ready alerting** for all critical infrastructure components
- 🔧 **Troubleshooting tools** for rapid issue resolution
- 📱 **Integration ready** for custom dashboards and external monitoring tools

**Use these infrastructure monitoring services alongside your NEO dashboards for complete system observability!** 🚀📊
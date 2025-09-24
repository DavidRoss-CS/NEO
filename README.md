# Agentic Trading Architecture (NEO)

**Multi-repo, event-driven trading architecture for autonomous AI agents.**

## Overview

NEO (New Economic Order) is a comprehensive trading platform that orchestrates AI agents for automated trading across futures, FX, and crypto markets. Built on event-driven architecture with NATS messaging, it enables independent development, deployment, and scaling of trading strategies.

## Quick Start

### 🚀 **For Development & Testing** (Minimal Setup)
```bash
# Start only core services (fastest startup)
make up
# OR manually:
docker-compose -f docker-compose.minimal.yml up -d
```

### 🏭 **For Production & Full Features** (Complete System)
```bash
# Start all implemented services
docker-compose -f docker-compose.production.yml up -d

# Verify all services
curl http://localhost:8001/healthz  # Gateway
curl http://localhost:8002/healthz  # Agent
curl http://localhost:8003/healthz  # Meta-agent (multi-agent coordination)
curl http://localhost:8004/healthz  # Execution Simulator
curl http://localhost:8005/healthz  # Backtester
curl http://localhost:8006/healthz  # Broker Adapters
curl http://localhost:8009/healthz  # Audit Trail
```

2) **Verify System Health**:
   ```bash
   make health
   # OR manually:
   curl http://localhost:8001/healthz  # Gateway
   curl http://localhost:8004/healthz  # Execution Simulator
   ```

3) **Test End-to-End**:
   ```bash
   # Run golden path test
   make golden

   # OR test webhook manually with proper HMAC:
   TIMESTAMP=$(date +%s)
   NONCE="test-$(date +%s)"
   PAYLOAD='{"instrument":"EURUSD","price":"1.0850","signal":"buy","strength":0.85}'
   SECRET="test-secret"
   MESSAGE="${TIMESTAMP}.${NONCE}.${PAYLOAD}"
   SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$SECRET" -hex | cut -d' ' -f2)

   curl -X POST http://localhost:8001/webhook/tradingview \
     -H 'Content-Type: application/json' \
     -H "X-Timestamp: $TIMESTAMP" \
     -H "X-Nonce: $NONCE" \
     -H "X-Signature: $SIGNATURE" \
     -d "$PAYLOAD"
   ```

## Architecture

### 🏗️ **Core Services** (Always Running)
- **at-gateway** (8001): Market data ingestion and webhook validation
- **at-exec-sim** (8004): Trade execution and simulation environment

### 🧠 **Intelligence Layer** (Production Features)
- **at-agent-mcp** (8002): AI trading strategy agent (momentum, risk, sentiment)
- **at-meta-agent** (8003): Multi-agent coordination and decision synthesis
- **at-strategy-manager** (8007): Dynamic strategy loading and management

### 🔌 **Integration Layer** (Live Trading)
- **at-broker-adapters** (8006): Real broker connections (IB, Alpaca, Paper)
- **at-backtester** (8005): Historical strategy validation

### 📊 **Compliance & Monitoring**
- **at-audit-trail** (8009): Immutable audit trail with hash chaining
- **at-core**: Shared contracts, schemas, and event definitions

### 🔄 **Data Flow**
```
Webhook → Gateway → NATS → Agent → Meta-Agent → Execution → Broker → Audit
   8001      ↓        ↓      8002      8003        8004       8006     8009
```

## Sprint 1 Status ✅

- Port conflicts resolved (gateway:8001, mcp:8002, exec:8004)
- Environment variables standardized across all services
- Authentication headers complete (X-Signature, X-Timestamp, X-Nonce, etc.)
- Error catalogs implemented (GW-xxx, CORE-xxx, MCP-xxx namespaces)
- Configuration consistency achieved
- v0.1.0 baseline tagged and committed

## Deployment Options ⚡

### 📦 **Tiered Architecture Approach**

| Setup | Services | Use Case | Startup Time | Resources |
|-------|----------|----------|--------------|-----------|
| **Minimal** | 3 core | Development, Testing | ~30 seconds | 512MB |
| **Production** | 8 full | Trading, Integration | ~90 seconds | 2GB |

### 🎯 **When to Use Each:**

**`docker-compose.minimal.yml`** - Development & Quick Testing
- Core trading flow only (Gateway → Exec-Sim)
- Fastest startup for rapid development
- Perfect for webhook testing and basic functionality

**`docker-compose.production.yml`** - Full Features & Live Trading
- Multi-agent coordination (Meta-agent)
- Strategy backtesting and validation
- Real broker connections
- Full audit trail compliance
- Complete system integration

## Troubleshooting 🔧

**Services won't start:**
```bash
# Check Docker is running
docker --version

# View service logs
make logs

# Check individual service status
docker-compose -f docker-compose.minimal.yml ps
```

**Webhook authentication failing:**
- Ensure HMAC signature uses format: `{timestamp}.{nonce}.{payload}`
- Secret must be `test-secret` (from docker-compose.minimal.yml)
- Timestamp must be Unix epoch format (not ISO)
- Payload must use `signal` and `strength` (not `action` and `confidence`)

**Network issues:**
```bash
# Check network exists
docker network ls | grep neo

# Recreate network if needed
make clean && make up
```

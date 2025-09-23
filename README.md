# Agentic Trading Architecture (NEO)

**Multi-repo, event-driven trading architecture for autonomous AI agents.**

## Overview

NEO (New Economic Order) is a comprehensive trading platform that orchestrates AI agents for automated trading across futures, FX, and crypto markets. Built on event-driven architecture with NATS messaging, it enables independent development, deployment, and scaling of trading strategies.

## Quick Start (Single Repo Mode)

1) **Start Infrastructure**:
   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```

2) **Start Services** (in separate terminals):
   ```bash
   # Gateway (port 8001)
   uvicorn repos/at-gateway/at_gateway/app:app --port 8001

   # MCP Server (port 8002)
   python -m repos.at_mcp.at_mcp.server

   # Execution Sim (port 8004)
   python -m repos.at_exec_sim.at_exec_sim.app
   ```

3) **Test End-to-End**:
   ```bash
   curl -X POST http://localhost:8001/webhook/tradingview \
     -H 'Content-Type: application/json' \
     -H 'X-Timestamp: 2024-01-15T10:30:00Z' \
     -H 'X-Signature: sha256=...' \
     -d '{"instrument":"EURUSD","price":"1.0850","action":"buy","confidence":0.85}'
   ```

## Architecture

- **at-gateway**: Market data ingestion and webhook validation
- **at-core**: Shared contracts, schemas, and event definitions
- **at-agents**: AI trading strategy agents (momentum, risk, sentiment)
- **at-orchestrator**: Multi-agent coordination and decision synthesis
- **at-mcp**: Model Context Protocol servers for agent tooling
- **at-exec-sim**: Trade execution and simulation environment
- **at-observability**: Metrics, monitoring, and alerting

## Sprint 1 Status ✅

- Port conflicts resolved (gateway:8001, mcp:8002, exec:8004)
- Environment variables standardized across all services
- Authentication headers complete (X-Signature, X-Timestamp, X-Nonce, etc.)
- Error catalogs implemented (GW-xxx, CORE-xxx, MCP-xxx namespaces)
- Configuration consistency achieved
- v0.1.0 baseline tagged and committed

## Next: Sprint 2

Ready for T-1200 (at-exec-sim bootstrap) and full end-to-end integration testing.

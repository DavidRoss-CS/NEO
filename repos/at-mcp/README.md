# Agentic Trading - MCP Servers

**Tool layer providing deterministic capabilities to LLM agents and orchestrators.**

## Purpose

The `at-mcp` repository contains MCP (Model Context Protocol) servers that expose deterministic tools to LLM agents and orchestrators. These servers provide capabilities like data fetching, feature calculation, risk checks, execution simulation, and state management - but do **not** embed trading strategy logic.

## Responsibilities

✅ **What we do**:
- Expose standardized tools via MCP protocol
- Provide data fetch and feature calculation capabilities
- Execute risk limit checks and validation
- Simulate execution quotes and slippage estimates
- Manage shared state storage and retrieval
- Enforce input validation and rate limiting
- Maintain tool observability and metrics

❌ **What we don't do**:
- Implement trading strategies or decision logic
- Store persistent trading state (only ephemeral shared state)
- Execute actual trades (only simulation and quotes)
- Define schemas or contracts (that's at-core's responsibility)
- Route or orchestrate between agents (that's at-orchestrator)

## Data Flow

```
Agent/Orchestrator
     ↓ (MCP call)
MCP Server Tool
     ↓ (validates input JSON Schema)
Tool Implementation
     ↓ (may fetch from HTTP/NATS/Redis)
External Data Source
     ↓ (returns structured data)
MCP Server
     ↓ (validates output JSON Schema)
Agent/Orchestrator
```

**Key principle**: MCP servers are stateless capability providers that transform inputs to outputs deterministically, with optional side effects to external systems.

## Quick Start

### Prerequisites
```bash
# Required infrastructure
docker compose up -d nats redis

# Verify services
curl http://localhost:8222/healthz  # NATS
redis-cli ping                      # Redis
```

### Install MCP Dependencies
```bash
pip install mcp anthropic pydantic fastapi uvicorn redis asyncio-nats-client
```

### Run Sample MCP Server
```python
import asyncio
import json
from datetime import datetime
from mcp.server import Server
from mcp.types import Tool, TextContent

class TradingMCPServer:
    def __init__(self):
        self.server = Server("trading-tools")
        self.setup_tools()

    def setup_tools(self):
        @self.server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="features.ohlcv_window",
                    description="Fetch OHLCV data and compute technical features",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "start": {"type": "string", "format": "date-time"},
                            "end": {"type": "string", "format": "date-time"},
                            "interval": {"type": "string", "enum": ["1m", "5m", "1h", "1d"]},
                            "features": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["symbol", "start", "end", "interval", "features"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name == "features.ohlcv_window":
                return await self.fetch_ohlcv_features(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

    async def fetch_ohlcv_features(self, args):
        """Sample OHLCV feature calculation."""
        # Simulate data fetch and feature calculation
        mock_data = {
            "symbol": args["symbol"],
            "rows": [
                {
                    "timestamp": "2024-01-15T10:00:00Z",
                    "open": 1.0940,
                    "high": 1.0950,
                    "low": 1.0935,
                    "close": 1.0945,
                    "volume": 12500
                }
            ],
            "stats": {
                "sma_20": 1.0942,
                "rsi_14": 65.2,
                "volatility": 0.0012
            }
        }

        return [TextContent(
            type="text",
            text=json.dumps(mock_data)
        )]

    async def run(self):
        # In production, would integrate with NATS/Redis
        async with self.server.run_stdio():
            await asyncio.Event().wait()

# Run server
if __name__ == "__main__":
    server = TradingMCPServer()
    asyncio.run(server.run())
```

### Test Tool Access
```bash
# List available tools
echo '{"method": "tools/list", "params": {}}' | python trading_mcp_server.py

# Call OHLCV tool
echo '{
  "method": "tools/call",
  "params": {
    "name": "features.ohlcv_window",
    "arguments": {
      "symbol": "EURUSD",
      "start": "2024-01-15T09:00:00Z",
      "end": "2024-01-15T10:00:00Z",
      "interval": "1m",
      "features": ["sma", "rsi"]
    }
  }
}' | python trading_mcp_server.py
```

## Repository Layout

```
at-mcp/
├── README.md                    # This file
├── MCP_OVERVIEW.md              # Protocol details and design choices
├── SERVER_TEMPLATE.md           # Reference implementation template
├── TOOLS_CATALOG.md             # Complete tool documentation
├── PROMPTS.md                   # System prompts for agent usage
├── TEST_STRATEGY.md             # Testing approach and CI gates
├── SECURITY.md                  # Auth, validation, rate limiting
├── servers/                     # MCP server implementations
│   ├── features/
│   │   ├── server.py           # OHLCV and technical indicators
│   │   ├── config.py           # Configuration management
│   │   └── tests/              # Unit tests
│   ├── risk/
│   │   ├── server.py           # Risk limits and validation
│   │   ├── rules.py            # Risk rule engine
│   │   └── tests/              # Unit tests
│   ├── execution/
│   │   ├── server.py           # Execution simulation
│   │   ├── simulator.py        # Slippage and fill models
│   │   └── tests/              # Unit tests
│   └── storage/
│       ├── server.py           # Shared state management
│       ├── redis_adapter.py    # Redis integration
│       └── tests/              # Unit tests
├── shared/                      # Common utilities
│   ├── mcp_base.py             # Base MCP server class
│   ├── validation.py           # JSON Schema validation
│   ├── auth.py                 # Authentication middleware
│   ├── rate_limiter.py         # Rate limiting
│   └── metrics.py              # Prometheus metrics
└── tests/                       # Integration tests
    ├── test_tool_integration.py
    ├── test_schema_compliance.py
    └── fixtures/
```

## Tool Categories

### Data & Features
- `features.ohlcv_window` - Historical price data with technical indicators
- `features.market_depth` - Order book and liquidity analysis
- `features.volatility_surface` - Options volatility calculations

### Risk Management
- `risk.position_limits_check` - Validate positions against configured limits
- `risk.correlation_analysis` - Cross-asset correlation calculations
- `risk.var_calculation` - Value-at-Risk estimates

### Execution Simulation
- `execution.sim_quote` - Expected fill price with slippage
- `execution.market_impact` - Market impact cost estimation
- `execution.timing_analysis` - Optimal execution timing

### State Management
- `storage.shared_state.get` - Retrieve shared state by key
- `storage.shared_state.set` - Store shared state with TTL
- `storage.shared_state.list` - List keys by pattern

## Configuration

### Port Assignment
The MCP server runs on **port 8002** to avoid conflicts with other services.

### Environment Variables

| Variable | Sample Value | Description |
|----------|--------------|-------------|
| `SERVICE_NAME` | `at-mcp` | Service identifier for logs/metrics |
| `MCP_SERVER_PORT` | `8002` | MCP server listening port |
| `NATS_URL` | `nats://localhost:4222` | NATS server connection |
| `NATS_STREAM` | `trading-events` | JetStream stream name |
| `NATS_DURABLE` | `mcp-consumer` | Durable consumer name |
| `API_KEY_HMAC_SECRET` | `your-secret-key` | Tool authentication secret |
| `RATE_LIMIT_RPS` | `20` | Tool calls per second limit |
| `IDEMPOTENCY_TTL_SEC` | `3600` | Duplicate detection window |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENV` | `development` | Environment name |

### Server Profiles

**Development (stdio)**:
```bash
MCP_SERVER_MODE=stdio
LOG_LEVEL=DEBUG
```

**Production (HTTP service)**:
```bash
MCP_SERVER_MODE=http
MCP_SERVER_PORT=8003
AUTH_TOKEN=your-secret-token
RATE_LIMIT_RPM=5000
```

## Monitoring and Health

### Key Metrics
- `mcp_tool_calls_total{tool,status}` - Tool invocations by status
- `mcp_tool_duration_seconds{tool}` - Tool execution latency
- `mcp_validation_errors_total{tool,error_type}` - Schema validation failures
- `mcp_rate_limit_hits_total{client}` - Rate limit violations
- `mcp_backend_errors_total{backend}` - External dependency failures

### Health Indicators
- All tools respond within SLO latency targets
- Schema validation success rate > 99%
- External dependency availability > 95%
- Rate limit violation rate < 1%

### Health Check Endpoint
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "server_mode": config.mode,
        "tools_available": len(tool_registry),
        "nats_connected": await nats.is_connected(),
        "redis_connected": await redis.ping(),
        "uptime_seconds": time.time() - start_time
    }
```

## Development Workflow

### Adding New Tool
1. **Define schema**: Add input/output JSON schemas to tool definition
2. **Implement handler**: Create tool function with validation and error handling
3. **Add tests**: Unit tests for happy/error paths and schema compliance
4. **Update catalog**: Document tool in TOOLS_CATALOG.md
5. **Test integration**: Verify tool works via MCP protocol

### Testing Tools
```bash
# Unit tests
pytest servers/features/tests/

# Schema compliance
pytest tests/test_schema_compliance.py

# Integration tests
pytest tests/test_tool_integration.py

# Soak testing
pytest tests/test_soak.py -m soak
```

## Integration with Other Services

### Tool Consumers
- **at-agents**: Use tools for data analysis and decision support
- **at-orchestrator**: Coordinate multi-tool workflows
- **Claude agents**: Direct MCP protocol integration

### External Dependencies
- **at-core**: Schema validation and contract compliance
- **NATS**: Event streaming for real-time data
- **Redis**: Shared state storage with TTL
- **Data APIs**: Market data and reference data sources

### Error Handling
```python
try:
    result = await tool_handler(validated_args)
    return success_response(result)
except ValidationError as e:
    return error_response("MCP-001", f"Invalid arguments: {e}")
except TimeoutError:
    return error_response("MCP-004", "Tool execution timeout")
except ExternalServiceError as e:
    return error_response("MCP-003", f"Backend unavailable: {e}")
except Exception as e:
    logger.error(f"Unexpected error in {tool_name}: {e}")
    return error_response("MCP-999", "Internal server error")
```

## Getting Help

- **Tool catalog**: See [TOOLS_CATALOG.md](TOOLS_CATALOG.md)
- **Implementation guide**: Review [SERVER_TEMPLATE.md](SERVER_TEMPLATE.md)
- **Agent integration**: Check [PROMPTS.md](PROMPTS.md)
- **Security**: Review [SECURITY.md](SECURITY.md)
- **Testing**: Check [TEST_STRATEGY.md](TEST_STRATEGY.md)

### Support Channels
- **Questions**: #trading-mcp Slack channel
- **Bugs**: GitHub Issues with tool name and request/response samples
- **Performance**: #trading-platform-alerts for production issues

---

**Next Steps**: Read [MCP_OVERVIEW.md](MCP_OVERVIEW.md) for protocol details and [TOOLS_CATALOG.md](TOOLS_CATALOG.md) for complete tool documentation.
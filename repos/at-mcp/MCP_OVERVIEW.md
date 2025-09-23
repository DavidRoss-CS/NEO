# MCP Protocol Overview

**Protocol details, design choices, and implementation patterns for trading MCP servers.**

## What is MCP?

Model Context Protocol (MCP) is a standardized protocol that enables Large Language Models to call external tools with well-defined schemas. It provides a bridge between AI agents and external capabilities, allowing agents to:

- Access real-time data and computations
- Perform actions in external systems
- Maintain consistency through schema validation
- Operate with predictable latency and error handling

## Our Design Choices

### Transport Layer

**Local Development: stdio**
```bash
# Direct pipe communication
echo '{"method": "tools/list"}' | python mcp_server.py
```

**Production Services: HTTP**
```bash
# RESTful API endpoints
curl -X POST http://localhost:8003/mcp/tools/call \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{"name": "features.ohlcv_window", "arguments": {...}}'
```

**Why both?**
- **stdio**: Zero network overhead for development and single-process deployments
- **HTTP**: Standard service discovery, load balancing, and observability for production

### Contract Management

**JSON Schema for Request/Response**
```json
{
  "tool": "risk.position_limits_check",
  "input_schema": {
    "type": "object",
    "properties": {
      "strategy": {"type": "string"},
      "instrument": {"type": "string"},
      "qty": {"type": "number"},
      "side": {"type": "string", "enum": ["buy", "sell"]}
    },
    "required": ["strategy", "instrument", "qty", "side"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "allowed": {"type": "boolean"},
      "reason": {"type": "string"},
      "max_qty": {"type": "number"}
    },
    "required": ["allowed"]
  }
}
```

**Semantic Versioning + Dual-Accept Window**
- **MAJOR**: Breaking changes require dual-support period
- **MINOR**: Backward-compatible additions (new optional fields)
- **PATCH**: Bug fixes and clarifications

**Version Evolution Example**:
```python
# v1.0.0 → v1.1.0 (add optional field)
{
  "strategy": "momentum_v2",
  "instrument": "EURUSD",
  "qty": 10000,
  "side": "buy",
  "time_horizon": "intraday"  # New optional field
}

# v1.1.0 → v2.0.0 (breaking change)
{
  "portfolio_id": "port_123",     # strategy → portfolio_id
  "symbol": "EURUSD",            # instrument → symbol
  "quantity": 10000,             # qty → quantity
  "direction": "long"             # side → direction with new enum
}
```

### Observability

**Structured Logging with Correlation IDs**
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "message": "Tool execution completed",
  "corr_id": "req_abc123",
  "tool": "features.ohlcv_window",
  "duration_ms": 87,
  "status": "success",
  "input_size_bytes": 234,
  "output_size_bytes": 1456
}
```

**Prometheus Metrics**
```python
# Tool performance metrics
mcp_tool_duration_seconds = Histogram(
    'mcp_tool_duration_seconds',
    'Tool execution time',
    ['tool', 'status']
)

# Usage patterns
mcp_tool_calls_total = Counter(
    'mcp_tool_calls_total',
    'Total tool invocations',
    ['tool', 'client', 'status']
)

# Error tracking
mcp_errors_total = Counter(
    'mcp_errors_total',
    'Tool errors by type',
    ['tool', 'error_code']
)
```

## Tool Design Principles

### Pure Functions Where Possible

**Preferred: Deterministic transformation**
```python
async def calculate_technical_indicators(ohlcv_data, indicators):
    """Pure function: same input → same output."""
    results = {}
    for indicator in indicators:
        if indicator == "sma_20":
            results[indicator] = calculate_sma(ohlcv_data, 20)
        elif indicator == "rsi_14":
            results[indicator] = calculate_rsi(ohlcv_data, 14)
    return results
```

**When side effects necessary: Clearly documented**
```python
async def store_shared_state(key, value, ttl_sec):
    """Side effect: stores in Redis with TTL.
    
    Idempotency: Same key+value+ttl → same Redis state
    """
    await redis.setex(key, ttl_sec, json.dumps(value))
    return {"stored": True, "expires_at": time.time() + ttl_sec}
```

### Bounded Latency and Timeouts

**Tool-Specific SLOs**
```python
TOOL_SLOS = {
    "features.ohlcv_window": {"p95_ms": 200, "timeout_ms": 500},
    "risk.position_limits_check": {"p95_ms": 50, "timeout_ms": 100},
    "execution.sim_quote": {"p95_ms": 80, "timeout_ms": 200},
    "storage.shared_state.get": {"p95_ms": 20, "timeout_ms": 50},
    "storage.shared_state.set": {"p95_ms": 30, "timeout_ms": 100}
}
```

**Timeout Implementation**
```python
async def execute_tool_with_timeout(tool_name, handler, args):
    timeout = TOOL_SLOS[tool_name]["timeout_ms"] / 1000
    try:
        return await asyncio.wait_for(handler(args), timeout=timeout)
    except asyncio.TimeoutError:
        raise ToolTimeoutError(f"{tool_name} exceeded {timeout}s timeout")
```

### Idempotency

All tool calls must include an idempotency key to prevent duplicate execution. The MCP server maintains a cache of processed keys with a **3600-second (1 hour) TTL**.

**Implementation:**
```python
idempotency_key = f"tool_{tool_name}_{hash(params)}_{timestamp}"
cache_ttl = 3600  # 1 hour
```

**Duplicate Handling:** If a duplicate key is detected within the TTL window, the server returns the cached result without re-executing the tool.

**Deterministic Key Generation**
```python
def generate_idempotency_key(tool_name, args, time_bucket_sec=3600):
    """Generate consistent key for identical operations.

    Time bucketing prevents indefinite caching while maintaining
    idempotency for retry scenarios (1 hour default).
    """
    # Round timestamp to bucket for time-sensitive operations
    bucket_time = int(time.time()) // time_bucket_sec * time_bucket_sec
    
    # Create deterministic hash of tool + args + time bucket
    key_data = {
        "tool": tool_name,
        "args": args,
        "time_bucket": bucket_time
    }
    
    hash_input = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
```

**Idempotency Implementation**
```python
async def call_tool_idempotent(tool_name, args):
    # Generate idempotency key
    idem_key = generate_idempotency_key(tool_name, args)
    cache_key = f"mcp:idem:{idem_key}"
    
    # Check cache first
    cached = await redis.get(cache_key)
    if cached:
        logger.info(f"Tool {tool_name} cache hit for key {idem_key}")
        return json.loads(cached)
    
    # Execute tool
    result = await execute_tool(tool_name, args)

    # Cache result with TTL
    await redis.setex(cache_key, 3600, json.dumps(result))  # 1 hour TTL

    return result
```

### Clear Failure Surface

**Standardized Error Codes**
```python
class MCPError(Exception):
    """Base class for MCP tool errors."""
    def __init__(self, code, message, details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"{code}: {message}")

class ValidationError(MCPError):
    """MCP-001: Invalid input arguments."""
    def __init__(self, message, field=None):
        details = {"field": field} if field else {}
        super().__init__("MCP-001", f"Invalid arguments: {message}", details)

class UnauthorizedError(MCPError):
    """MCP-002: Authentication/authorization failed."""
    def __init__(self, message="Access denied"):
        super().__init__("MCP-002", message)

class BackendUnavailableError(MCPError):
    """MCP-003: External dependency unavailable."""
    def __init__(self, service, message):
        details = {"service": service}
        super().__init__("MCP-003", f"Backend unavailable: {message}", details)

class TimeoutError(MCPError):
    """MCP-004: Tool execution timeout."""
    def __init__(self, tool, timeout_ms):
        details = {"tool": tool, "timeout_ms": timeout_ms}
        super().__init__("MCP-004", f"Tool {tool} timeout after {timeout_ms}ms", details)

class IdempotencyConflictError(MCPError):
    """MCP-005: Idempotency key conflict."""
    def __init__(self, key, message):
        details = {"idempotency_key": key}
        super().__init__("MCP-005", f"Idempotency conflict: {message}", details)
```

## Versioning and Deprecation Policy

### Schema Evolution Strategy

**Following ADR-0002 (Schema Evolution)**:

1. **Propose Change**: RFC with migration plan and compatibility analysis
2. **Dual-Write Period**: Support both old and new versions (minimum 30 days)
3. **Consumer Migration**: Update clients to use new version
4. **Deprecation**: Mark old version as deprecated with sunset date
5. **Cleanup**: Remove deprecated version after grace period

**Example Migration Timeline**:
```
Day 0:   Release v2.0.0 alongside v1.x
Day 1:   Begin dual-support period
Day 30:  Mark v1.x as deprecated
Day 60:  Remove v1.x support
```

### Backward Compatibility Rules

**MINOR version changes (backward compatible)**:
- Add optional fields to input schema
- Add fields to output schema
- Add new enum values (with default handling)
- Relax validation constraints

**MAJOR version changes (breaking)**:
- Remove or rename fields
- Change field types
- Make optional fields required
- Remove enum values
- Change output structure

### Version Negotiation

**Tool Registration with Version Support**
```python
class ToolDefinition:
    def __init__(self, name, versions):
        self.name = name
        self.versions = versions  # ["1.0.0", "1.1.0", "2.0.0"]
        self.latest = max(versions, key=version.parse)
        self.deprecated = []  # ["1.0.0"] if deprecated

@server.list_tools()
async def list_tools():
    return [
        {
            "name": "features.ohlcv_window",
            "versions": ["1.0.0", "1.1.0"],
            "latest": "1.1.0",
            "deprecated": [],
            "description": "Fetch OHLCV data with technical indicators"
        }
    ]
```

**Version-Aware Tool Calls**
```json
{
  "method": "tools/call",
  "params": {
    "name": "features.ohlcv_window",
    "version": "1.1.0",
    "arguments": {
      "symbol": "EURUSD",
      "start": "2024-01-15T09:00:00Z",
      "end": "2024-01-15T10:00:00Z",
      "interval": "1m",
      "features": ["sma", "rsi"]
    }
  }
}
```

## Integration Patterns

### NATS Event Integration

**Tools that consume NATS events**
```python
async def get_live_market_data(symbol, lookback_minutes):
    """Fetch recent market data from NATS stream."""
    # Subscribe to market data stream
    js = nats.jetstream()
    sub = await js.subscribe(
        subject=f"market.data.{symbol}",
        durable="mcp-features-consumer"
    )
    
    # Collect recent messages
    messages = []
    async for msg in sub.messages:
        data = json.loads(msg.data)
        if is_within_lookback(data['timestamp'], lookback_minutes):
            messages.append(data)
        await msg.ack()
    
    return messages
```

**Tools that publish NATS events**
```python
async def trigger_risk_alert(alert_data):
    """Publish risk alert to NATS for downstream processing."""
    # Validate against at-core schema
    validated_alert = validate_schema(
        "risk.alert.v1.json", 
        alert_data
    )
    
    # Publish to NATS
    await nats.publish(
        subject="risk.alerts",
        data=json.dumps(validated_alert).encode()
    )
    
    return {"published": True, "subject": "risk.alerts"}
```

### Redis State Integration

**Shared state with TTL management**
```python
class SharedStateManager:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def get(self, corr_id, key):
        """Get shared state with correlation context."""
        full_key = f"shared:{corr_id}:{key}"
        value = await self.redis.get(full_key)
        
        if value is None:
            return {"exists": False}
        
        return {
            "exists": True,
            "value": json.loads(value),
            "ttl_seconds": await self.redis.ttl(full_key)
        }
    
    async def set(self, corr_id, key, value, ttl_sec):
        """Set shared state with TTL."""
        full_key = f"shared:{corr_id}:{key}"
        await self.redis.setex(
            full_key, 
            ttl_sec, 
            json.dumps(value)
        )
        
        return {"stored": True, "expires_at": time.time() + ttl_sec}
```

## Performance Considerations

### Connection Pooling

**Redis Connection Pool**
```python
import aioredis

redis_pool = aioredis.ConnectionPool.from_url(
    "redis://localhost:6379",
    max_connections=20,
    retry_on_timeout=True
)
redis_client = aioredis.Redis(connection_pool=redis_pool)
```

**NATS Connection with Limits**
```python
nats_client = NATS()
await nats_client.connect(
    servers=["nats://localhost:4222"],
    max_outstanding_msgs=1000,
    max_pending_msgs=10000
)
```

### Caching Strategy

**Multi-level caching**
```python
class CachedTool:
    def __init__(self):
        self.local_cache = {}  # In-memory for < 1s TTL
        self.redis_cache = redis_client  # Redis for < 5min TTL
    
    async def execute(self, args):
        # L1: Local memory cache
        key = self.cache_key(args)
        if key in self.local_cache:
            entry = self.local_cache[key]
            if entry['expires'] > time.time():
                return entry['data']
        
        # L2: Redis cache
        cached = await self.redis_cache.get(f"tool:{key}")
        if cached:
            return json.loads(cached)
        
        # L3: Execute tool
        result = await self.tool_handler(args)
        
        # Store in both caches
        self.local_cache[key] = {
            'data': result,
            'expires': time.time() + 1  # 1s local TTL
        }
        await self.redis_cache.setex(
            f"tool:{key}", 
            60,  # 1min Redis TTL
            json.dumps(result)
        )
        
        return result
```

---

**Next Steps**: See [SERVER_TEMPLATE.md](SERVER_TEMPLATE.md) for implementation patterns and [TOOLS_CATALOG.md](TOOLS_CATALOG.md) for complete tool specifications.
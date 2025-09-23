# MCP Server Template

**Reference skeleton for building MCP servers with standard patterns and best practices.**

## Template Overview

This template provides a language-agnostic outline for implementing MCP servers that expose trading tools to LLM agents. Follow this structure to ensure consistency, observability, and reliability across all MCP servers.

## Configuration

### Environment Variables

```bash
# Server Configuration
PORT=8003
LOG_LEVEL=INFO
SERVICE_NAME=trading-mcp-features
ENVIRONMENT=development

# External Dependencies
NATS_URL=nats://localhost:4222
REDIS_URL=redis://localhost:6379
DATA_API_URL=http://localhost:8001

# Security
AUTH_TOKEN=your-secret-token
RATE_LIMIT_RPM=1000
TIMEOUT_SECONDS=30

# Observability
METRICS_PORT=9090
HEALTH_CHECK_INTERVAL=30
CORRELATION_ID_HEADER=X-Correlation-ID
```

### Configuration Class

```python
from pydantic import BaseSettings
from typing import Optional

class MCPServerConfig(BaseSettings):
    # Server
    port: int = 8003
    log_level: str = "INFO"
    service_name: str = "trading-mcp"
    environment: str = "development"

    # External Dependencies
    nats_url: str = "nats://localhost:4222"
    redis_url: str = "redis://localhost:6379"
    data_api_url: Optional[str] = None

    # Security
    auth_token: Optional[str] = None
    rate_limit_rpm: int = 1000
    timeout_seconds: int = 30

    # Observability
    metrics_port: int = 9090
    health_check_interval: int = 30
    correlation_id_header: str = "X-Correlation-ID"

    class Config:
        env_file = ".env"
        case_sensitive = False
```

## Tool Registry

### Tool Definition

```python
from dataclasses import dataclass
from typing import Dict, Any, List
from jsonschema import Draft202012Validator

@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    slo_ms: int  # p95 latency target
    timeout_ms: int
    idempotent: bool = True
    side_effects: List[str] = None

    def __post_init__(self):
        # Validate schemas on initialization
        Draft202012Validator.check_schema(self.input_schema)
        Draft202012Validator.check_schema(self.output_schema)
        self.side_effects = self.side_effects or []

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.handlers: Dict[str, callable] = {}

    def register_tool(self, definition: ToolDefinition, handler: callable):
        """Register a tool with its handler function."""
        self.tools[definition.name] = definition
        self.handlers[definition.name] = handler

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return MCP-compatible tool list."""
        return [
            {
                "name": name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "outputSchema": tool.output_schema
            }
            for name, tool in self.tools.items()
        ]

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self.tools.get(name)

    def get_handler(self, name: str) -> Optional[callable]:
        return self.handlers.get(name)
```

## Middleware

### Authentication Middleware

```python
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer
import hmac
import hashlib

class AuthMiddleware:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.bearer = HTTPBearer() if config.auth_token else None

    async def verify_request(self, request: Request):
        """Verify request authentication."""
        if not self.config.auth_token:
            return  # No auth required

        if request.url.path in ["/health", "/metrics"]:
            return  # Skip auth for monitoring endpoints

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(401, "Missing or invalid authorization header")

        token = auth_header[7:]  # Remove "Bearer "
        if not hmac.compare_digest(token, self.config.auth_token):
            raise HTTPException(401, "Invalid authentication token")
```

### Correlation ID Middleware

```python
import uuid
from contextvars import ContextVar

# Global context for correlation ID
correlation_id_context: ContextVar[str] = ContextVar('correlation_id')

class CorrelationMiddleware:
    def __init__(self, config: MCPServerConfig):
        self.header_name = config.correlation_id_header

    async def process_request(self, request: Request):
        """Extract or generate correlation ID."""
        corr_id = (
            request.headers.get(self.header_name) or
            f"mcp_{uuid.uuid4().hex[:8]}"
        )
        correlation_id_context.set(corr_id)
        return corr_id

def get_correlation_id() -> str:
    """Get current correlation ID from context."""
    try:
        return correlation_id_context.get()
    except LookupError:
        return f"mcp_{uuid.uuid4().hex[:8]}"
```

### Rate Limiting Middleware

```python
import time
from collections import defaultdict
from typing import Dict

class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """Check if client is within rate limit."""
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > minute_ago
        ]

        # Check limit
        if len(self.requests[client_id]) >= self.rpm:
            return False

        # Record request
        self.requests[client_id].append(now)
        return True

class RateLimitingMiddleware:
    def __init__(self, config: MCPServerConfig):
        self.limiter = RateLimiter(config.rate_limit_rpm)

    async def check_rate_limit(self, request: Request):
        """Enforce rate limiting per client."""
        client_id = self.get_client_id(request)

        if not self.limiter.is_allowed(client_id):
            raise HTTPException(
                429,
                f"Rate limit exceeded: {self.limiter.rpm} requests per minute"
            )

    def get_client_id(self, request: Request) -> str:
        """Extract client identifier for rate limiting."""
        # Try auth token first, then IP
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return f"token_{hashlib.md5(auth_header.encode()).hexdigest()[:8]}"

        return f"ip_{request.client.host}"
```

## Error Model

### Standard Error Response

```python
from pydantic import BaseModel
from typing import Dict, Any, Optional

class MCPErrorResponse(BaseModel):
    error: bool = True
    code: str
    message: str
    corr_id: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str
    tool: Optional[str] = None

class MCPSuccessResponse(BaseModel):
    error: bool = False
    data: Any
    corr_id: str
    timestamp: str
    tool: str
    duration_ms: int

def create_error_response(code: str, message: str, tool: str = None, details: Dict = None) -> MCPErrorResponse:
    """Create standardized error response."""
    return MCPErrorResponse(
        code=code,
        message=message,
        corr_id=get_correlation_id(),
        details=details or {},
        timestamp=datetime.utcnow().isoformat(),
        tool=tool
    )

def create_success_response(data: Any, tool: str, duration_ms: int) -> MCPSuccessResponse:
    """Create standardized success response."""
    return MCPSuccessResponse(
        data=data,
        corr_id=get_correlation_id(),
        timestamp=datetime.utcnow().isoformat(),
        tool=tool,
        duration_ms=duration_ms
    )
```

### Request Validation

**Payload Limits:**
- Maximum request body size: **1MB**
- Maximum parameter string length: 10,000 characters
- Maximum nested object depth: 10 levels

**Port Configuration:**
```python
MCP_SERVER_PORT = int(os.getenv('MCP_SERVER_PORT', '8002'))
app.run(host='0.0.0.0', port=MCP_SERVER_PORT)
```

## Core Server Implementation

### Base MCP Server Class

```python
import asyncio
import time
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, ValidationError
from jsonschema import validate, ValidationError as JSONSchemaError
import logging

class MCPServer:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.app = FastAPI(title=f"{config.service_name} MCP Server")
        self.registry = ToolRegistry()
        self.auth = AuthMiddleware(config)
        self.rate_limiter = RateLimitingMiddleware(config)
        self.correlation = CorrelationMiddleware(config)

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(config.service_name)

        # Setup routes
        self.setup_routes()

    def setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.middleware("http")
        async def middleware_pipeline(request: Request, call_next):
            # Process correlation ID
            corr_id = await self.correlation.process_request(request)

            # Auth check
            try:
                await self.auth.verify_request(request)
            except HTTPException as e:
                return create_error_response(
                    "MCP-002", "Authentication failed"
                )

            # Rate limiting
            try:
                await self.rate_limiter.check_rate_limit(request)
            except HTTPException as e:
                return create_error_response(
                    "MCP-006", "Rate limit exceeded"
                )

            # Process request
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = corr_id
            return response

        @self.app.get("/health")
        async def health_check():
            return await self.get_health_status()

        @self.app.post("/mcp/tools/list")
        async def list_tools():
            return self.registry.list_tools()

        @self.app.post("/mcp/tools/call")
        async def call_tool(request: ToolCallRequest):
            return await self.execute_tool(request.name, request.arguments)

    async def execute_tool(self, tool_name: str, arguments: dict):
        """Execute a tool with validation and error handling."""
        start_time = time.time()

        try:
            # Get tool definition
            tool_def = self.registry.get_tool(tool_name)
            if not tool_def:
                return create_error_response(
                    "MCP-007", f"Unknown tool: {tool_name}"
                )

            # Validate input schema
            try:
                validate(arguments, tool_def.input_schema)
            except JSONSchemaError as e:
                return create_error_response(
                    "MCP-001", f"Invalid arguments: {e.message}",
                    tool=tool_name,
                    details={"schema_error": str(e)}
                )

            # Get handler
            handler = self.registry.get_handler(tool_name)
            if not handler:
                return create_error_response(
                    "MCP-008", f"No handler for tool: {tool_name}"
                )

            # Execute with timeout
            timeout = tool_def.timeout_ms / 1000
            try:
                result = await asyncio.wait_for(
                    handler(arguments),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                return create_error_response(
                    "MCP-004", f"Tool execution timeout ({timeout}s)",
                    tool=tool_name
                )

            # Validate output schema
            try:
                validate(result, tool_def.output_schema)
            except JSONSchemaError as e:
                self.logger.error(f"Tool {tool_name} output schema violation: {e}")
                return create_error_response(
                    "MCP-009", "Tool output schema violation",
                    tool=tool_name
                )

            # Success response
            duration_ms = int((time.time() - start_time) * 1000)
            return create_success_response(result, tool_name, duration_ms)

        except Exception as e:
            self.logger.error(f"Unexpected error in {tool_name}: {e}")
            return create_error_response(
                "MCP-999", "Internal server error",
                tool=tool_name
            )

    async def get_health_status(self):
        """Return server health status."""
        return {
            "status": "healthy",
            "service": self.config.service_name,
            "version": "1.0.0",
            "tools_available": len(self.registry.tools),
            "uptime_seconds": time.time() - self.start_time,
            "dependencies": await self.check_dependencies()
        }

    async def check_dependencies(self) -> dict:
        """Check external dependency health."""
        status = {}

        # Check Redis
        try:
            await self.redis.ping()
            status["redis"] = "healthy"
        except Exception:
            status["redis"] = "unhealthy"

        # Check NATS
        try:
            status["nats"] = "healthy" if self.nats.is_connected else "unhealthy"
        except Exception:
            status["nats"] = "unhealthy"

        return status

    async def start(self):
        """Start the MCP server."""
        self.start_time = time.time()

        # Initialize dependencies
        await self.init_dependencies()

        # Start server
        import uvicorn
        config = uvicorn.Config(
            app=self.app,
            host="0.0.0.0",
            port=self.config.port,
            log_level=self.config.log_level.lower()
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def init_dependencies(self):
        """Initialize external dependencies."""
        # Redis connection
        import aioredis
        self.redis = aioredis.from_url(self.config.redis_url)

        # NATS connection
        from nats.aio.client import Client as NATS
        self.nats = NATS()
        await self.nats.connect(self.config.nats_url)
```

### Tool Implementation Example

```python
# Example: OHLCV Features Tool

async def ohlcv_features_handler(args: dict) -> dict:
    """Fetch OHLCV data and compute technical features.

    Args:
        args: {
            "symbol": "EURUSD",
            "start": "2024-01-15T09:00:00Z",
            "end": "2024-01-15T10:00:00Z",
            "interval": "1m",
            "features": ["sma", "rsi"]
        }

    Returns:
        {
            "symbol": "EURUSD",
            "rows": [...],
            "stats": {...}
        }
    """
    symbol = args["symbol"]
    start = args["start"]
    end = args["end"]
    interval = args["interval"]
    features = args["features"]

    # Fetch OHLCV data (implementation specific)
    ohlcv_data = await fetch_ohlcv_data(symbol, start, end, interval)

    # Compute requested features
    stats = {}
    for feature in features:
        if feature == "sma":
            stats["sma_20"] = calculate_sma(ohlcv_data, 20)
        elif feature == "rsi":
            stats["rsi_14"] = calculate_rsi(ohlcv_data, 14)
        elif feature == "volatility":
            stats["volatility"] = calculate_volatility(ohlcv_data)

    return {
        "symbol": symbol,
        "rows": ohlcv_data,
        "stats": stats
    }

# Register the tool
server.registry.register_tool(
    ToolDefinition(
        name="features.ohlcv_window",
        description="Fetch OHLCV data and compute technical features",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "start": {"type": "string", "format": "date-time"},
                "end": {"type": "string", "format": "date-time"},
                "interval": {"type": "string", "enum": ["1m", "5m", "1h", "1d"]},
                "features": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["symbol", "start", "end", "interval", "features"]
        },
        output_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "rows": {"type": "array"},
                "stats": {"type": "object"}
            },
            "required": ["symbol", "rows", "stats"]
        },
        slo_ms=200,
        timeout_ms=500
    ),
    ohlcv_features_handler
)
```

## Usage Example

### Server Startup

```python
if __name__ == "__main__":
    # Load configuration
    config = MCPServerConfig()

    # Create server
    server = MCPServer(config)

    # Register tools (import from modules)
    from tools.features import register_features_tools
    from tools.risk import register_risk_tools
    from tools.storage import register_storage_tools

    register_features_tools(server)
    register_risk_tools(server)
    register_storage_tools(server)

    # Start server
    asyncio.run(server.start())
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8003 9090

CMD ["python", "server.py"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  mcp-server:
    build: .
    ports:
      - "8003:8003"
      - "9090:9090"
    environment:
      - NATS_URL=nats://nats:4222
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    depends_on:
      - nats
      - redis
    restart: unless-stopped
```

---

**Next Steps**: Use this template to implement specific MCP servers. See [TOOLS_CATALOG.md](TOOLS_CATALOG.md) for detailed tool specifications.
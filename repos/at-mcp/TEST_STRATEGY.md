# Test Strategy

**Comprehensive testing approach for MCP servers and tools.**

## Testing Philosophy

**Contract-First Testing**: All tests validate adherence to JSON schemas and SLO targets defined in TOOLS_CATALOG.md. Testing ensures tools remain reliable, deterministic, and performant under various conditions.

**Test Pyramid Structure**:
```
    /\
   /  \
  /Soak\
 /      \
/__E2E__\
/Contract\
/__Unit__\
```

## Unit Testing

### Tool Handler Testing

**Scope**: Individual tool functions in isolation
**Coverage**: Happy path, error conditions, edge cases
**SLO**: All unit tests complete in <100ms

```python
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from tools.features import ohlcv_features_handler
from shared.errors import MCPError

class TestOHLCVFeaturesHandler:
    @pytest.fixture
    def sample_args(self):
        return {
            "symbol": "EURUSD",
            "start": "2024-01-15T09:00:00Z",
            "end": "2024-01-15T10:00:00Z",
            "interval": "1m",
            "features": ["sma", "rsi"]
        }
    
    @pytest.fixture
    def mock_market_data(self):
        return [
            {
                "timestamp": "2024-01-15T09:00:00Z",
                "open": 1.0940,
                "high": 1.0950,
                "low": 1.0935,
                "close": 1.0945,
                "volume": 12500
            }
        ]
    
    @pytest.mark.asyncio
    async def test_ohlcv_handler_success(self, sample_args, mock_market_data, monkeypatch):
        """Test successful OHLCV data fetch and feature calculation."""
        # Mock external data source
        async def mock_fetch_ohlcv(symbol, start, end, interval):
            return mock_market_data
        
        monkeypatch.setattr("tools.features.fetch_ohlcv_data", mock_fetch_ohlcv)
        
        # Execute handler
        result = await ohlcv_features_handler(sample_args)
        
        # Validate output structure
        assert "symbol" in result
        assert "rows" in result
        assert "stats" in result
        assert "metadata" in result
        
        # Validate content
        assert result["symbol"] == "EURUSD"
        assert len(result["rows"]) == 1
        assert "sma_20" in result["stats"]
        assert "rsi_14" in result["stats"]
    
    @pytest.mark.asyncio
    async def test_ohlcv_handler_invalid_symbol(self, sample_args):
        """Test error handling for invalid symbol."""
        sample_args["symbol"] = "INVALID"
        
        with pytest.raises(MCPError) as exc_info:
            await ohlcv_features_handler(sample_args)
        
        assert exc_info.value.code == "MCP-001"
        assert "invalid symbol" in exc_info.value.message.lower()
    
    @pytest.mark.asyncio
    async def test_ohlcv_handler_data_unavailable(self, sample_args, monkeypatch):
        """Test handling when external data source is unavailable."""
        async def mock_fetch_ohlcv_error(symbol, start, end, interval):
            raise ConnectionError("Market data API unavailable")
        
        monkeypatch.setattr("tools.features.fetch_ohlcv_data", mock_fetch_ohlcv_error)
        
        with pytest.raises(MCPError) as exc_info:
            await ohlcv_features_handler(sample_args)
        
        assert exc_info.value.code == "MCP-003"
    
    @pytest.mark.asyncio
    async def test_ohlcv_handler_insufficient_data(self, sample_args, monkeypatch):
        """Test handling when insufficient data for technical indicators."""
        async def mock_fetch_ohlcv_insufficient(symbol, start, end, interval):
            return []  # No data points
        
        monkeypatch.setattr("tools.features.fetch_ohlcv_data", mock_fetch_ohlcv_insufficient)
        
        with pytest.raises(MCPError) as exc_info:
            await ohlcv_features_handler(sample_args)
        
        assert exc_info.value.code == "MCP-010"
        assert "insufficient data" in exc_info.value.message.lower()
```

### Schema Validation Testing

```python
import pytest
from jsonschema import validate, ValidationError
from tools.registry import ToolRegistry

class TestSchemaValidation:
    @pytest.fixture
    def tool_registry(self):
        registry = ToolRegistry()
        # Load all tool definitions
        from tools.features import register_features_tools
        from tools.risk import register_risk_tools
        register_features_tools(registry)
        register_risk_tools(registry)
        return registry
    
    def test_all_input_schemas_valid(self, tool_registry):
        """Verify all tool input schemas are valid JSON Schema."""
        for tool_name, tool_def in tool_registry.tools.items():
            # This will raise if schema is invalid
            validate({}, tool_def.input_schema)
    
    def test_all_output_schemas_valid(self, tool_registry):
        """Verify all tool output schemas are valid JSON Schema."""
        for tool_name, tool_def in tool_registry.tools.items():
            # This will raise if schema is invalid
            validate({}, tool_def.output_schema)
    
    @pytest.mark.parametrize("tool_name,valid_input", [
        ("features.ohlcv_window", {
            "symbol": "EURUSD",
            "start": "2024-01-15T09:00:00Z",
            "end": "2024-01-15T10:00:00Z",
            "interval": "1m",
            "features": ["sma"]
        }),
        ("risk.position_limits_check", {
            "strategy": "momentum_v2",
            "instrument": "EURUSD",
            "qty": 50000,
            "side": "buy"
        })
    ])
    def test_valid_inputs_pass_validation(self, tool_registry, tool_name, valid_input):
        """Test that valid inputs pass schema validation."""
        tool_def = tool_registry.get_tool(tool_name)
        # Should not raise
        validate(valid_input, tool_def.input_schema)
    
    @pytest.mark.parametrize("tool_name,invalid_input,expected_error", [
        ("features.ohlcv_window", {
            "symbol": "invalid_symbol",  # Wrong format
            "start": "2024-01-15T09:00:00Z",
            "end": "2024-01-15T10:00:00Z",
            "interval": "1m",
            "features": ["sma"]
        }, "pattern"),
        ("risk.position_limits_check", {
            "strategy": "momentum_v2",
            "instrument": "EURUSD",
            "qty": -50000,  # Negative quantity
            "side": "buy"
        }, "exclusiveMinimum")
    ])
    def test_invalid_inputs_fail_validation(self, tool_registry, tool_name, invalid_input, expected_error):
        """Test that invalid inputs fail schema validation."""
        tool_def = tool_registry.get_tool(tool_name)
        with pytest.raises(ValidationError) as exc_info:
            validate(invalid_input, tool_def.input_schema)
        assert expected_error in str(exc_info.value)
```

### Idempotency Testing

```python
class TestIdempotency:
    @pytest.mark.asyncio
    async def test_idempotent_tool_calls(self, mcp_server, sample_request):
        """Test that identical tool calls return identical results."""
        # First call
        result1 = await mcp_server.execute_tool(
            "features.ohlcv_window", 
            sample_request
        )
        
        # Second identical call
        result2 = await mcp_server.execute_tool(
            "features.ohlcv_window", 
            sample_request
        )
        
        # Results should be identical
        assert result1["data"] == result2["data"]
        
        # Second call should be faster (cached)
        assert result2["duration_ms"] <= result1["duration_ms"]
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, mcp_server, sample_request, monkeypatch):
        """Test that cached results expire correctly."""
        # Mock time to control cache expiration
        import time
        original_time = time.time
        current_time = 1000000
        
        def mock_time():
            return current_time
        
        monkeypatch.setattr(time, "time", mock_time)
        
        # First call
        result1 = await mcp_server.execute_tool(
            "features.ohlcv_window", 
            sample_request
        )
        
        # Advance time beyond cache TTL
        current_time += 400  # 400 seconds (> 5min cache)
        
        # Second call should not be cached
        result2 = await mcp_server.execute_tool(
            "features.ohlcv_window", 
            sample_request
        )
        
        # Duration should be similar (both fetched fresh)
        assert abs(result1["duration_ms"] - result2["duration_ms"]) < 50
```

## Contract Testing

### Schema Compatibility Testing

**Scope**: Verify schema evolution maintains backward compatibility
**Coverage**: All schema versions supported
**SLO**: Contract tests complete in <30s

```python
import pytest
import json
from pathlib import Path
from jsonschema import validate

class TestSchemaCompatibility:
    def load_schema_versions(self, tool_name):
        """Load all versions of a tool's schema."""
        schema_dir = Path("schemas") / tool_name
        versions = {}
        
        for schema_file in schema_dir.glob("v*.json"):
            version = schema_file.stem  # e.g., "v1_0_0"
            with open(schema_file) as f:
                versions[version] = json.load(f)
        
        return versions
    
    @pytest.mark.parametrize("tool_name", [
        "features.ohlcv_window",
        "risk.position_limits_check",
        "execution.sim_quote"
    ])
    def test_backward_compatibility(self, tool_name):
        """Test that newer schemas accept older valid inputs."""
        versions = self.load_schema_versions(tool_name)
        
        if len(versions) < 2:
            pytest.skip(f"Only one version available for {tool_name}")
        
        # Get sample data that was valid in v1.0.0
        v1_sample = self.load_sample_data(tool_name, "v1_0_0")
        
        # Should validate against all newer versions
        for version, schema in versions.items():
            if version == "v1_0_0":
                continue
            
            validate(v1_sample, schema["input_schema"])
    
    def test_schema_version_metadata(self):
        """Test that all schemas have proper version metadata."""
        for tool_dir in Path("schemas").iterdir():
            if not tool_dir.is_dir():
                continue
            
            for schema_file in tool_dir.glob("*.json"):
                with open(schema_file) as f:
                    schema = json.load(f)
                
                # Required metadata
                assert "version" in schema
                assert "$id" in schema
                assert "title" in schema
                assert "description" in schema
                
                # Version format validation
                import re
                version_pattern = r'^\d+\.\d+\.\d+$'
                assert re.match(version_pattern, schema["version"])
```

### API Contract Testing

```python
class TestAPIContracts:
    @pytest.mark.asyncio
    async def test_tool_response_format(self, mcp_client):
        """Test that all tools return standard response format."""
        tools = await mcp_client.list_tools()
        
        for tool in tools:
            # Call with minimal valid input
            sample_input = self.generate_minimal_valid_input(tool["name"])
            
            response = await mcp_client.call_tool(
                tool["name"], 
                sample_input
            )
            
            # Standard response format
            if response.get("error"):
                # Error response format
                assert "code" in response
                assert "message" in response
                assert "corr_id" in response
                assert "timestamp" in response
            else:
                # Success response format
                assert "data" in response
                assert "corr_id" in response
                assert "timestamp" in response
                assert "tool" in response
                assert "duration_ms" in response
    
    @pytest.mark.asyncio
    async def test_error_code_consistency(self, mcp_client):
        """Test that error codes are consistent across tools."""
        # Test invalid input scenario
        invalid_input = {"invalid_field": "invalid_value"}
        
        tools = await mcp_client.list_tools()
        for tool in tools:
            response = await mcp_client.call_tool(
                tool["name"], 
                invalid_input
            )
            
            assert response["error"]
            assert response["code"] == "MCP-001"  # Invalid arguments
            assert "invalid arguments" in response["message"].lower()
```

## Integration Testing

### End-to-End Tool Integration

**Scope**: Complete tool workflows with real dependencies
**Coverage**: Happy path and error scenarios
**SLO**: Integration tests complete in <5 minutes

```python
import pytest
import asyncio
from testcontainers import DockerCompose

@pytest.fixture(scope="session")
def infrastructure():
    """Start required infrastructure for integration tests."""
    with DockerCompose(".", compose_file_name="docker-compose.test.yml") as compose:
        # Wait for services to be ready
        nats_url = compose.get_service_host("nats", 4222)
        redis_url = compose.get_service_host("redis", 6379)
        
        # Health check services
        wait_for_service(nats_url)
        wait_for_service(redis_url)
        
        yield {
            "nats_url": f"nats://{nats_url}",
            "redis_url": f"redis://{redis_url}"
        }

class TestToolIntegration:
    @pytest.mark.asyncio
    async def test_complete_analysis_workflow(self, mcp_server, infrastructure):
        """Test complete trading analysis workflow."""
        corr_id = "test_workflow_001"
        symbol = "EURUSD"
        
        # Step 1: Fetch market data
        ohlcv_result = await mcp_server.execute_tool(
            "features.ohlcv_window",
            {
                "symbol": symbol,
                "start": "2024-01-15T09:00:00Z",
                "end": "2024-01-15T10:00:00Z",
                "interval": "1m",
                "features": ["sma", "rsi"]
            }
        )
        
        assert not ohlcv_result["error"]
        market_data = ohlcv_result["data"]
        
        # Step 2: Store analysis state
        analysis = {
            "trend": "bullish" if market_data["stats"]["sma_20"] > market_data["stats"]["sma_50"] else "bearish",
            "strength": market_data["stats"]["rsi_14"] / 100
        }
        
        store_result = await mcp_server.execute_tool(
            "storage.shared_state.set",
            {
                "corr_id": corr_id,
                "key": "analysis.momentum",
                "value": analysis,
                "ttl_seconds": 300
            }
        )
        
        assert not store_result["error"]
        assert store_result["data"]["stored"]
        
        # Step 3: Risk check
        risk_result = await mcp_server.execute_tool(
            "risk.position_limits_check",
            {
                "strategy": "test_strategy",
                "instrument": symbol,
                "qty": 10000,
                "side": "buy"
            }
        )
        
        assert not risk_result["error"]
        
        # Step 4: Execution simulation
        exec_result = await mcp_server.execute_tool(
            "execution.sim_quote",
            {
                "instrument": symbol,
                "side": "buy",
                "qty": 10000,
                "order_type": "market",
                "timestamp": "2024-01-15T10:00:00Z"
            }
        )
        
        assert not exec_result["error"]
        assert "expected_price" in exec_result["data"]
        
        # Step 5: Retrieve stored analysis
        get_result = await mcp_server.execute_tool(
            "storage.shared_state.get",
            {
                "corr_id": corr_id,
                "key": "analysis.momentum"
            }
        )
        
        assert not get_result["error"]
        assert get_result["data"]["exists"]
        assert get_result["data"]["value"] == analysis
    
    @pytest.mark.asyncio
    async def test_tool_error_propagation(self, mcp_server):
        """Test that external service errors are properly handled."""
        # Simulate external service unavailable
        with patch("tools.features.fetch_ohlcv_data") as mock_fetch:
            mock_fetch.side_effect = ConnectionError("API unavailable")
            
            result = await mcp_server.execute_tool(
                "features.ohlcv_window",
                {
                    "symbol": "EURUSD",
                    "start": "2024-01-15T09:00:00Z",
                    "end": "2024-01-15T10:00:00Z",
                    "interval": "1m",
                    "features": ["sma"]
                }
            )
            
            assert result["error"]
            assert result["code"] == "MCP-003"
            assert "backend unavailable" in result["message"].lower()
```

### Performance Testing

```python
class TestPerformance:
    @pytest.mark.asyncio
    async def test_tool_latency_slos(self, mcp_server):
        """Test that all tools meet their latency SLOs."""
        test_cases = [
            ("features.ohlcv_window", sample_ohlcv_args(), 200),  # p95 < 200ms
            ("risk.position_limits_check", sample_risk_args(), 50),  # p95 < 50ms
            ("execution.sim_quote", sample_exec_args(), 80),  # p95 < 80ms
            ("storage.shared_state.get", sample_storage_args(), 20),  # p95 < 20ms
        ]
        
        for tool_name, args, slo_ms in test_cases:
            latencies = []
            
            # Run 20 iterations to get p95
            for _ in range(20):
                start_time = time.time()
                result = await mcp_server.execute_tool(tool_name, args)
                end_time = time.time()
                
                assert not result["error"], f"Tool {tool_name} failed: {result}"
                latencies.append((end_time - start_time) * 1000)
            
            # Calculate p95
            p95_latency = sorted(latencies)[int(0.95 * len(latencies))]
            
            assert p95_latency < slo_ms, (
                f"Tool {tool_name} p95 latency {p95_latency:.1f}ms "
                f"exceeds SLO of {slo_ms}ms"
            )
    
    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, mcp_server):
        """Test tool behavior under concurrent load."""
        # Create 10 concurrent calls
        tasks = []
        for i in range(10):
            task = mcp_server.execute_tool(
                "features.ohlcv_window",
                {
                    "symbol": "EURUSD",
                    "start": "2024-01-15T09:00:00Z",
                    "end": "2024-01-15T10:00:00Z",
                    "interval": "1m",
                    "features": ["sma"]
                }
            )
            tasks.append(task)
        
        # Execute all concurrently
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        for i, result in enumerate(results):
            assert not result["error"], f"Task {i} failed: {result}"
        
        # Results should be consistent (cached)
        first_result = results[0]["data"]
        for result in results[1:]:
            assert result["data"] == first_result
```

## Soak Testing

### Long-Running Stability Tests

**Scope**: Extended operation under realistic load
**Coverage**: Memory leaks, connection stability, cache behavior
**SLO**: 1000 requests/minute for 30 minutes with <1% error rate

```python
@pytest.mark.soak
class TestSoakTesting:
    @pytest.mark.asyncio
    async def test_sustained_load(self, mcp_server):
        """Test server stability under sustained load."""
        duration_minutes = 30
        requests_per_minute = 1000
        max_error_rate = 0.01  # 1%
        
        total_requests = 0
        error_count = 0
        start_time = time.time()
        
        async def make_request():
            nonlocal total_requests, error_count
            
            try:
                result = await mcp_server.execute_tool(
                    "features.ohlcv_window",
                    {
                        "symbol": "EURUSD",
                        "start": "2024-01-15T09:00:00Z",
                        "end": "2024-01-15T10:00:00Z",
                        "interval": "1m",
                        "features": ["sma"]
                    }
                )
                
                total_requests += 1
                
                if result["error"]:
                    error_count += 1
                    
            except Exception as e:
                total_requests += 1
                error_count += 1
                logging.error(f"Request failed: {e}")
        
        # Run for specified duration
        while (time.time() - start_time) < (duration_minutes * 60):
            # Batch of requests
            batch_size = min(10, requests_per_minute // 6)  # 10-second batches
            tasks = [make_request() for _ in range(batch_size)]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Rate limiting
            await asyncio.sleep(10)  # 10-second intervals
        
        # Validate results
        error_rate = error_count / total_requests if total_requests > 0 else 0
        
        assert error_rate < max_error_rate, (
            f"Error rate {error_rate:.2%} exceeds maximum {max_error_rate:.2%}"
        )
        
        assert total_requests > 0, "No requests were made"
        
        logging.info(
            f"Soak test completed: {total_requests} requests, "
            f"{error_count} errors ({error_rate:.2%})"
        )
    
    @pytest.mark.asyncio
    async def test_memory_stability(self, mcp_server):
        """Test for memory leaks during extended operation."""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Run 1000 requests
        for i in range(1000):
            await mcp_server.execute_tool(
                "features.ohlcv_window",
                {
                    "symbol": "EURUSD",
                    "start": "2024-01-15T09:00:00Z",
                    "end": "2024-01-15T10:00:00Z",
                    "interval": "1m",
                    "features": ["sma"]
                }
            )
            
            # Periodic memory check
            if i % 100 == 0:
                gc.collect()  # Force garbage collection
                current_memory = process.memory_info().rss
                memory_growth = current_memory - initial_memory
                
                # Allow some growth, but not excessive
                assert memory_growth < 100 * 1024 * 1024, (
                    f"Memory growth {memory_growth / 1024 / 1024:.1f}MB "
                    f"after {i} requests exceeds 100MB limit"
                )
```

## CI/CD Integration

### Test Configuration

```yaml
# .github/workflows/test.yml
name: MCP Server Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run contract tests
        run: pytest tests/contract/ -v

  integration-tests:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7
        ports:
          - 6379:6379
      nats:
        image: nats:2.9
        ports:
          - 4222:4222
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          REDIS_URL: redis://localhost:6379
          NATS_URL: nats://localhost:4222

  soak-tests:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - name: Run soak tests
        run: pytest tests/soak/ -v -m soak
        timeout-minutes: 45
```

### Quality Gates

```python
# conftest.py
def pytest_configure(config):
    """Configure pytest with quality gates."""
    config.addinivalue_line(
        "markers", "soak: marks tests as soak tests (deselect with '-m "not soak"')"
    )

def pytest_collection_modifyitems(config, items):
    """Apply quality gates to test collection."""
    # Unit test timeout
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.timeout(10))  # 10s max per unit test
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.timeout(300))  # 5min max per integration test

# Quality thresholds
QUALITY_GATES = {
    "code_coverage": 0.80,     # 80% minimum coverage
    "unit_test_time": 100,     # 100ms max per unit test
    "integration_time": 300,   # 5min max for all integration tests
    "soak_error_rate": 0.01,   # 1% max error rate in soak tests
    "performance_regression": 0.20  # 20% max performance regression
}
```

---

**Next Steps**: Implement this testing strategy across all MCP servers. See [SECURITY.md](SECURITY.md) for security testing requirements.
# System Prompts and Usage Templates

**Prompts and templates for reliable MCP tool usage by LLM agents.**

## System Prompt Fragment

### Core Tool Usage Principles

```
You are a trading agent with access to MCP tools for data analysis and decision support. Follow these principles:

**Tool-First Approach**:
- ALWAYS use MCP tools instead of free-form reasoning when tools are available
- Validate all inputs against tool JSON schemas before calling
- Never guess or approximate tool parameters
- Fail closed on schema validation errors

**Correlation ID Propagation**:
- ALWAYS include correlation ID in tool metadata when available
- Use the same correlation ID across related tool calls
- Generate new correlation ID only for new trading workflows

**Error Handling**:
- Check tool response status before using data
- Retry on MCP-003 (backend unavailable) and MCP-004 (timeout) errors
- Do not retry on MCP-001 (invalid args) or MCP-002 (unauthorized)
- Log all errors with correlation ID for debugging

**Rate Limiting**:
- Respect tool rate limits documented in TOOLS_CATALOG.md
- Batch requests when possible to avoid hitting limits
- Implement exponential backoff for rate limit violations

**Idempotency**:
- Attach idempotency_key to tool metadata for all calls
- Use consistent keys for identical operations
- Understand that repeated calls with same key return cached results

**Output Constraints**:
- Never emit actual trade orders - only produce analysis and recommendations
- Always validate tool outputs against expected schemas
- Include confidence scores and reasoning in your analysis
```

## Tool Call Templates

### features.ohlcv_window

**Purpose**: Fetch market data and compute technical indicators

**Template**:
```python
# Fetch EURUSD 1-hour data with technical indicators
result = await call_tool({
    "name": "features.ohlcv_window",
    "arguments": {
        "symbol": "EURUSD",
        "start": "2024-01-15T00:00:00Z",  # ISO 8601 format
        "end": "2024-01-15T23:59:59Z",
        "interval": "1h",                   # 1m, 5m, 15m, 1h, 4h, 1d
        "features": ["sma", "rsi", "volatility"]
    },
    "metadata": {
        "corr_id": "req_abc123",
        "idempotency_key": "ohlcv_EURUSD_20240115_1h_sma_rsi_vol"
    }
})

if result["error"]:
    handle_error(result["code"], result["message"])
else:
    data = result["data"]
    rows = data["rows"]              # OHLCV candlestick data
    stats = data["stats"]            # Technical indicators
    metadata = data["metadata"]      # Data quality info
```

**Common Patterns**:
```python
# Short-term momentum analysis
features = ["sma", "ema", "rsi", "macd"]

# Volatility analysis
features = ["volatility", "bollinger"]

# Volume analysis
features = ["volume_profile"]
```

### risk.position_limits_check

**Purpose**: Validate position against risk limits

**Template**:
```python
# Check if momentum strategy can take 50k EURUSD long position
result = await call_tool({
    "name": "risk.position_limits_check",
    "arguments": {
        "strategy": "momentum_v2",
        "instrument": "EURUSD",
        "qty": 50000,
        "side": "buy",
        "current_positions": {
            "EURUSD": 25000,    # Existing position
            "GBPUSD": -10000
        }
    },
    "metadata": {
        "corr_id": "req_abc123",
        "idempotency_key": "risk_momentum_v2_EURUSD_buy_20240115"
    }
})

if result["error"]:
    handle_error(result["code"], result["message"])
else:
    risk_check = result["data"]
    if risk_check["allowed"]:
        max_qty = risk_check["max_qty"]
        # Proceed with position sizing
    else:
        reason = risk_check["reason"]
        # Log rejection and adjust strategy
```

**Decision Logic**:
```python
# Risk-aware position sizing
if risk_check["allowed"]:
    proposed_qty = min(requested_qty, risk_check["max_qty"])
    utilization = risk_check["risk_metrics"]["position_utilization"]
    
    if utilization > 0.8:
        # High utilization - reduce position
        proposed_qty *= 0.5
    
    return {"action": "trade", "qty": proposed_qty}
else:
    return {"action": "no_trade", "reason": risk_check["reason"]}
```

### execution.sim_quote

**Purpose**: Get execution cost estimates

**Template**:
```python
# Get slippage estimate for market order
result = await call_tool({
    "name": "execution.sim_quote",
    "arguments": {
        "instrument": "EURUSD",
        "side": "buy",
        "qty": 100000,
        "order_type": "market",
        "timestamp": "2024-01-15T10:30:00Z"
    },
    "metadata": {
        "corr_id": "req_abc123",
        "idempotency_key": "sim_EURUSD_buy_100k_market_20240115_1030"
    }
})

if result["error"]:
    handle_error(result["code"], result["message"])
else:
    quote = result["data"]
    expected_price = quote["expected_price"]
    slippage_bps = quote["slippage_bps"]
    fill_probability = quote["execution_estimate"]["fill_probability"]
    
    # Factor execution costs into decision
    if slippage_bps > 2.0:  # More than 2 bps slippage
        # Consider splitting order or using limit order
        pass
```

**Cost Analysis**:
```python
# Total execution cost analysis
market_impact = quote["market_impact"]
total_cost_bps = market_impact["total_cost_bps"]
liquidity_score = quote["market_conditions"]["liquidity_score"]

if total_cost_bps > profit_target_bps * 0.1:  # Cost > 10% of target
    # Execution cost too high - reconsider trade
    return {"action": "monitor", "reason": "execution_cost_too_high"}
```

### storage.shared_state (get/set)

**Purpose**: Manage shared state across agent calls

**Template**:
```python
# Store analysis results for correlation
analysis = {
    "trend_direction": "bullish",
    "strength": 0.78,
    "confidence": 0.85,
    "supporting_indicators": ["sma_crossover", "rsi_oversold"]
}

store_result = await call_tool({
    "name": "storage.shared_state.set",
    "arguments": {
        "corr_id": "req_abc123",
        "key": "analysis.momentum",
        "value": analysis,
        "ttl_seconds": 600  # 10 minutes
    },
    "metadata": {
        "idempotency_key": "store_momentum_analysis_req_abc123"
    }
})

# Later, retrieve stored analysis
get_result = await call_tool({
    "name": "storage.shared_state.get",
    "arguments": {
        "corr_id": "req_abc123",
        "key": "analysis.momentum"
    },
    "metadata": {
        "idempotency_key": "get_momentum_analysis_req_abc123"
    }
})

if get_result["data"]["exists"]:
    stored_analysis = get_result["data"]["value"]
    # Use stored analysis
else:
    # Analysis not found or expired
    pass
```

**State Management Patterns**:
```python
# Cross-agent state sharing
state_keys = {
    "analysis.momentum": "Momentum analysis results",
    "analysis.risk": "Risk assessment results", 
    "analysis.correlation": "Cross-asset correlation analysis",
    "decision.pending": "Pending trading decision",
    "execution.plan": "Execution strategy plan"
}

# State lifecycle management
ttl_by_type = {
    "analysis.*": 600,      # 10 minutes
    "decision.*": 300,      # 5 minutes
    "execution.*": 120      # 2 minutes
}
```

## Workflow Templates

### Complete Trading Signal Analysis

```python
async def analyze_trading_signal(symbol: str, corr_id: str):
    """Complete analysis workflow using multiple MCP tools."""
    
    # Step 1: Fetch market data and technical indicators
    ohlcv_result = await call_tool({
        "name": "features.ohlcv_window",
        "arguments": {
            "symbol": symbol,
            "start": get_lookback_time(hours=24),
            "end": get_current_time(),
            "interval": "1h",
            "features": ["sma", "rsi", "macd", "volatility"]
        },
        "metadata": {"corr_id": corr_id}
    })
    
    if ohlcv_result["error"]:
        return {"error": "data_fetch_failed", "details": ohlcv_result}
    
    # Step 2: Analyze momentum
    stats = ohlcv_result["data"]["stats"]
    momentum_analysis = {
        "trend_direction": "bullish" if stats["sma_20"] > stats["sma_50"] else "bearish",
        "rsi_level": stats["rsi_14"],
        "volatility": stats["volatility"],
        "confidence": calculate_confidence(stats)
    }
    
    # Step 3: Store analysis for correlation with other agents
    await call_tool({
        "name": "storage.shared_state.set",
        "arguments": {
            "corr_id": corr_id,
            "key": "analysis.momentum",
            "value": momentum_analysis,
            "ttl_seconds": 600
        }
    })
    
    # Step 4: Check risk limits for potential position
    if momentum_analysis["confidence"] > 0.7:
        qty = calculate_position_size(momentum_analysis)
        side = "buy" if momentum_analysis["trend_direction"] == "bullish" else "sell"
        
        risk_result = await call_tool({
            "name": "risk.position_limits_check",
            "arguments": {
                "strategy": "momentum_v2",
                "instrument": symbol,
                "qty": qty,
                "side": side
            },
            "metadata": {"corr_id": corr_id}
        })
        
        if risk_result["error"] or not risk_result["data"]["allowed"]:
            return {
                "action": "no_trade",
                "reason": "risk_limits" if not risk_result["error"] else "risk_check_failed"
            }
        
        # Step 5: Get execution cost estimate
        exec_result = await call_tool({
            "name": "execution.sim_quote",
            "arguments": {
                "instrument": symbol,
                "side": side,
                "qty": min(qty, risk_result["data"]["max_qty"]),
                "order_type": "market",
                "timestamp": get_current_time()
            },
            "metadata": {"corr_id": corr_id}
        })
        
        if exec_result["error"]:
            return {"action": "monitor", "reason": "execution_cost_unavailable"}
        
        # Step 6: Make final decision
        slippage = exec_result["data"]["slippage_bps"]
        if slippage > 2.0:  # More than 2bps slippage
            return {"action": "monitor", "reason": "high_execution_cost"}
        
        return {
            "action": "trade",
            "side": side,
            "qty": min(qty, risk_result["data"]["max_qty"]),
            "expected_price": exec_result["data"]["expected_price"],
            "confidence": momentum_analysis["confidence"]
        }
    
    return {"action": "monitor", "reason": "low_confidence"}
```

## Guardrails and Constraints

### Trading Constraints

```
**CRITICAL**: You are a decision support system, not an execution system.

- NEVER emit actual trade orders or execute trades
- ONLY produce analysis, recommendations, and risk assessments
- ALWAYS include confidence scores in your output
- NEVER override risk limits or bypass risk checks
- ALWAYS validate position sizes against available capital
```

### Error Recovery Patterns

```python
# Retry strategy for transient errors
async def call_tool_with_retry(tool_request, max_retries=3):
    for attempt in range(max_retries):
        result = await call_tool(tool_request)
        
        if not result["error"]:
            return result
        
        error_code = result["code"]
        
        # Retry on transient errors
        if error_code in ["MCP-003", "MCP-004", "MCP-006"]:
            wait_time = 2 ** attempt  # Exponential backoff
            await asyncio.sleep(wait_time)
            continue
        
        # Don't retry on permanent errors
        if error_code in ["MCP-001", "MCP-002", "MCP-007"]:
            break
    
    return result  # Return last error

# Graceful degradation
async def get_market_data_with_fallback(symbol, corr_id):
    # Try primary data source
    result = await call_tool_with_retry({
        "name": "features.ohlcv_window",
        "arguments": {"symbol": symbol, ...},
        "metadata": {"corr_id": corr_id}
    })
    
    if not result["error"]:
        return result["data"]
    
    # Fallback to cached data
    cache_result = await call_tool({
        "name": "storage.shared_state.get",
        "arguments": {
            "corr_id": corr_id,
            "key": f"cache.ohlcv.{symbol}"
        }
    })
    
    if cache_result["data"]["exists"]:
        return cache_result["data"]["value"]
    
    # No data available
    raise DataUnavailableError(f"No market data for {symbol}")
```

### Input Validation

```python
# Always validate inputs before tool calls
def validate_symbol(symbol: str) -> bool:
    """Validate trading symbol format."""
    import re
    pattern = r'^[A-Z]{3,6}(/[A-Z]{3,6})?$'
    return bool(re.match(pattern, symbol))

def validate_datetime(dt_str: str) -> bool:
    """Validate ISO 8601 datetime format."""
    try:
        from datetime import datetime
        datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False

# Example usage
if not validate_symbol(symbol):
    raise ValueError(f"Invalid symbol format: {symbol}")

if not validate_datetime(start_time):
    raise ValueError(f"Invalid datetime format: {start_time}")
```

---

**Next Steps**: Use these prompts and templates to build reliable agent tool usage. See [TEST_STRATEGY.md](TEST_STRATEGY.md) for testing tool integration.
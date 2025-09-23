# Tools Catalog

**Complete documentation of MCP tools with precise input/output schemas, SLOs, and implementation details.**

## Tool Categories

- **[Data & Features](#data--features)**: Market data and technical analysis
- **[Risk Management](#risk-management)**: Position limits and risk validation
- **[Execution Simulation](#execution-simulation)**: Trade simulation and cost estimation
- **[State Management](#state-management)**: Shared state storage and retrieval

---

## Data & Features

### features.ohlcv_window

**Purpose**: Fetch OHLCV historical data and compute technical features for analysis.

**Input JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "symbol": {
      "type": "string",
      "pattern": "^[A-Z]{3,6}(/[A-Z]{3,6})?$",
      "description": "Trading symbol (EURUSD, BTC/USD, SPY)"
    },
    "start": {
      "type": "string",
      "format": "date-time",
      "description": "Start time for data window (ISO 8601)"
    },
    "end": {
      "type": "string",
      "format": "date-time",
      "description": "End time for data window (ISO 8601)"
    },
    "interval": {
      "type": "string",
      "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
      "description": "Candlestick interval"
    },
    "features": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["sma", "ema", "rsi", "macd", "bollinger", "volatility", "volume_profile"]
      },
      "minItems": 1,
      "maxItems": 10,
      "description": "Technical features to calculate"
    }
  },
  "required": ["symbol", "start", "end", "interval", "features"]
}
```

**Output JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "symbol": {"type": "string"},
    "interval": {"type": "string"},
    "rows": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "timestamp": {"type": "string", "format": "date-time"},
          "open": {"type": "number"},
          "high": {"type": "number"},
          "low": {"type": "number"},
          "close": {"type": "number"},
          "volume": {"type": "number"}
        },
        "required": ["timestamp", "open", "high", "low", "close", "volume"]
      }
    },
    "stats": {
      "type": "object",
      "properties": {
        "sma_20": {"type": "number"},
        "sma_50": {"type": "number"},
        "ema_12": {"type": "number"},
        "ema_26": {"type": "number"},
        "rsi_14": {"type": "number", "minimum": 0, "maximum": 100},
        "macd_line": {"type": "number"},
        "macd_signal": {"type": "number"},
        "macd_histogram": {"type": "number"},
        "bollinger_upper": {"type": "number"},
        "bollinger_middle": {"type": "number"},
        "bollinger_lower": {"type": "number"},
        "volatility": {"type": "number", "minimum": 0},
        "volume_vwap": {"type": "number"}
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "total_rows": {"type": "integer"},
        "first_timestamp": {"type": "string", "format": "date-time"},
        "last_timestamp": {"type": "string", "format": "date-time"},
        "data_completeness": {"type": "number", "minimum": 0, "maximum": 1}
      }
    }
  },
  "required": ["symbol", "interval", "rows", "stats", "metadata"]
}
```

**Performance**:
- **Latency SLO**: p95 < 200ms
- **Timeout**: 500ms
- **Rate Limit**: 100 requests/minute per client

**Idempotency Key**: `hash(symbol|start|end|interval|features)`

**Side Effects**: None (read-only)

**Dependencies**:
- Market data API (HTTP)
- Redis cache for frequently requested windows

**Failure Modes**:
- `MCP-001`: Invalid symbol format or unsupported interval
- `MCP-003`: Market data API unavailable
- `MCP-004`: Timeout fetching large data windows
- `MCP-010`: Insufficient data for technical indicator calculation

**Example Usage**:
```bash
curl -X POST http://localhost:8003/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "features.ohlcv_window",
    "arguments": {
      "symbol": "EURUSD",
      "start": "2024-01-15T09:00:00Z",
      "end": "2024-01-15T10:00:00Z",
      "interval": "1m",
      "features": ["sma", "rsi", "volatility"]
    }
  }'
```

---

## Risk Management

### risk.position_limits_check

**Purpose**: Validate trading intent against configured position limits and risk rules.

**Input JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "strategy": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]+$",
      "maxLength": 50,
      "description": "Strategy identifier"
    },
    "instrument": {
      "type": "string",
      "pattern": "^[A-Z]{3,6}(/[A-Z]{3,6})?$",
      "description": "Trading instrument"
    },
    "qty": {
      "type": "number",
      "exclusiveMinimum": 0,
      "description": "Requested position size (positive number)"
    },
    "side": {
      "type": "string",
      "enum": ["buy", "sell", "long", "short"],
      "description": "Position direction"
    },
    "current_positions": {
      "type": "object",
      "additionalProperties": {
        "type": "number"
      },
      "description": "Current positions by instrument"
    }
  },
  "required": ["strategy", "instrument", "qty", "side"]
}
```

**Output JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "allowed": {
      "type": "boolean",
      "description": "Whether the position is allowed"
    },
    "reason": {
      "type": "string",
      "description": "Explanation for decision"
    },
    "max_qty": {
      "type": "number",
      "minimum": 0,
      "description": "Maximum allowed quantity"
    },
    "risk_metrics": {
      "type": "object",
      "properties": {
        "position_utilization": {"type": "number", "minimum": 0, "maximum": 1},
        "instrument_concentration": {"type": "number", "minimum": 0, "maximum": 1},
        "strategy_exposure": {"type": "number"},
        "var_impact": {"type": "number"}
      }
    },
    "limits_applied": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "rule_name": {"type": "string"},
          "limit_type": {"type": "string"},
          "threshold": {"type": "number"},
          "current_value": {"type": "number"},
          "violated": {"type": "boolean"}
        }
      }
    }
  },
  "required": ["allowed", "reason", "max_qty", "risk_metrics", "limits_applied"]
}
```

**Performance**:
- **Latency SLO**: p95 < 50ms
- **Timeout**: 100ms
- **Rate Limit**: 500 requests/minute per client

**Idempotency Key**: `hash(strategy|instrument|side|timestamp_bucket_1m)`

**Side Effects**: May log risk violations for audit

**Dependencies**:
- Risk configuration database (Redis)
- Position tracking system (NATS)

**Failure Modes**:
- `MCP-001`: Invalid strategy or instrument format
- `MCP-003`: Risk configuration service unavailable
- `MCP-011`: Risk limits not configured for strategy

**Example Usage**:
```bash
curl -X POST http://localhost:8003/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "risk.position_limits_check",
    "arguments": {
      "strategy": "momentum_v2",
      "instrument": "EURUSD",
      "qty": 50000,
      "side": "buy",
      "current_positions": {
        "EURUSD": 25000,
        "GBPUSD": -10000
      }
    }
  }'
```

---

## Execution Simulation

### execution.sim_quote

**Purpose**: Provide expected fill price and slippage estimates for trading decisions.

**Input JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "instrument": {
      "type": "string",
      "pattern": "^[A-Z]{3,6}(/[A-Z]{3,6})?$",
      "description": "Trading instrument"
    },
    "side": {
      "type": "string",
      "enum": ["buy", "sell"],
      "description": "Order side"
    },
    "qty": {
      "type": "number",
      "exclusiveMinimum": 0,
      "description": "Order quantity"
    },
    "order_type": {
      "type": "string",
      "enum": ["market", "limit", "stop"],
      "default": "market",
      "description": "Order type for simulation"
    },
    "limit_price": {
      "type": "number",
      "description": "Limit price (required for limit orders)"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Simulation timestamp"
    }
  },
  "required": ["instrument", "side", "qty", "timestamp"]
}
```

**Output JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "expected_price": {
      "type": "number",
      "description": "Expected average fill price"
    },
    "slippage_bps": {
      "type": "number",
      "description": "Expected slippage in basis points"
    },
    "market_impact": {
      "type": "object",
      "properties": {
        "permanent_bps": {"type": "number"},
        "temporary_bps": {"type": "number"},
        "total_cost_bps": {"type": "number"}
      }
    },
    "execution_estimate": {
      "type": "object",
      "properties": {
        "fill_probability": {"type": "number", "minimum": 0, "maximum": 1},
        "expected_fill_time_ms": {"type": "number"},
        "partial_fill_risk": {"type": "number", "minimum": 0, "maximum": 1}
      }
    },
    "market_conditions": {
      "type": "object",
      "properties": {
        "bid_price": {"type": "number"},
        "ask_price": {"type": "number"},
        "spread_bps": {"type": "number"},
        "liquidity_score": {"type": "number", "minimum": 0, "maximum": 1},
        "volatility_regime": {"type": "string", "enum": ["low", "normal", "high", "extreme"]}
      }
    }
  },
  "required": ["expected_price", "slippage_bps", "market_impact", "execution_estimate", "market_conditions"]
}
```

**Performance**:
- **Latency SLO**: p95 < 80ms
- **Timeout**: 200ms
- **Rate Limit**: 200 requests/minute per client

**Idempotency Key**: `hash(instrument|side|qty|order_type|timestamp_bucket_1m)`

**Side Effects**: None (simulation only)

**Dependencies**:
- Market data feed (NATS)
- Liquidity model cache (Redis)
- Historical execution data

**Failure Modes**:
- `MCP-001`: Invalid instrument or quantity
- `MCP-003`: Market data unavailable
- `MCP-012`: Insufficient liquidity for simulation

**Example Usage**:
```bash
curl -X POST http://localhost:8003/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "execution.sim_quote",
    "arguments": {
      "instrument": "EURUSD",
      "side": "buy",
      "qty": 100000,
      "order_type": "market",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }'
```

---

## State Management

### storage.shared_state.get

**Purpose**: Retrieve shared state data by correlation ID and key.

**Input JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "corr_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]+$",
      "maxLength": 128,
      "description": "Correlation ID for state scope"
    },
    "key": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9._-]+$",
      "maxLength": 256,
      "description": "State key within correlation scope"
    }
  },
  "required": ["corr_id", "key"]
}
```

**Output JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "exists": {
      "type": "boolean",
      "description": "Whether the key exists"
    },
    "value": {
      "description": "Stored value (any valid JSON)"
    },
    "metadata": {
      "type": "object",
      "properties": {
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
        "ttl_seconds": {"type": "integer", "minimum": -1},
        "access_count": {"type": "integer", "minimum": 0}
      }
    }
  },
  "required": ["exists"]
}
```

**Performance**:
- **Latency SLO**: p95 < 20ms
- **Timeout**: 50ms
- **Rate Limit**: 1000 requests/minute per client

**Idempotency Key**: `hash(corr_id|key)`

**Side Effects**: Increments access counter

**Dependencies**:
- Redis cluster for state storage

**Failure Modes**:
- `MCP-001`: Invalid correlation ID or key format
- `MCP-003`: Redis unavailable
- `MCP-013`: State key not found (returns exists: false)

### storage.shared_state.set

**Purpose**: Store shared state data with TTL.

**Input JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "corr_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]+$",
      "maxLength": 128,
      "description": "Correlation ID for state scope"
    },
    "key": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9._-]+$",
      "maxLength": 256,
      "description": "State key within correlation scope"
    },
    "value": {
      "description": "Value to store (any valid JSON, max 1MB)"
    },
    "ttl_seconds": {
      "type": "integer",
      "minimum": 1,
      "maximum": 86400,
      "default": 300,
      "description": "Time-to-live in seconds (max 24 hours)"
    }
  },
  "required": ["corr_id", "key", "value"]
}
```

**Output JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "stored": {
      "type": "boolean",
      "description": "Whether the value was stored successfully"
    },
    "expires_at": {
      "type": "string",
      "format": "date-time",
      "description": "When the stored value will expire"
    },
    "size_bytes": {
      "type": "integer",
      "description": "Size of stored value in bytes"
    }
  },
  "required": ["stored", "expires_at", "size_bytes"]
}
```

**Performance**:
- **Latency SLO**: p95 < 30ms
- **Timeout**: 100ms
- **Rate Limit**: 500 requests/minute per client

**Idempotency Key**: `hash(corr_id|key|value_hash)`

**Side Effects**: Stores/overwrites data in Redis

**Dependencies**:
- Redis cluster for state storage

**Failure Modes**:
- `MCP-001`: Invalid input or value too large (>1MB)
- `MCP-003`: Redis unavailable
- `MCP-014`: Storage quota exceeded

**Example Usage**:
```bash
# Store state
curl -X POST http://localhost:8003/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "storage.shared_state.set",
    "arguments": {
      "corr_id": "req_abc123",
      "key": "analysis.momentum",
      "value": {
        "trend_direction": "bullish",
        "strength": 0.78,
        "confidence": 0.85
      },
      "ttl_seconds": 600
    }
  }'

# Retrieve state
curl -X POST http://localhost:8003/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "storage.shared_state.get",
    "arguments": {
      "corr_id": "req_abc123",
      "key": "analysis.momentum"
    }
  }'
```

---

## Error Code Reference

| Code | Name | Description | Retry |
|------|------|-------------|-------|
| `MCP-001` | `invalid-args` | Invalid input arguments or schema violation | No |
| `MCP-002` | `unauthorized` | Authentication or authorization failed | No |
| `MCP-003` | `backend-unavailable` | External dependency unavailable | Yes |
| `MCP-004` | `timeout` | Tool execution timeout | Yes |
| `MCP-005` | `idempotency-conflict` | Idempotency key conflict | No |
| `MCP-006` | `rate-limit-exceeded` | Rate limit violation | Yes (after delay) |
| `MCP-007` | `unknown-tool` | Tool not found in registry | No |
| `MCP-008` | `no-handler` | Tool handler not implemented | No |
| `MCP-009` | `output-schema-violation` | Tool output doesn't match schema | No |
| `MCP-010` | `insufficient-data` | Not enough data for calculation | Yes |
| `MCP-011` | `missing-configuration` | Required configuration not found | No |
| `MCP-012` | `insufficient-liquidity` | Market liquidity too low for simulation | No |
| `MCP-013` | `key-not-found` | State key doesn't exist | No |
| `MCP-014` | `storage-quota-exceeded` | Storage limit reached | No |
| `MCP-999` | `internal-error` | Unexpected server error | Yes |

---

## Performance Summary

| Tool | p95 SLO | Timeout | Rate Limit (req/min) | Cacheable |
|------|---------|---------|---------------------|----------|
| `features.ohlcv_window` | 200ms | 500ms | 100 | Yes (5min TTL) |
| `risk.position_limits_check` | 50ms | 100ms | 500 | Yes (1min TTL) |
| `execution.sim_quote` | 80ms | 200ms | 200 | Yes (1min TTL) |
| `storage.shared_state.get` | 20ms | 50ms | 1000 | No |
| `storage.shared_state.set` | 30ms | 100ms | 500 | No |

---

**Next Steps**: Use these tools in agent implementations. See [PROMPTS.md](PROMPTS.md) for system prompts and usage templates.
# Agents Overview

**Catalog of available trading agents and their interoperability.**

## Agent Architecture

The agentic trading system operates as a distributed network of specialized micro-agents. Each agent consumes normalized market signals and produces enriched analysis for downstream orchestration. Agents run independently and can be scaled, deployed, and versioned separately while maintaining contract compatibility.

## Current Agent Catalog

### Production Agents

| Agent | Purpose | Input | Output | Status |
|-------|---------|-------|--------|--------|
| **momentum** | Detect price momentum and trend strength | `signals.normalized` | `signals.enriched.momentum` | ✅ Active |
| **risk** | Monitor position risk and exposure limits | `signals.normalized` | `signals.enriched.risk` | ✅ Active |

### Future Agents (Roadmap)

| Agent | Purpose | Input | Output | Priority |
|-------|---------|-------|--------|----------|
| **correlation** | Cross-asset correlation analysis | `signals.normalized` | `signals.enriched.correlation` | High |
| **liquidity** | Liquidity sweep and orderbook analysis | `signals.normalized` | `signals.enriched.liquidity` | High |
| **sentiment** | News and social sentiment analysis | `signals.normalized`, `external.news` | `signals.enriched.sentiment` | Medium |
| **volatility** | Volatility forecasting and regime detection | `signals.normalized` | `signals.enriched.volatility` | Medium |
| **arbitrage** | Cross-market arbitrage opportunity detection | `signals.normalized` | `signals.enriched.arbitrage` | Low |
| **orchestrator** | Multi-agent strategy coordination | `signals.enriched.*` | `decisions.order_intent` | Low |

## Agent Interoperability

### Signal Flow Pattern

```
┌───────────────────────┐
│    signals.normalized     │
│  (from at-gateway)       │
└───────────┬───────────┘
             │
    ┌────────┴────────┐
    │ Fan-out to agents │
    └────────┬────────┘
             │
   ┌─────────┼─────────┐
   │         │         │
   │         │         │
┌─┴──┐  ┌─┴──┐  ┌─┴──┐
│Momentum│  │Risk│  │Corr│
│ Agent  │  │Agent│  │Agent│
└─┬──┘  └─┬──┘  └─┬──┘
   │         │         │
   │         │         │
   └────┬────┘         │
        │              │
        │              │
  ┌─────┴──────────────┘
  │ signals.enriched.*     │
  │ (to orchestrator)      │
  └─────────────────────┘
```

### Communication Patterns

**1. Fan-out Pattern**: Single normalized signal distributed to multiple agents
```
signals.normalized → [momentum, risk, correlation] agents
```

**2. Enrichment Chain**: Sequential enrichment (future)
```
signals.normalized → sentiment → momentum → orchestrator
```

**3. Aggregation Pattern**: Multiple enriched signals combined
```
[momentum, risk, volatility] → orchestrator → decisions.order_intent
```

## Agent Versioning Strategy

### Independent Versioning
Each agent maintains its own semantic version:
- **momentum-agent**: v1.2.1
- **risk-agent**: v2.0.0
- **correlation-agent**: v1.0.0-beta

### Contract Compatibility
All agents must comply with at-core schema versions:
- **Input**: `signals.normalized.v1.x.x` (backwards compatible)
- **Output**: Agent-specific enriched schemas

### Version Tags in Events
```json
{
  "schema_version": "1.0.0",
  "agent_name": "momentum",
  "agent_version": "1.2.1",
  "corr_id": "req_abc123",
  "analysis": {
    "momentum_strength": 0.75
  }
}
```

### Deployment Strategy
- **Rolling updates**: Deploy new agent versions without downtime
- **Blue-green**: Switch traffic between agent versions
- **Canary releases**: Route subset of traffic to new versions
- **Feature flags**: Enable/disable agent features dynamically

## Agent Specifications

### Momentum Agent

**Purpose**: Detect price momentum conditions and trend strength

**Algorithm**: 
- Moving average crossover detection
- RSI trend confirmation
- Volume-weighted momentum scoring

**Input Schema**: `signals.normalized`
```json
{
  "corr_id": "req_123",
  "instrument": "EURUSD", 
  "price": 1.0945,
  "side": "buy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Output Schema**: `signals.enriched.momentum`
```json
{
  "schema_version": "1.0.0",
  "agent_name": "momentum",
  "agent_version": "1.2.1",
  "corr_id": "req_123",
  "source_signal": { "instrument": "EURUSD", "price": 1.0945 },
  "enriched_at": "2024-01-15T10:30:01Z",
  "analysis": {
    "momentum_strength": 0.75,
    "trend_direction": "bullish",
    "confidence": 0.82,
    "ma_signal": "golden_cross",
    "rsi_value": 68.5,
    "volume_confirmation": true
  }
}
```

**Configuration**:
- `MOMENTUM_LOOKBACK_PERIODS`: Historical periods for MA calculation (default: 20)
- `MOMENTUM_RSI_THRESHOLD`: RSI overbought/oversold levels (default: 70/30)
- `MOMENTUM_MIN_CONFIDENCE`: Minimum confidence for signal emission (default: 0.6)

### Risk Agent

**Purpose**: Monitor position risk and exposure limits

**Algorithm**:
- Position size validation
- Correlation-based exposure limits
- Drawdown monitoring
- Volatility-adjusted position sizing

**Input Schema**: `signals.normalized`

**Output Schema**: `signals.enriched.risk`
```json
{
  "schema_version": "1.0.0",
  "agent_name": "risk",
  "agent_version": "2.0.0",
  "corr_id": "req_123",
  "source_signal": { "instrument": "EURUSD", "price": 1.0945 },
  "enriched_at": "2024-01-15T10:30:01Z",
  "analysis": {
    "risk_level": "medium",
    "max_position_size": 10000,
    "current_exposure": 0.15,
    "correlation_risk": 0.45,
    "volatility_adjusted_size": 8500,
    "alerts": [
      {
        "type": "exposure_warning",
        "severity": "medium",
        "message": "EUR exposure approaching 20% limit"
      }
    ]
  }
}
```

**Configuration**:
- `RISK_MAX_POSITION_PCT`: Maximum position size as % of capital (default: 5%)
- `RISK_MAX_CORRELATION`: Maximum correlation between positions (default: 0.7)
- `RISK_VOLATILITY_WINDOW`: Lookback for volatility calculation (default: 30 days)
- `RISK_ALERT_THRESHOLDS`: Risk level thresholds for alerts

## Agent Coordination

### Event Ordering
NATS JetStream ensures message ordering per subject:
- Agents process signals in the order they were published
- Correlation IDs enable end-to-end tracing
- Idempotency keys prevent duplicate processing

### State Management
Agents are designed to be stateless, but may maintain:
- **Short-term cache**: Recent signals for moving averages (TTL: 1 hour)
- **Configuration state**: Updated via environment variables
- **No persistent state**: Avoids data consistency issues

### Error Isolation
Agent failures don't impact other agents:
- Independent NATS consumers
- Circuit breakers for downstream dependencies
- Graceful degradation with default responses

### Monitoring Integration
All agents report standardized metrics:
- `agent_messages_processed_total{agent, subject}`
- `agent_processing_duration_seconds{agent}`
- `agent_errors_total{agent, error_type}`
- `agent_consumer_lag{agent, subject}`

## Development Workflow

### Adding New Agents

1. **Design Phase**:
   - Define agent purpose and algorithm
   - Specify input/output schemas
   - Plan configuration parameters

2. **Implementation**:
   - Use [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md) as starting point
   - Implement agent-specific logic in `_process_signal()`
   - Add comprehensive tests

3. **Testing**:
   - Unit tests for processing logic
   - Contract tests against at-core schemas
   - Integration tests with NATS
   - Load tests for performance validation

4. **Documentation**:
   - Agent-specific README.md
   - Update this overview document
   - Add monitoring runbooks

5. **Deployment**:
   - Deploy to staging environment
   - Validate with real signals
   - Gradual rollout to production

### Agent Lifecycle Management

**Development** → **Testing** → **Staging** → **Production** → **Retirement**

- **Development**: Local testing with sample data
- **Testing**: Automated CI/CD pipeline validation
- **Staging**: End-to-end testing with production-like data
- **Production**: Gradual rollout with monitoring
- **Retirement**: Graceful shutdown and data migration

## Performance Characteristics

### Throughput Targets
- **Per-agent**: 1,000 messages/second sustained
- **System-wide**: 10,000+ messages/second aggregate
- **Latency**: p95 < 100ms processing time
- **Availability**: 99.9% uptime per agent

### Resource Requirements
- **Memory**: 128MB baseline + 2MB per 1K cached signals
- **CPU**: 0.1 cores baseline + scaling with message volume
- **Network**: Minimal (NATS compression enabled)
- **Storage**: Stateless (no persistent storage required)

### Scaling Strategies
- **Horizontal**: Multiple instances with durable consumers
- **Vertical**: Increase resources for single instance
- **Load balancing**: NATS handles distribution automatically
- **Circuit breakers**: Protect against downstream failures

---

**For detailed agent implementations, see individual agent README files in the `agents/` directory.**
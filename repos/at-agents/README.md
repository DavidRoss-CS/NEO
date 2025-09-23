# Agentic Trading - Agent Hub

**Autonomous trading agents for strategy execution and market analysis.**

## Purpose

The `at-agents` repository hosts specialized micro-agents that subscribe to NATS events, analyze market conditions, and produce higher-order trading signals. Each agent operates independently, applying specific strategies or risk management logic while communicating through standardized event contracts.

## Responsibilities

✅ **What we do**:
- Subscribe to normalized market signals via NATS
- Apply agent-specific analysis and strategy logic
- Emit enriched signals for downstream orchestration
- Maintain agent state and configuration
- Provide observability hooks for monitoring

❌ **What we don't do**:
- Execute trades directly (that's at-exec-sim)
- Store persistent market data
- Handle authentication or rate limiting
- Mutate or modify raw input events

## Data Flow

```
at-gateway receives webhook
     ↓
Validates and normalizes signal
     ↓
NATS: signals.normalized
     ↓
at-agents (parallel processing):
├── momentum agent → signals.enriched.momentum
├── risk agent → signals.enriched.risk
├── correlation agent → signals.enriched.correlation
└── [future agents]
     ↓
NATS: signals.enriched.*
     ↓
Downstream orchestration (at-exec-sim)
```

**Key principle**: Agents are stateless event processors that can be scaled independently.

## Quick Start

### Install Dependencies
```bash
pip install asyncio-nats-client pydantic pytest httpx
```

### Run Sample Agent
```python
import asyncio
import json
from nats.aio.client import Client as NATS
from jsonschema import validate

async def momentum_handler(msg):
    """Simple momentum detection agent."""
    try:
        # Parse and validate signal
        signal = json.loads(msg.data.decode())
        
        # Apply momentum logic
        if signal['price'] > 100:  # Simple threshold
            enriched = {
                'corr_id': signal['corr_id'],
                'source_signal': signal,
                'momentum_strength': 0.75,
                'recommendation': 'strong_buy',
                'timestamp': '2024-01-15T10:30:00Z'
            }
            
            # Publish enriched signal
            await nats.publish('signals.enriched.momentum', 
                             json.dumps(enriched).encode())
        
        await msg.ack()
    except Exception as e:
        print(f"Error processing signal: {e}")
        await msg.nak()

# Connect and subscribe
nats = NATS()
await nats.connect('nats://localhost:4222')
js = nats.jetstream()

await js.subscribe('signals.normalized', cb=momentum_handler, 
                   durable='momentum-agent')
```

## Repository Layout

```
at-agents/
├── README.md                    # This file
├── AGENT_TEMPLATE.md            # Standard agent skeleton
├── AGENTS_OVERVIEW.md           # Agent catalog and interop
├── TEST_STRATEGY.md             # Testing approach
├── agents/                      # Individual agent implementations
│   ├── momentum/
│   │   ├── README.md           # Momentum agent docs
│   │   ├── agent.py            # Implementation
│   │   ├── config.py           # Configuration
│   │   └── tests/              # Agent-specific tests
│   ├── risk/
│   │   ├── README.md           # Risk agent docs
│   │   ├── agent.py            # Implementation
│   │   ├── config.py           # Configuration
│   │   └── tests/              # Agent-specific tests
│   └── [future agents]
├── shared/                      # Common utilities
│   ├── base_agent.py           # Base agent class
│   ├── metrics.py              # Prometheus metrics
│   └── validation.py           # Schema validation helpers
└── tests/                       # Integration tests
    ├── test_agent_integration.py
    └── fixtures/
```

## Agent Development Patterns

### Standard Agent Lifecycle
1. **Connect** to NATS with durable consumer
2. **Subscribe** to relevant signal subjects
3. **Validate** incoming messages against at-core schemas
4. **Process** signals with agent-specific logic
5. **Emit** enriched events to downstream subjects
6. **Acknowledge** or negatively acknowledge messages

## Environment Variables

| Variable | Sample Value | Description |
|----------|--------------|-------------|
| `SERVICE_NAME` | `at-agent-momentum` | Service identifier for logs/metrics |
| `NATS_URL` | `nats://localhost:4222` | NATS server connection |
| `NATS_STREAM` | `trading-events` | JetStream stream name |
| `NATS_DURABLE` | `agent-consumer` | Durable consumer name |
| `RATE_LIMIT_RPS` | `10` | Message processing rate limit |
| `REPLAY_WINDOW_SEC` | `300` | Event replay tolerance |
| `IDEMPOTENCY_TTL_SEC` | `3600` | Duplicate detection window |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENV` | `development` | Environment name |

### Configuration Management
```python
# All agents use environment variables
NATS_URL = os.getenv('NATS_URL', 'nats://localhost:4222')
NATS_STREAM = os.getenv('NATS_STREAM', 'trading-events')
AGENT_NAME = os.getenv('SERVICE_NAME', 'at-agent-momentum')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
```

### Error Handling
```python
try:
    # Process signal
    result = await process_signal(signal)
    await publish_result(result)
    await msg.ack()
except ValidationError as e:
    logger.error(f"Schema validation failed: {e}", 
                extra={'corr_id': signal.get('corr_id')})
    await msg.ack()  # Don't retry validation errors
except Exception as e:
    logger.error(f"Processing failed: {e}", 
                extra={'corr_id': signal.get('corr_id')})
    await msg.nak()  # Retry processing errors
```

## Monitoring and Observability

### Key Metrics
- `agent_messages_processed_total{agent, subject}` - Messages consumed
- `agent_messages_published_total{agent, target_subject}` - Messages produced
- `agent_processing_duration_seconds{agent}` - Processing latency
- `agent_errors_total{agent, error_type}` - Error counts
- `agent_consumer_lag{agent, subject}` - NATS consumer lag

### Health Indicators
- Agent connects to NATS successfully
- Consumer lag < 10 messages under normal load
- Error rate < 1% over 5-minute window
- Processing latency p95 < 100ms

### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# Log with correlation ID
logger.info("Processing signal", 
           corr_id=signal['corr_id'],
           agent='momentum',
           instrument=signal['instrument'],
           price=signal['price'])
```

## Agent Development Workflow

### Creating a New Agent
1. **Copy template**: Use [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md) as starting point
2. **Define schema**: Add enriched event schema to at-core
3. **Implement logic**: Write agent-specific processing in `agents/[name]/agent.py`
4. **Add tests**: Unit, contract, and integration tests
5. **Update catalog**: Add agent to [AGENTS_OVERVIEW.md](AGENTS_OVERVIEW.md)
6. **Add monitoring**: Define agent-specific metrics and alerts

### Testing New Agents
```bash
# Unit tests for agent logic
pytest agents/momentum/tests/test_momentum_logic.py

# Contract tests against at-core schemas
pytest tests/test_contract_compliance.py

# Integration test with NATS
pytest tests/test_agent_integration.py

# Soak test under load
pytest tests/test_soak.py -m soak
```

## Deployment

### Local Development
```bash
# Start NATS
docker compose -f docker-compose.dev.yml up -d nats

# Run individual agent
cd agents/momentum
python agent.py

# Or run all agents
python -m agents.momentum.agent &
python -m agents.risk.agent &
```

### Production Deployment
- Each agent runs as separate service/container
- Auto-scaling based on consumer lag metrics
- Circuit breakers for downstream failures
- Graceful shutdown on SIGTERM

## Integration with at-core

### Schema Validation
```python
import json
from jsonschema import validate

# Load schema from at-core
with open('../at-core/schemas/signals.normalized.schema.json') as f:
    normalized_schema = json.load(f)

# Validate incoming signal
validate(instance=signal, schema=normalized_schema)
```

### Event Publishing
```python
# Publish enriched signal with version tag
enriched_signal = {
    'schema_version': '1.0.0',
    'agent_name': 'momentum',
    'agent_version': '1.2.1',
    'corr_id': original_signal['corr_id'],
    'source_timestamp': original_signal['timestamp'],
    'enriched_at': datetime.utcnow().isoformat(),
    'analysis': {
        'momentum_strength': 0.75,
        'recommendation': 'strong_buy',
        'confidence': 0.82
    }
}

await nats.publish('signals.enriched.momentum', 
                  json.dumps(enriched_signal).encode())
```

## Getting Help

- **Agent development**: See [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md) for implementation guide
- **Testing**: Review [TEST_STRATEGY.md](TEST_STRATEGY.md) for testing patterns
- **Schema questions**: Check at-core schemas and validation examples
- **NATS issues**: Verify connection and stream configuration
- **Performance problems**: Monitor consumer lag and processing metrics

### Support Channels
- **Questions**: #trading-agents Slack channel
- **Bugs**: GitHub Issues with agent name and correlation IDs
- **Performance**: #trading-platform-alerts for production issues

---

**Next Steps**: 
1. Read [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md) for agent development guide
2. Review [AGENTS_OVERVIEW.md](AGENTS_OVERVIEW.md) for available agents
3. See [agents/momentum/README.md](agents/momentum/README.md) for example implementation
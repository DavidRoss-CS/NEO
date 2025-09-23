# Agentic Trading - Orchestrator

**Meta-agent layer for coordinating specialized agents and managing shared state.**

## Purpose

The `at-orchestrator` repository contains the meta-agent layer that coordinates the network of specialized trading agents, manages shared memory and state, and orchestrates complex multi-agent workflows. It serves as the central coordination hub that aggregates agent outputs and routes them to appropriate execution adapters.

## Responsibilities

✅ **What we do**:
- Subscribe to enriched signals from all agent types
- Coordinate multi-agent workflows and decision flows
- Manage shared state and cross-agent memory
- Aggregate and merge agent outputs by correlation ID
- Route coordinated signals to execution layer
- Maintain health dashboards and orchestration metrics
- Provide conditional triggering and workflow management

❌ **What we don't do**:
- Ingest raw external data (that's at-gateway's responsibility)
- Define core schemas or contracts (that's at-core's responsibility)
- Execute actual trades (that's at-exec-sim's responsibility)
- Implement agent-specific logic (that's individual agents' responsibility)
- Mutate or modify agent outputs (only aggregate and route)

## Data Flow

```
at-gateway receives webhook
     ↓
Validates and normalizes signal
     ↓
NATS: signals.normalized
     ↓
at-agents (parallel processing):
├── momentum → signals.enriched.momentum
├── risk → signals.enriched.risk
└── correlation → signals.enriched.correlation
     ↓
NATS: signals.enriched.*
     ↓
at-orchestrator:
├── Aggregates by correlation ID
├── Applies workflow rules
├── Manages shared state
└── Routes to execution
     ↓
NATS: orchestrated.decision
     ↓
at-exec-sim (trade execution)
```

**Key principle**: Orchestrator acts as intelligent middleware that coordinates agent outputs without modifying their analysis.

## Quick Start

### Prerequisites
```bash
# Required infrastructure
docker compose up -d nats redis

# Verify services
curl http://localhost:8222/healthz  # NATS
redis-cli ping                      # Redis
```

### Install Dependencies
```bash
pip install asyncio-nats-client redis pydantic fastapi uvicorn
```

### Run Sample Orchestrator
```python
import asyncio
import json
import redis
from nats.aio.client import Client as NATS
from datetime import datetime

class SimpleOrchestrator:
    def __init__(self):
        self.nats = None
        self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self.correlation_cache = {}  # In-memory for quick access
    
    async def start(self):
        # Connect to NATS
        self.nats = NATS()
        await self.nats.connect('nats://localhost:4222')
        js = self.nats.jetstream()
        
        # Subscribe to enriched signals
        await js.subscribe(
            'signals.enriched.*',
            cb=self.handle_enriched_signal,
            durable='orchestrator-consumer'
        )
        
        print("Orchestrator started, waiting for enriched signals...")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
    
    async def handle_enriched_signal(self, msg):
        try:
            signal = json.loads(msg.data.decode())
            corr_id = signal['corr_id']
            agent_name = signal['agent_name']
            
            print(f"Received {agent_name} signal for {corr_id}")
            
            # Store in shared state
            await self.store_agent_output(corr_id, agent_name, signal)
            
            # Check if we have enough signals to make decision
            if await self.can_make_decision(corr_id):
                await self.orchestrate_decision(corr_id)
            
            await msg.ack()
            
        except Exception as e:
            print(f"Error processing signal: {e}")
            await msg.nak()
    
    async def store_agent_output(self, corr_id, agent_name, signal):
        """Store agent output in shared state."""
        key = f"orchestrator:signals:{corr_id}"
        
        # Store in Redis with TTL
        self.redis.hset(key, agent_name, json.dumps(signal))
        self.redis.expire(key, 300)  # 5 minute TTL
        
        # Update correlation cache
        if corr_id not in self.correlation_cache:
            self.correlation_cache[corr_id] = {}
        self.correlation_cache[corr_id][agent_name] = signal
    
    async def can_make_decision(self, corr_id):
        """Check if we have sufficient agent signals to proceed."""
        signals = self.correlation_cache.get(corr_id, {})
        
        # Simple rule: need both momentum and risk analysis
        required_agents = ['momentum', 'risk']
        return all(agent in signals for agent in required_agents)
    
    async def orchestrate_decision(self, corr_id):
        """Aggregate agent signals and emit orchestrated decision."""
        signals = self.correlation_cache[corr_id]
        
        # Extract key information
        momentum = signals['momentum']['analysis']
        risk = signals['risk']['analysis']
        
        # Simple orchestration logic
        decision = {
            'corr_id': corr_id,
            'orchestrator_version': '1.0.0',
            'orchestrated_at': datetime.utcnow().isoformat(),
            'source_signals': {
                'momentum': momentum['momentum_strength'],
                'risk': risk['risk_level']
            },
            'decision': self.make_trading_decision(momentum, risk),
            'confidence': self.calculate_confidence(momentum, risk)
        }
        
        # Publish orchestrated decision
        await self.nats.publish(
            'orchestrated.decision',
            json.dumps(decision).encode()
        )
        
        print(f"Published decision for {corr_id}: {decision['decision']['action']}")
        
        # Cleanup
        del self.correlation_cache[corr_id]
    
    def make_trading_decision(self, momentum, risk):
        """Simple decision logic combining momentum and risk."""
        if risk['risk_level'] == 'blocked':
            return {'action': 'no_trade', 'reason': 'risk_blocked'}
        
        if momentum['confidence'] > 0.7 and risk['risk_level'] in ['low', 'medium']:
            return {
                'action': 'trade',
                'direction': momentum['trend_direction'],
                'size': risk['position_sizing']['recommended_size'],
                'reason': 'high_confidence_momentum'
            }
        
        return {'action': 'monitor', 'reason': 'insufficient_confidence'}
    
    def calculate_confidence(self, momentum, risk):
        """Calculate overall decision confidence."""
        momentum_conf = momentum['confidence']
        
        # Risk penalty
        risk_multiplier = {
            'low': 1.0,
            'medium': 0.8,
            'high': 0.5,
            'blocked': 0.0
        }.get(risk['risk_level'], 0.5)
        
        return momentum_conf * risk_multiplier

# Run orchestrator
if __name__ == '__main__':
    orchestrator = SimpleOrchestrator()
    asyncio.run(orchestrator.start())
```

## Repository Layout

```
at-orchestrator/
├── README.md                    # This file
├── ORCHESTRATION_MODEL.md       # Orchestration patterns and flows
├── STATE_MANAGEMENT.md          # Shared state and memory management
├── TEST_STRATEGY.md             # Testing approach and strategies
├── META_AGENT_TEMPLATE.md       # Template for building meta-agents
├── orchestrators/               # Orchestrator implementations
│   ├── simple/
│   │   ├── orchestrator.py     # Simple aggregation logic
│   │   ├── config.py           # Configuration management
│   │   └── tests/              # Unit tests
│   ├── workflow/
│   │   ├── orchestrator.py     # Complex workflow orchestration
│   │   ├── rules.py            # Workflow rules engine
│   │   └── tests/              # Unit tests
│   └── ml/
│       ├── orchestrator.py     # ML-based coordination
│       ├── models.py           # ML models for decision making
│       └── tests/              # Unit tests
├── shared/                      # Common utilities
│   ├── state_manager.py        # State management utilities
│   ├── correlation_tracker.py  # Correlation ID tracking
│   ├── workflow_engine.py      # Workflow execution engine
│   └── metrics.py              # Prometheus metrics
└── tests/                       # Integration tests
    ├── test_orchestration_flow.py
    ├── test_state_management.py
    └── fixtures/
```

## Orchestration Patterns

### Fan-In Aggregation
**Pattern**: Multiple agents contribute to single decision
```python
# Wait for momentum + risk + correlation signals
signals = await collect_signals(corr_id, ['momentum', 'risk', 'correlation'])
decision = aggregate_analysis(signals)
await publish_decision(decision)
```

### Fan-Out Broadcasting
**Pattern**: Single orchestrated decision triggers multiple workflows
```python
# Broadcast decision to multiple execution channels
decision = create_decision(signals)
await broadcast_to_channels(['execution', 'risk_monitor', 'audit'], decision)
```

### Conditional Routing
**Pattern**: Route based on signal content and rules
```python
# Route based on instrument type and risk level
if signal['instrument'].startswith('CRYPTO') and risk_level == 'high':
    await route_to_specialized_handler(signal)
else:
    await route_to_standard_handler(signal)
```

## State Management

### Shared Memory Architecture
```python
# Redis-based shared state
state_manager = StateManager(redis_url='redis://localhost:6379')

# Store agent output
await state_manager.store(
    key=f"signals:{corr_id}:momentum",
    value=momentum_signal,
    ttl=300  # 5 minutes
)

# Retrieve aggregated signals
signals = await state_manager.get_all_for_correlation(corr_id)
```

### State Synchronization
```python
# Ensure consistency across orchestrator instances
async with state_manager.lock(f"orchestration:{corr_id}"):
    signals = await state_manager.get_signals(corr_id)
    if can_orchestrate(signals):
        decision = orchestrate(signals)
        await publish_decision(decision)
        await state_manager.mark_orchestrated(corr_id)
```

## Environment Variables

| Variable | Sample Value | Description |
|----------|--------------|-------------|
| `SERVICE_NAME` | `at-orchestrator` | Service identifier for logs/metrics |
| `NATS_URL` | `nats://localhost:4222` | NATS server connection |
| `NATS_STREAM` | `trading-events` | JetStream stream name |
| `NATS_DURABLE` | `orchestrator-consumer` | Durable consumer name |
| `RATE_LIMIT_RPS` | `50` | Decision processing rate limit |
| `IDEMPOTENCY_TTL_SEC` | `3600` | Duplicate detection window |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENV` | `development` | Environment name |

### Configuration Profiles

**Simple Orchestration**:
```bash
ORCHESTRATOR_TYPE=simple
MIN_AGENTS_REQUIRED=2
DECISION_TIMEOUT_SEC=60
```

**Complex Workflow**:
```bash
ORCHESTRATOR_TYPE=workflow
ENABLE_WORKFLOW_ENGINE=true
MIN_AGENTS_REQUIRED=3
DECISION_TIMEOUT_SEC=300
```

**High Frequency**:
```bash
ORCHESTRATOR_TYPE=simple
MIN_AGENTS_REQUIRED=1
DECISION_TIMEOUT_SEC=10
STATE_TTL_SECONDS=60
```

## Monitoring and Health

### Key Metrics
- `orchestrator_signals_received_total{agent}` - Signals received by agent type
- `orchestrator_decisions_made_total{type}` - Decisions made by type
- `orchestrator_correlation_timeout_total` - Timed out correlations
- `orchestrator_state_operations_total{operation}` - State operations
- `orchestrator_decision_latency_seconds` - Time from first signal to decision

### Health Indicators
- NATS connection healthy
- Redis connection healthy
- Average decision latency < 5 seconds
- Correlation timeout rate < 5%
- State storage success rate > 99%

### Health Check Endpoint
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "orchestrator_type": config.orchestrator_type,
        "nats_connected": nats.is_connected,
        "redis_connected": await redis.ping(),
        "active_correlations": len(correlation_cache),
        "uptime_seconds": time.time() - start_time
    }
```

## Development Workflow

### Creating New Orchestrator
1. **Copy template**: Use [META_AGENT_TEMPLATE.md](META_AGENT_TEMPLATE.md)
2. **Define workflow**: Specify agent requirements and decision logic
3. **Implement routing**: Add conditional routing rules
4. **Add state management**: Define shared state requirements
5. **Test integration**: Unit and integration tests
6. **Add monitoring**: Orchestrator-specific metrics

### Testing Orchestrator
```bash
# Unit tests
pytest orchestrators/simple/tests/

# Integration tests with NATS + Redis
pytest tests/test_orchestration_flow.py

# Load testing
pytest tests/test_soak.py -m soak
```

## Deployment

### Local Development
```bash
# Start infrastructure
docker compose up -d nats redis

# Run orchestrator
cd orchestrators/simple
python orchestrator.py
```

### Production Deployment
```yaml
# Docker Compose
version: '3.8'
services:
  orchestrator:
    image: trading/orchestrator:1.0.0
    environment:
      - NATS_URL=nats://nats-cluster:4222
      - REDIS_URL=redis://redis-cluster:6379
      - ORCHESTRATOR_TYPE=workflow
    depends_on:
      - nats
      - redis
    restart: unless-stopped
```

### Scaling Considerations
- Multiple orchestrator instances with Redis locking
- Partition by correlation ID for horizontal scaling
- Circuit breakers for Redis failures
- Graceful degradation when state unavailable

## Integration with Other Services

### Upstream Dependencies
- **at-agents**: Consumes enriched signals
- **NATS**: Message broker for event streaming
- **Redis**: Shared state and coordination

### Downstream Consumers
- **at-exec-sim**: Receives orchestrated decisions
- **at-observability**: Monitoring and alerting

### Error Handling
```python
try:
    signals = await collect_signals(corr_id, timeout=60)
    decision = orchestrate(signals)
    await publish_decision(decision)
except TimeoutError:
    # Handle incomplete signal collection
    await handle_partial_decision(corr_id)
except RedisConnectionError:
    # Graceful degradation without state
    await handle_stateless_orchestration(corr_id)
except Exception as e:
    # Log and alert on unexpected errors
    await alert_orchestration_failure(corr_id, e)
```

## Getting Help

- **Orchestration patterns**: See [ORCHESTRATION_MODEL.md](ORCHESTRATION_MODEL.md)
- **State management**: Review [STATE_MANAGEMENT.md](STATE_MANAGEMENT.md)
- **Testing**: Check [TEST_STRATEGY.md](TEST_STRATEGY.md)
- **Implementation**: Use [META_AGENT_TEMPLATE.md](META_AGENT_TEMPLATE.md)

### Support Channels
- **Questions**: #trading-orchestration Slack channel
- **Bugs**: GitHub Issues with correlation IDs and state dumps
- **Performance**: #trading-platform-alerts for production issues

---

**Next Steps**: Read [ORCHESTRATION_MODEL.md](ORCHESTRATION_MODEL.md) for orchestration patterns and [STATE_MANAGEMENT.md](STATE_MANAGEMENT.md) for state management details.
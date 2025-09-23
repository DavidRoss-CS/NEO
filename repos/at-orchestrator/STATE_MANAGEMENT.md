# State Management

**Shared memory and state coordination for multi-agent orchestration.**

## Overview

State management in the orchestrator provides coordinated memory that enables agents to share context, maintain workflow state, and ensure consistent decision-making across the distributed system. The state management layer supports both ephemeral (fast, in-memory) and durable (persistent, auditable) storage patterns.

## State Requirements

### Ephemeral State (In-Memory)

**Purpose**: Fast access scratchpad for active orchestration workflows.

**Characteristics**:
- **Storage**: In-memory dictionaries and caches
- **TTL**: < 5 minutes (typical workflow duration)
- **Scope**: Single orchestrator instance
- **Performance**: Sub-millisecond access
- **Persistence**: Not persisted across restarts

**Use Cases**:
- Active correlation tracking
- Temporary signal aggregation
- Workflow state transitions
- Performance counters

```python
class EphemeralStateManager:
    def __init__(self):
        self.correlation_cache = {}  # corr_id -> signals
        self.workflow_state = {}     # corr_id -> workflow_step
        self.performance_counters = defaultdict(int)
        self.ttl_tracker = {}        # corr_id -> expiry_time
    
    async def store_signal(self, corr_id, agent_name, signal):
        """Store agent signal in memory."""
        if corr_id not in self.correlation_cache:
            self.correlation_cache[corr_id] = {}
            self.ttl_tracker[corr_id] = time.time() + 300  # 5 min TTL
        
        self.correlation_cache[corr_id][agent_name] = signal
        self.performance_counters['signals_stored'] += 1
    
    async def get_signals(self, corr_id):
        """Retrieve all signals for correlation ID."""
        # Check TTL
        if corr_id in self.ttl_tracker:
            if time.time() > self.ttl_tracker[corr_id]:
                await self.cleanup_correlation(corr_id)
                return {}
        
        return self.correlation_cache.get(corr_id, {})
    
    async def cleanup_correlation(self, corr_id):
        """Remove expired correlation data."""
        self.correlation_cache.pop(corr_id, None)
        self.workflow_state.pop(corr_id, None)
        self.ttl_tracker.pop(corr_id, None)
        self.performance_counters['correlations_cleaned'] += 1
```

### Durable State (Redis/Database)

**Purpose**: Persistent storage for audit trails, cross-instance coordination, and recovery.

**Characteristics**:
- **Storage**: Redis or PostgreSQL
- **TTL**: Hours to days (configurable)
- **Scope**: Cross-instance shared state
- **Performance**: Millisecond access
- **Persistence**: Survives restarts and failures

**Use Cases**:
- Audit trails and compliance logs
- Cross-instance coordination
- Workflow recovery after failures
- Historical analysis and debugging

```python
class DurableStateManager:
    def __init__(self, redis_url):
        self.redis = redis.asyncio.from_url(redis_url, decode_responses=True)
        self.default_ttl = 86400  # 24 hours
    
    async def store_correlation_state(self, corr_id, state_data, ttl=None):
        """Store correlation state durably."""
        key = f"orchestrator:correlation:{corr_id}"
        ttl = ttl or self.default_ttl
        
        async with self.redis.pipeline() as pipe:
            pipe.hset(key, mapping={
                'state': json.dumps(state_data),
                'created_at': datetime.utcnow().isoformat(),
                'last_updated': datetime.utcnow().isoformat()
            })
            pipe.expire(key, ttl)
            await pipe.execute()
    
    async def get_correlation_state(self, corr_id):
        """Retrieve correlation state."""
        key = f"orchestrator:correlation:{corr_id}"
        state_data = await self.redis.hgetall(key)
        
        if not state_data:
            return None
        
        return {
            'state': json.loads(state_data['state']),
            'created_at': state_data['created_at'],
            'last_updated': state_data['last_updated']
        }
    
    async def lock_correlation(self, corr_id, timeout=30):
        """Distributed lock for correlation processing."""
        lock_key = f"orchestrator:lock:{corr_id}"
        
        # Try to acquire lock
        acquired = await self.redis.set(
            lock_key, 
            f"orchestrator:{os.getpid()}",
            nx=True,  # Only set if not exists
            ex=timeout  # Expire after timeout
        )
        
        return acquired
    
    async def release_lock(self, corr_id):
        """Release distributed lock."""
        lock_key = f"orchestrator:lock:{corr_id}"
        await self.redis.delete(lock_key)
```

## Shared Memory Contract

### Data Structure Standards

**All shared state follows standardized JSON schemas**:

```python
CORRELATION_STATE_SCHEMA = {
    "type": "object",
    "required": ["corr_id", "status", "signals", "metadata"],
    "properties": {
        "corr_id": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["collecting", "ready", "orchestrating", "completed", "failed"]
        },
        "signals": {
            "type": "object",
            "patternProperties": {
                "^[a-z_]+$": {  # agent names
                    "type": "object",
                    "required": ["agent_name", "corr_id", "enriched_at"],
                    "properties": {
                        "agent_name": {"type": "string"},
                        "agent_version": {"type": "string"},
                        "corr_id": {"type": "string"},
                        "enriched_at": {"type": "string", "format": "date-time"},
                        "analysis": {"type": "object"}
                    }
                }
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "created_at": {"type": "string", "format": "date-time"},
                "last_updated": {"type": "string", "format": "date-time"},
                "expected_agents": {"type": "array", "items": {"type": "string"}},
                "timeout_at": {"type": "string", "format": "date-time"},
                "orchestration_pattern": {"type": "string"}
            }
        }
    }
}
```

### Access Patterns

**Read Pattern**: Agents can read shared context but not modify orchestration state

```python
class AgentStateReader:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def read_correlation_context(self, corr_id):
        """Agents can read correlation context for enhanced analysis."""
        key = f"orchestrator:context:{corr_id}"
        context = await self.redis.hgetall(key)
        
        return {
            'instrument_history': json.loads(context.get('instrument_history', '{}')),
            'recent_decisions': json.loads(context.get('recent_decisions', '[]')),
            'market_regime': context.get('market_regime'),
            'portfolio_state': json.loads(context.get('portfolio_state', '{}'))
        }
    
    async def read_agent_signals(self, corr_id):
        """Read signals from other agents (for correlation analysis)."""
        key = f"orchestrator:signals:{corr_id}"
        signals = await self.redis.hgetall(key)
        
        parsed_signals = {}
        for agent_name, signal_json in signals.items():
            parsed_signals[agent_name] = json.loads(signal_json)
        
        return parsed_signals
```

**Write Pattern**: Only orchestrators can modify correlation state

```python
class OrchestratorStateWriter:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def update_correlation_state(self, corr_id, updates):
        """Update correlation state with locking."""
        async with self.distributed_lock(corr_id):
            key = f"orchestrator:correlation:{corr_id}"
            
            # Get current state
            current_state = await self.redis.hgetall(key)
            if current_state:
                state_data = json.loads(current_state['state'])
            else:
                state_data = self._create_initial_state(corr_id)
            
            # Apply updates
            state_data.update(updates)
            state_data['metadata']['last_updated'] = datetime.utcnow().isoformat()
            
            # Store updated state
            await self.redis.hset(key, 'state', json.dumps(state_data))
            await self.redis.hset(key, 'last_updated', state_data['metadata']['last_updated'])
    
    @asynccontextmanager
    async def distributed_lock(self, corr_id, timeout=30):
        """Distributed lock context manager."""
        lock_key = f"orchestrator:lock:{corr_id}"
        lock_value = f"orchestrator:{os.getpid()}:{time.time()}"
        
        # Acquire lock
        acquired = await self.redis.set(lock_key, lock_value, nx=True, ex=timeout)
        if not acquired:
            raise LockAcquisitionError(f"Could not acquire lock for {corr_id}")
        
        try:
            yield
        finally:
            # Release lock (only if we still own it)
            current_value = await self.redis.get(lock_key)
            if current_value == lock_value:
                await self.redis.delete(lock_key)
```

## TTL Policies

### Ephemeral TTL Management

**Automatic cleanup based on workflow lifecycle**:

```python
class TTLManager:
    def __init__(self):
        self.ttl_policies = {
            'active_correlation': 300,      # 5 minutes
            'failed_correlation': 600,      # 10 minutes (for debugging)
            'completed_correlation': 60,    # 1 minute (quick cleanup)
            'workflow_state': 180,          # 3 minutes
            'performance_counters': 3600    # 1 hour
        }
    
    async def apply_ttl_policy(self, state_type, key, data):
        """Apply appropriate TTL based on state type."""
        ttl = self.ttl_policies.get(state_type, 300)
        
        if isinstance(data, dict):
            data['ttl_expires_at'] = time.time() + ttl
        
        # Set Redis TTL if using durable storage
        if hasattr(self, 'redis'):
            await self.redis.expire(key, ttl)
        
        return ttl
    
    async def cleanup_expired_state(self):
        """Periodic cleanup of expired ephemeral state."""
        current_time = time.time()
        expired_keys = []
        
        # Check ephemeral state for expired entries
        for key, data in self.ephemeral_state.items():
            if isinstance(data, dict) and 'ttl_expires_at' in data:
                if current_time > data['ttl_expires_at']:
                    expired_keys.append(key)
        
        # Remove expired entries
        for key in expired_keys:
            del self.ephemeral_state[key]
            logger.debug(f"Cleaned up expired state: {key}")
        
        return len(expired_keys)
```

### Durable TTL Configuration

**Redis TTL policies for different data types**:

```python
DURABLE_TTL_POLICIES = {
    'correlation_state': {
        'default': 86400,       # 24 hours
        'completed': 3600,      # 1 hour for completed
        'failed': 604800        # 7 days for failed (debugging)
    },
    'audit_logs': {
        'default': 2592000,     # 30 days
        'compliance': 31536000  # 1 year for compliance
    },
    'performance_metrics': {
        'default': 604800,      # 7 days
        'aggregated': 2592000   # 30 days for aggregated metrics
    },
    'locks': {
        'default': 60,          # 1 minute
        'long_running': 300     # 5 minutes for complex operations
    }
}

class DurableTTLManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.policies = DURABLE_TTL_POLICIES
    
    async def set_with_policy(self, key, value, data_type, state=None):
        """Set data with appropriate TTL policy."""
        policy = self.policies.get(data_type, {})
        ttl = policy.get(state, policy.get('default', 3600))
        
        await self.redis.setex(key, ttl, value)
        
        logger.debug(
            "Set durable state with TTL",
            key=key,
            data_type=data_type,
            state=state,
            ttl_seconds=ttl
        )
    
    async def extend_ttl(self, key, data_type, new_state=None):
        """Extend TTL when state changes."""
        policy = self.policies.get(data_type, {})
        ttl = policy.get(new_state, policy.get('default', 3600))
        
        await self.redis.expire(key, ttl)
        
        logger.debug(
            "Extended TTL",
            key=key,
            new_ttl_seconds=ttl,
            new_state=new_state
        )
```

## State Schema Versioning

### Schema Evolution

**State schemas are versioned like core contracts**:

```python
STATE_SCHEMA_VERSIONS = {
    'correlation_state': {
        'v1.0.0': {
            'schema': CORRELATION_STATE_SCHEMA_V1,
            'migration_from': None
        },
        'v1.1.0': {
            'schema': CORRELATION_STATE_SCHEMA_V1_1,
            'migration_from': 'v1.0.0'
        }
    }
}

class StateSchemaManager:
    def __init__(self):
        self.current_versions = {
            'correlation_state': 'v1.1.0',
            'workflow_state': 'v1.0.0',
            'audit_state': 'v1.0.0'
        }
    
    async def validate_state(self, state_type, data):
        """Validate state data against current schema."""
        current_version = self.current_versions[state_type]
        schema = STATE_SCHEMA_VERSIONS[state_type][current_version]['schema']
        
        try:
            jsonschema.validate(data, schema)
            return True
        except jsonschema.ValidationError as e:
            logger.error(
                "State validation failed",
                state_type=state_type,
                version=current_version,
                error=str(e)
            )
            return False
    
    async def migrate_state(self, state_type, old_data, from_version, to_version):
        """Migrate state data between schema versions."""
        migration_path = self._find_migration_path(state_type, from_version, to_version)
        
        migrated_data = old_data
        for step in migration_path:
            migrated_data = await self._apply_migration_step(migrated_data, step)
        
        return migrated_data
    
    def _find_migration_path(self, state_type, from_version, to_version):
        """Find migration path between schema versions."""
        # Implementation for finding migration steps
        # Returns list of migration functions to apply
        pass
```

## Example: Agent Signal Merging

### Signal Aggregation Pattern

**Demonstrate how orchestrator merges agent outputs**:

```python
class SignalMerger:
    async def merge_agent_signals(self, corr_id):
        """Example of merging momentum and risk agent outputs."""
        
        # Retrieve signals from shared state
        signals = await self.state_manager.get_signals(corr_id)
        
        momentum_signal = signals.get('momentum')
        risk_signal = signals.get('risk')
        
        if not momentum_signal or not risk_signal:
            return None  # Wait for more signals
        
        # Extract analysis data
        momentum_analysis = momentum_signal['analysis']
        risk_analysis = risk_signal['analysis']
        
        # Merge into unified decision context
        merged_context = {
            'corr_id': corr_id,
            'source_signals': {
                'momentum': {
                    'agent_version': momentum_signal['agent_version'],
                    'enriched_at': momentum_signal['enriched_at'],
                    'trend_direction': momentum_analysis['trend_direction'],
                    'momentum_strength': momentum_analysis['momentum_strength'],
                    'confidence': momentum_analysis['confidence']
                },
                'risk': {
                    'agent_version': risk_signal['agent_version'],
                    'enriched_at': risk_signal['enriched_at'],
                    'risk_level': risk_analysis['risk_level'],
                    'max_position_size': risk_analysis['position_sizing']['max_position_size'],
                    'recommended_size': risk_analysis['position_sizing']['recommended_size']
                }
            },
            'merged_analysis': {
                'overall_confidence': self._calculate_combined_confidence(
                    momentum_analysis['confidence'],
                    risk_analysis['overall_score']
                ),
                'recommended_action': self._determine_action(
                    momentum_analysis,
                    risk_analysis
                ),
                'position_sizing': self._calculate_position_size(
                    momentum_analysis,
                    risk_analysis
                ),
                'risk_constraints': {
                    'stop_loss': self._calculate_stop_loss(momentum_analysis, risk_analysis),
                    'max_risk_pct': risk_analysis.get('recommendations', {}).get('max_risk_per_trade', 0.02)
                }
            },
            'metadata': {
                'merged_at': datetime.utcnow().isoformat(),
                'orchestrator_version': self.version,
                'merge_pattern': 'momentum_risk_fusion'
            }
        }
        
        # Store merged context for audit
        await self.state_manager.store_merged_context(corr_id, merged_context)
        
        return merged_context
    
    def _calculate_combined_confidence(self, momentum_conf, risk_score):
        """Combine momentum confidence with risk assessment."""
        # Risk score is 0-1 where 1 is highest risk
        # Convert to confidence multiplier (lower risk = higher confidence)
        risk_confidence = 1.0 - risk_score
        
        # Weighted combination
        combined = (momentum_conf * 0.6) + (risk_confidence * 0.4)
        
        return min(max(combined, 0.0), 1.0)  # Clamp to [0, 1]
    
    def _determine_action(self, momentum_analysis, risk_analysis):
        """Determine trading action based on combined analysis."""
        risk_level = risk_analysis['risk_level']
        momentum_direction = momentum_analysis['trend_direction']
        momentum_strength = momentum_analysis['momentum_strength']
        
        # Risk-based filtering
        if risk_level == 'blocked':
            return 'no_trade'
        
        if risk_level == 'high' and momentum_strength < 0.8:
            return 'monitor'  # High risk requires high momentum
        
        # Momentum-based action
        if momentum_direction in ['bullish', 'bearish'] and momentum_strength > 0.6:
            return 'trade'
        
        return 'monitor'
    
    def _calculate_position_size(self, momentum_analysis, risk_analysis):
        """Calculate final position size combining momentum and risk."""
        base_size = risk_analysis['position_sizing']['recommended_size']
        momentum_strength = momentum_analysis['momentum_strength']
        
        # Adjust size based on momentum strength
        momentum_multiplier = 0.5 + (momentum_strength * 0.5)  # 0.5 to 1.0
        
        final_size = base_size * momentum_multiplier
        
        return {
            'base_size': base_size,
            'momentum_multiplier': momentum_multiplier,
            'final_size': final_size,
            'currency': 'USD'  # From original signal
        }
```

### State Persistence Example

**Show how merged state is stored and retrieved**:

```python
class StatePersistenceExample:
    async def demonstrate_state_lifecycle(self):
        """Demonstrate complete state lifecycle."""
        corr_id = "example_correlation_123"
        
        # 1. Initialize correlation state
        await self.initialize_correlation(corr_id)
        
        # 2. Store agent signals as they arrive
        momentum_signal = {
            'agent_name': 'momentum',
            'agent_version': '1.2.1',
            'corr_id': corr_id,
            'enriched_at': datetime.utcnow().isoformat(),
            'analysis': {
                'trend_direction': 'bullish',
                'momentum_strength': 0.75,
                'confidence': 0.82
            }
        }
        
        await self.store_agent_signal(corr_id, 'momentum', momentum_signal)
        
        # 3. Wait for and store risk signal
        risk_signal = {
            'agent_name': 'risk',
            'agent_version': '2.0.0',
            'corr_id': corr_id,
            'enriched_at': datetime.utcnow().isoformat(),
            'analysis': {
                'risk_level': 'medium',
                'overall_score': 0.65,
                'position_sizing': {
                    'recommended_size': 10000
                }
            }
        }
        
        await self.store_agent_signal(corr_id, 'risk', risk_signal)
        
        # 4. Check if ready for orchestration
        if await self.can_orchestrate(corr_id):
            # 5. Merge signals
            merged_context = await self.merge_agent_signals(corr_id)
            
            # 6. Store final decision
            decision = {
                'action': 'trade',
                'direction': 'buy',
                'size': 7500,
                'confidence': 0.78
            }
            
            await self.store_orchestration_decision(corr_id, decision, merged_context)
            
            # 7. Cleanup correlation state
            await self.cleanup_completed_correlation(corr_id)
        
        return decision
    
    async def initialize_correlation(self, corr_id):
        """Initialize tracking for new correlation."""
        initial_state = {
            'corr_id': corr_id,
            'status': 'collecting',
            'signals': {},
            'metadata': {
                'created_at': datetime.utcnow().isoformat(),
                'expected_agents': ['momentum', 'risk'],
                'timeout_at': (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            }
        }
        
        # Store in both ephemeral and durable state
        await self.ephemeral_state.store_correlation(corr_id, initial_state)
        await self.durable_state.store_correlation_state(corr_id, initial_state)
```

---

**For implementation details, see [META_AGENT_TEMPLATE.md](META_AGENT_TEMPLATE.md) and [ORCHESTRATION_MODEL.md](ORCHESTRATION_MODEL.md).**
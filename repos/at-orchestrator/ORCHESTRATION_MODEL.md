# Orchestration Model

**Patterns and flows for coordinating multi-agent trading decisions.**

## Overview

The orchestration model defines how the meta-agent layer coordinates specialized trading agents to make informed trading decisions. It provides structured patterns for aggregating agent outputs, managing complex workflows, and ensuring reliable decision-making across the distributed agent network.

## Supported Orchestration Patterns

### 1. Fan-In Pattern

**Purpose**: Multiple agents contribute analysis to a single decision point.

**Flow Diagram**:
```
          signals.normalized
                  ↓
        ┌───────┴───────┐
        │ Agent Distribution │
        └───────┬───────┘
                  │
     ┌────────┼────────┐
     │            │            │
┌───┴───┐  ┌──┴──┐  ┌─┴───┐
│Momentum│  │Risk│  │Corr│
│ Agent │  │Agent│  │Agent│
└───┬───┘  └──┬──┘  └─┬───┘
     │          │         │
     └────┬─────┘         │
          │              │
   ┌─────┴──────────────┘
   │   Orchestrator        │
   │   (Aggregation)       │
   └─────────┬─────────┘
              │
       orchestrated.decision
```

**Implementation Pattern**:
```python
class FanInOrchestrator:
    async def handle_enriched_signal(self, signal):
        corr_id = signal['corr_id']
        agent_name = signal['agent_name']
        
        # Store agent output
        await self.state.store_agent_signal(corr_id, agent_name, signal)
        
        # Check if we have all required agents
        required_agents = ['momentum', 'risk', 'correlation']
        available_signals = await self.state.get_signals(corr_id)
        
        if all(agent in available_signals for agent in required_agents):
            # All agents have reported - aggregate and decide
            decision = await self.aggregate_signals(available_signals)
            await self.publish_decision(corr_id, decision)
            await self.state.cleanup_correlation(corr_id)
    
    async def aggregate_signals(self, signals):
        """Combine multiple agent analyses into unified decision."""
        momentum = signals['momentum']['analysis']
        risk = signals['risk']['analysis']
        correlation = signals['correlation']['analysis']
        
        # Weighted aggregation logic
        confidence = (
            momentum['confidence'] * 0.4 +
            (1.0 - risk['overall_score']) * 0.4 +
            correlation['portfolio_impact'] * 0.2
        )
        
        return {
            'action': self._determine_action(momentum, risk),
            'confidence': confidence,
            'contributing_agents': list(signals.keys()),
            'aggregation_method': 'weighted_average'
        }
```

**Use Cases**:
- **Trade Decision Making**: Combine momentum, risk, and correlation analysis
- **Portfolio Rebalancing**: Aggregate multiple asset analyses
- **Risk Assessment**: Merge various risk factor evaluations

### 2. Fan-Out Pattern

**Purpose**: Single event triggers multiple downstream workflows.

**Flow Diagram**:
```
       orchestrated.decision
                ↓
      ┌───────┴───────┐
      │   Orchestrator   │
      │   (Broadcast)    │
      └───────┬───────┘
                │
    ┌───────┼───────┐
    │             │             │
┌─┴───┐   ┌──┴───┐   ┌─┴───┐
│Exec│   │Risk│   │Audit│
│Sim │   │Mon │   │Log │
└─────┘   └─────┘   └─────┘
```

**Implementation Pattern**:
```python
class FanOutOrchestrator:
    async def orchestrate_decision(self, signals):
        decision = await self.make_decision(signals)
        
        # Broadcast to multiple downstream systems
        tasks = []
        
        # Send to execution
        if decision['action'] == 'trade':
            tasks.append(self.send_to_execution(decision))
        
        # Send to risk monitoring
        tasks.append(self.send_to_risk_monitor(decision))
        
        # Send to audit log
        tasks.append(self.send_to_audit(decision))
        
        # Send to portfolio tracker
        tasks.append(self.send_to_portfolio_tracker(decision))
        
        # Execute all broadcasts in parallel
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_to_execution(self, decision):
        await self.nats.publish(
            'execution.order',
            self._format_execution_order(decision)
        )
    
    async def send_to_risk_monitor(self, decision):
        await self.nats.publish(
            'risk.monitor.decision',
            self._format_risk_update(decision)
        )
    
    async def send_to_audit(self, decision):
        await self.nats.publish(
            'audit.decision',
            self._format_audit_entry(decision)
        )
```

**Use Cases**:
- **Decision Broadcasting**: Send trading decisions to execution, monitoring, and audit
- **Alert Distribution**: Notify multiple systems of important events
- **Workflow Triggering**: Initiate multiple parallel processes

### 3. Conditional Routing Pattern

**Purpose**: Route events based on content, rules, and conditions.

**Flow Diagram**:
```
      enriched signals
            ↓
   ┌───────┴───────┐
   │   Orchestrator   │
   │  (Rule Engine)   │
   └───────┬───────┘
             │
    ┌─────┴─────┐
    │ Rule  │ Rule  │
    │  A    │  B    │
    └──┬──┘└──┬──┘
        │       │
  ┌───┴───┐ ┌─┴───┐
  │Handler│ │Handler│
  │   1   │ │   2   │
  └───────┘ └───────┘
```

**Implementation Pattern**:
```python
class ConditionalOrchestrator:
    def __init__(self):
        self.routing_rules = [
            {
                'name': 'crypto_high_risk',
                'condition': self._is_crypto_high_risk,
                'handler': self._handle_crypto_high_risk
            },
            {
                'name': 'forex_momentum',
                'condition': self._is_forex_momentum,
                'handler': self._handle_forex_momentum
            },
            {
                'name': 'default',
                'condition': lambda _: True,  # Catch-all
                'handler': self._handle_default
            }
        ]
    
    async def route_signal(self, signals):
        """Route signals based on conditional rules."""
        for rule in self.routing_rules:
            if rule['condition'](signals):
                await rule['handler'](signals)
                break
    
    def _is_crypto_high_risk(self, signals):
        """Check if this is a high-risk crypto signal."""
        source_signal = signals.get('momentum', {}).get('source_signal', {})
        risk_analysis = signals.get('risk', {}).get('analysis', {})
        
        is_crypto = source_signal.get('instrument', '').endswith('/USD')
        is_high_risk = risk_analysis.get('risk_level') == 'high'
        
        return is_crypto and is_high_risk
    
    def _is_forex_momentum(self, signals):
        """Check if this is a forex momentum signal."""
        source_signal = signals.get('momentum', {}).get('source_signal', {})
        momentum_analysis = signals.get('momentum', {}).get('analysis', {})
        
        is_forex = len(source_signal.get('instrument', '')) == 6  # EURUSD format
        has_momentum = momentum_analysis.get('momentum_strength', 0) > 0.7
        
        return is_forex and has_momentum
    
    async def _handle_crypto_high_risk(self, signals):
        """Handle high-risk crypto signals."""
        # Reduce position size and add extra risk checks
        decision = {
            'action': 'trade_with_caution',
            'position_multiplier': 0.5,
            'additional_checks': ['volatility', 'liquidity'],
            'handler': 'crypto_high_risk'
        }
        
        await self.publish_to_specialized_handler(
            'execution.crypto.high_risk',
            decision
        )
    
    async def _handle_forex_momentum(self, signals):
        """Handle forex momentum signals."""
        # Standard momentum-based execution
        decision = {
            'action': 'trade',
            'strategy': 'momentum_breakout',
            'handler': 'forex_momentum'
        }
        
        await self.publish_to_standard_handler(
            'execution.forex.momentum',
            decision
        )
```

**Use Cases**:
- **Asset-Specific Routing**: Different handling for crypto vs forex vs stocks
- **Risk-Based Routing**: Route high-risk signals to specialized handlers
- **Strategy Selection**: Choose appropriate execution strategy based on signal characteristics

### 4. Sequential Workflow Pattern

**Purpose**: Multi-stage processing with dependencies between stages.

**Flow Diagram**:
```
signals.enriched.*
        ↓
 ┌─────┴─────┐
 │ Stage 1:   │
 │ Validation │
 └─────┬─────┘
        │
 ┌─────┴─────┐
 │ Stage 2:   │
 │ Risk Check │
 └─────┬─────┘
        │
 ┌─────┴─────┐
 │ Stage 3:   │
 │ Execution  │
 └─────┬─────┘
        │
 orchestrated.decision
```

**Implementation Pattern**:
```python
class SequentialWorkflowOrchestrator:
    def __init__(self):
        self.workflow_stages = [
            self._stage_validation,
            self._stage_risk_check,
            self._stage_position_sizing,
            self._stage_execution_timing
        ]
    
    async def process_workflow(self, signals):
        """Process signals through sequential stages."""
        context = {
            'signals': signals,
            'stage_results': {},
            'current_stage': 0
        }
        
        for stage_num, stage_func in enumerate(self.workflow_stages):
            context['current_stage'] = stage_num
            
            try:
                stage_result = await stage_func(context)
                context['stage_results'][stage_num] = stage_result
                
                # Check if stage indicates workflow should stop
                if stage_result.get('stop_workflow'):
                    break
                    
            except Exception as e:
                await self._handle_stage_error(stage_num, e, context)
                break
        
        return await self._finalize_workflow(context)
    
    async def _stage_validation(self, context):
        """Stage 1: Validate signal quality and completeness."""
        signals = context['signals']
        
        # Check signal quality
        quality_score = self._calculate_signal_quality(signals)
        
        if quality_score < 0.6:
            return {'stop_workflow': True, 'reason': 'poor_signal_quality'}
        
        return {
            'quality_score': quality_score,
            'validated': True
        }
    
    async def _stage_risk_check(self, context):
        """Stage 2: Comprehensive risk assessment."""
        risk_signals = context['signals'].get('risk', {})
        
        # Aggregate risk factors
        risk_factors = self._aggregate_risk_factors(risk_signals)
        
        if risk_factors['overall_risk'] > 0.8:
            return {'stop_workflow': True, 'reason': 'excessive_risk'}
        
        return {
            'risk_factors': risk_factors,
            'risk_approved': True
        }
```

## Correlation ID Flow

### End-to-End Tracing

**Correlation ID propagation ensures complete traceability**:

```
Webhook (corr_id: req_abc123)
    ↓
Gateway validates and normalizes
    ↓
NATS: signals.normalized (corr_id: req_abc123)
    ↓
Agents process in parallel:
├── Momentum Agent (corr_id: req_abc123)
├── Risk Agent (corr_id: req_abc123)
└── Correlation Agent (corr_id: req_abc123)
    ↓
NATS: signals.enriched.* (corr_id: req_abc123)
    ↓
Orchestrator aggregates by corr_id
    ↓
NATS: orchestrated.decision (corr_id: req_abc123)
    ↓
Execution (corr_id: req_abc123)
```

### Correlation State Management

```python
class CorrelationTracker:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.correlation_ttl = 300  # 5 minutes
    
    async def track_signal(self, corr_id, agent_name, signal):
        """Track agent signal for correlation."""
        key = f"correlation:{corr_id}"
        
        # Store signal data
        await self.redis.hset(key, agent_name, json.dumps(signal))
        await self.redis.expire(key, self.correlation_ttl)
        
        # Update tracking metadata
        metadata_key = f"correlation:meta:{corr_id}"
        await self.redis.hset(metadata_key, {
            'last_update': datetime.utcnow().isoformat(),
            'agent_count': await self.redis.hlen(key),
            'status': 'collecting'
        })
        await self.redis.expire(metadata_key, self.correlation_ttl)
    
    async def get_correlation_signals(self, corr_id):
        """Get all signals for correlation ID."""
        key = f"correlation:{corr_id}"
        signal_data = await self.redis.hgetall(key)
        
        signals = {}
        for agent_name, signal_json in signal_data.items():
            signals[agent_name] = json.loads(signal_json)
        
        return signals
    
    async def mark_orchestrated(self, corr_id):
        """Mark correlation as orchestrated."""
        metadata_key = f"correlation:meta:{corr_id}"
        await self.redis.hset(metadata_key, {
            'status': 'orchestrated',
            'orchestrated_at': datetime.utcnow().isoformat()
        })
```

## Orchestration Guardrails

### 1. Immutability Principle

**Orchestrator never mutates agent outputs**:

```python
# ✅ CORRECT: Aggregate without mutation
def aggregate_signals(self, signals):
    # Create new decision based on agent outputs
    decision = {
        'confidence': self._calculate_combined_confidence(signals),
        'action': self._determine_action(signals),
        'contributing_signals': [s['corr_id'] for s in signals.values()]
    }
    return decision

# ❌ INCORRECT: Mutating agent outputs
def aggregate_signals(self, signals):
    # Don't modify agent outputs directly
    signals['momentum']['analysis']['modified'] = True  # BAD
    return signals
```

### 2. Timeout Management

**Handle incomplete signal collection gracefully**:

```python
class TimeoutManager:
    async def wait_for_signals(self, corr_id, required_agents, timeout_sec=300):
        """Wait for required agents with timeout."""
        start_time = time.time()
        
        while time.time() - start_time < timeout_sec:
            signals = await self.get_signals(corr_id)
            
            if all(agent in signals for agent in required_agents):
                return signals
            
            await asyncio.sleep(1)  # Check every second
        
        # Handle timeout
        available_signals = await self.get_signals(corr_id)
        return await self._handle_timeout(corr_id, available_signals, required_agents)
    
    async def _handle_timeout(self, corr_id, available_signals, required_agents):
        """Handle partial signal collection on timeout."""
        missing_agents = set(required_agents) - set(available_signals.keys())
        
        # Log timeout for investigation
        logger.warning(
            "Signal collection timeout",
            corr_id=corr_id,
            available_agents=list(available_signals.keys()),
            missing_agents=list(missing_agents),
            timeout_duration=300
        )
        
        # Decide based on available signals if possible
        if len(available_signals) >= self.min_agents_threshold:
            return available_signals
        
        # Return None to indicate insufficient data
        return None
```

### 3. Error Isolation

**Prevent single agent failures from blocking orchestration**:

```python
class ErrorIsolation:
    async def safe_signal_processing(self, signals):
        """Process signals with error isolation."""
        valid_signals = {}
        errors = {}
        
        for agent_name, signal in signals.items():
            try:
                # Validate signal format
                validated_signal = await self._validate_signal(signal)
                valid_signals[agent_name] = validated_signal
                
            except ValidationError as e:
                errors[agent_name] = {
                    'type': 'validation_error',
                    'message': str(e)
                }
                logger.error(
                    "Signal validation failed",
                    agent=agent_name,
                    error=str(e),
                    corr_id=signal.get('corr_id')
                )
            
            except Exception as e:
                errors[agent_name] = {
                    'type': 'processing_error',
                    'message': str(e)
                }
                logger.error(
                    "Signal processing failed",
                    agent=agent_name,
                    error=str(e),
                    corr_id=signal.get('corr_id')
                )
        
        return valid_signals, errors
```

### 4. Decision Auditing

**Log all orchestration decisions for audit and debugging**:

```python
class DecisionAuditor:
    async def audit_decision(self, corr_id, signals, decision, metadata):
        """Create audit trail for orchestration decisions."""
        audit_entry = {
            'corr_id': corr_id,
            'timestamp': datetime.utcnow().isoformat(),
            'orchestrator_version': self.version,
            'input_signals': {
                agent: {
                    'agent_version': signal.get('agent_version'),
                    'confidence': signal.get('analysis', {}).get('confidence'),
                    'timestamp': signal.get('enriched_at')
                }
                for agent, signal in signals.items()
            },
            'decision': decision,
            'metadata': {
                'processing_time_ms': metadata.get('processing_time_ms'),
                'orchestration_pattern': metadata.get('pattern'),
                'timeout_occurred': metadata.get('timeout_occurred'),
                'error_count': metadata.get('error_count', 0)
            }
        }
        
        # Store audit entry
        await self.store_audit_entry(audit_entry)
        
        # Publish to audit stream
        await self.nats.publish(
            'audit.orchestration.decision',
            json.dumps(audit_entry).encode()
        )
```

---

**For implementation details, see [META_AGENT_TEMPLATE.md](META_AGENT_TEMPLATE.md) and [STATE_MANAGEMENT.md](STATE_MANAGEMENT.md).**
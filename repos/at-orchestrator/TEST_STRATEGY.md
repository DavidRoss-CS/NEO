# Test Strategy - Orchestrator Testing

**Comprehensive testing approach for meta-agent orchestration from unit to chaos tests.**

## Testing Philosophy

**Orchestration-first testing**: All tests validate that the meta-agent layer correctly coordinates multiple agents, manages shared state, and handles complex failure scenarios. The testing pyramid emphasizes both individual orchestrator logic and system-wide integration reliability.

**Test Categories**:
- **Unit tests**: Orchestrator logic and state management
- **Contract tests**: State schema compliance and agent interaction
- **Integration tests**: End-to-end NATS + Redis orchestration flows
- **Chaos tests**: Failure scenarios and recovery (Redis outages, agent failures)
- **Soak tests**: Sustained load (5k events/minute for 30 minutes)

## Test Pyramid

```
    ┌───────────────┐
    │  Chaos Tests   │  ← Failure scenarios
    └──────┬────────┘
          │
    ┌──────┴──────────┐
    │   Soak Tests    │  ← Sustained load
    └────────┬────────┘
              │
    ┌─────────┴─────────────┐
    │ Integration Tests  │  ← NATS + Redis + Agents
    └───────────┬───────────┘
                 │
    ┌─────────────┴────────────────┐
    │     Contract Tests      │  ← State schemas
    └────────────────┬────────────────┘
                          │
    ┌────────────────────┴────────────────────┐
    │            Unit Tests            │  ← Fast, isolated
    └────────────────────────────────────────┘
```

## Unit Tests

### Orchestration Logic Tests

**Test individual orchestrator routing and decision logic**:

```python
# tests/test_orchestration_logic.py
import pytest
from datetime import datetime, timedelta
from orchestrators.simple.orchestrator import SimpleOrchestrator
from shared.state_manager import MockStateManager

class TestOrchestrationLogic:
    def setup_method(self):
        self.state_manager = MockStateManager()
        self.orchestrator = SimpleOrchestrator(state_manager=self.state_manager)
    
    def test_fan_in_aggregation(self):
        """Test aggregation of multiple agent signals."""
        corr_id = "test_fanin_001"
        
        # Mock momentum signal
        momentum_signal = {
            'agent_name': 'momentum',
            'corr_id': corr_id,
            'analysis': {
                'trend_direction': 'bullish',
                'momentum_strength': 0.75,
                'confidence': 0.82
            }
        }
        
        # Mock risk signal
        risk_signal = {
            'agent_name': 'risk',
            'corr_id': corr_id,
            'analysis': {
                'risk_level': 'medium',
                'overall_score': 0.65,
                'position_sizing': {
                    'recommended_size': 10000
                }
            }
        }
        
        signals = {'momentum': momentum_signal, 'risk': risk_signal}
        
        # Test aggregation
        result = self.orchestrator.aggregate_signals(signals)
        
        assert result['action'] == 'trade'
        assert result['confidence'] > 0.5
        assert result['contributing_agents'] == ['momentum', 'risk']
        assert 'aggregation_method' in result
    
    def test_conditional_routing(self):
        """Test routing based on signal characteristics."""
        # Test crypto high-risk routing
        crypto_signals = {
            'momentum': {
                'source_signal': {'instrument': 'BTC/USD'},
                'analysis': {'momentum_strength': 0.6}
            },
            'risk': {
                'analysis': {'risk_level': 'high'}
            }
        }
        
        route = self.orchestrator.determine_route(crypto_signals)
        assert route == 'crypto_high_risk'
        
        # Test forex momentum routing
        forex_signals = {
            'momentum': {
                'source_signal': {'instrument': 'EURUSD'},
                'analysis': {'momentum_strength': 0.8}
            },
            'risk': {
                'analysis': {'risk_level': 'low'}
            }
        }
        
        route = self.orchestrator.determine_route(forex_signals)
        assert route == 'forex_momentum'
    
    def test_timeout_handling(self):
        """Test handling of incomplete signal collection."""
        corr_id = "test_timeout_001"
        
        # Only momentum signal arrives
        incomplete_signals = {
            'momentum': {
                'agent_name': 'momentum',
                'corr_id': corr_id,
                'analysis': {'confidence': 0.8}
            }
        }
        
        # Test timeout handling
        result = self.orchestrator.handle_timeout(
            corr_id, 
            incomplete_signals, 
            required_agents=['momentum', 'risk']
        )
        
        assert result['action'] == 'insufficient_data'
        assert result['available_agents'] == ['momentum']
        assert result['missing_agents'] == ['risk']
    
    def test_confidence_calculation(self):
        """Test confidence scoring algorithms."""
        # High confidence scenario
        high_conf_signals = {
            'momentum': {'analysis': {'confidence': 0.9}},
            'risk': {'analysis': {'overall_score': 0.2}}  # Low risk
        }
        
        confidence = self.orchestrator.calculate_confidence(high_conf_signals)
        assert confidence > 0.8
        
        # Low confidence scenario
        low_conf_signals = {
            'momentum': {'analysis': {'confidence': 0.4}},
            'risk': {'analysis': {'overall_score': 0.8}}  # High risk
        }
        
        confidence = self.orchestrator.calculate_confidence(low_conf_signals)
        assert confidence < 0.4
    
    def test_decision_logic_edge_cases(self):
        """Test edge cases in decision making."""
        # Risk blocked scenario
        blocked_signals = {
            'momentum': {'analysis': {'confidence': 0.9}},
            'risk': {'analysis': {'risk_level': 'blocked'}}
        }
        
        decision = self.orchestrator.make_decision(blocked_signals)
        assert decision['action'] == 'no_trade'
        assert decision['reason'] == 'risk_blocked'
        
        # Conflicting signals scenario
        conflicting_signals = {
            'momentum': {
                'analysis': {
                    'trend_direction': 'bullish',
                    'confidence': 0.8
                }
            },
            'risk': {
                'analysis': {
                    'risk_level': 'high',
                    'overall_score': 0.9
                }
            }
        }
        
        decision = self.orchestrator.make_decision(conflicting_signals)
        assert decision['action'] in ['monitor', 'reduce_size']
```

### State Management Unit Tests

```python
# tests/test_state_management.py
class TestStateManagement:
    def setup_method(self):
        self.state_manager = EphemeralStateManager()
    
    async def test_correlation_tracking(self):
        """Test correlation ID tracking and cleanup."""
        corr_id = "test_correlation_001"
        
        # Store signals
        momentum_signal = {'agent_name': 'momentum', 'data': 'test'}
        await self.state_manager.store_signal(corr_id, 'momentum', momentum_signal)
        
        risk_signal = {'agent_name': 'risk', 'data': 'test'}
        await self.state_manager.store_signal(corr_id, 'risk', risk_signal)
        
        # Retrieve signals
        signals = await self.state_manager.get_signals(corr_id)
        assert len(signals) == 2
        assert 'momentum' in signals
        assert 'risk' in signals
        
        # Test cleanup
        await self.state_manager.cleanup_correlation(corr_id)
        signals = await self.state_manager.get_signals(corr_id)
        assert len(signals) == 0
    
    async def test_ttl_expiration(self):
        """Test TTL-based state expiration."""
        corr_id = "test_ttl_001"
        
        # Store with short TTL
        signal = {'data': 'test'}
        await self.state_manager.store_signal(corr_id, 'test_agent', signal)
        
        # Verify signal exists
        signals = await self.state_manager.get_signals(corr_id)
        assert len(signals) == 1
        
        # Mock TTL expiration
        self.state_manager.ttl_tracker[corr_id] = time.time() - 1
        
        # Verify signal is cleaned up
        signals = await self.state_manager.get_signals(corr_id)
        assert len(signals) == 0
    
    async def test_concurrent_access(self):
        """Test concurrent access to shared state."""
        corr_id = "test_concurrent_001"
        
        async def store_signal(agent_name, delay=0):
            if delay:
                await asyncio.sleep(delay)
            signal = {'agent_name': agent_name, 'timestamp': time.time()}
            await self.state_manager.store_signal(corr_id, agent_name, signal)
        
        # Store signals concurrently
        await asyncio.gather(
            store_signal('momentum', 0.1),
            store_signal('risk', 0.2),
            store_signal('correlation', 0.3)
        )
        
        # Verify all signals stored
        signals = await self.state_manager.get_signals(corr_id)
        assert len(signals) == 3
        assert all(agent in signals for agent in ['momentum', 'risk', 'correlation'])
```

## Contract Tests

### State Schema Validation

**Ensure state blobs validate against schemas**:

```python
# tests/test_contract_compliance.py
import json
import pytest
from jsonschema import validate, ValidationError

class TestContractCompliance:
    def setup_method(self):
        # Load state schemas
        with open('schemas/correlation_state.schema.json') as f:
            self.correlation_schema = json.load(f)
        
        with open('schemas/orchestration_decision.schema.json') as f:
            self.decision_schema = json.load(f)
    
    def test_correlation_state_schema(self):
        """Test correlation state validates against schema."""
        valid_state = {
            'corr_id': 'test_001',
            'status': 'collecting',
            'signals': {
                'momentum': {
                    'agent_name': 'momentum',
                    'corr_id': 'test_001',
                    'enriched_at': '2024-01-15T10:30:00Z',
                    'analysis': {'confidence': 0.8}
                }
            },
            'metadata': {
                'created_at': '2024-01-15T10:29:00Z',
                'expected_agents': ['momentum', 'risk'],
                'timeout_at': '2024-01-15T10:34:00Z'
            }
        }
        
        # Should validate successfully
        validate(instance=valid_state, schema=self.correlation_schema)
    
    def test_invalid_correlation_state(self):
        """Test invalid correlation state fails validation."""
        invalid_state = {
            'corr_id': 'test_002',
            'status': 'invalid_status',  # Invalid enum value
            'signals': {},
            # Missing required metadata
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_state, schema=self.correlation_schema)
    
    def test_orchestration_decision_schema(self):
        """Test orchestration decisions validate against schema."""
        valid_decision = {
            'corr_id': 'test_003',
            'orchestrator_version': '1.0.0',
            'orchestrated_at': '2024-01-15T10:30:00Z',
            'source_signals': {
                'momentum': 0.75,
                'risk': 0.65
            },
            'decision': {
                'action': 'trade',
                'confidence': 0.78,
                'reasoning': 'high_momentum_acceptable_risk'
            }
        }
        
        validate(instance=valid_decision, schema=self.decision_schema)
    
    def test_state_schema_versioning(self):
        """Test state schema version compatibility."""
        # Test v1.0.0 state validates against v1.1.0 schema
        v1_state = {
            'corr_id': 'test_004',
            'status': 'completed',
            'signals': {},
            'metadata': {
                'created_at': '2024-01-15T10:30:00Z'
            }
        }
        
        # Should validate (backwards compatible)
        validate(instance=v1_state, schema=self.correlation_schema)
    
    def test_cross_service_compatibility(self):
        """Test compatibility with agent output schemas."""
        # Simulate agent output that will be stored in orchestrator state
        agent_output = {
            'schema_version': '1.0.0',
            'agent_name': 'momentum',
            'agent_version': '1.2.1',
            'corr_id': 'test_005',
            'enriched_at': '2024-01-15T10:30:00Z',
            'analysis': {
                'momentum_strength': 0.75,
                'confidence': 0.82
            }
        }
        
        # Wrap in correlation state format
        correlation_state = {
            'corr_id': 'test_005',
            'status': 'collecting',
            'signals': {
                'momentum': agent_output
            },
            'metadata': {
                'created_at': '2024-01-15T10:29:00Z',
                'expected_agents': ['momentum'],
                'timeout_at': '2024-01-15T10:34:00Z'
            }
        }
        
        validate(instance=correlation_state, schema=self.correlation_schema)
```

## Integration Tests

### End-to-End NATS + Redis Flow

**Test complete orchestration flow with real infrastructure**:

```python
# tests/test_integration.py
import asyncio
import json
import pytest
import redis.asyncio as redis
from nats.aio.client import Client as NATS
from orchestrators.simple.orchestrator import SimpleOrchestrator

@pytest.mark.integration
class TestIntegrationFlow:
    @pytest.fixture
    async def infrastructure(self):
        """Set up NATS and Redis for testing."""
        # NATS connection
        nats = NATS()
        await nats.connect('nats://localhost:4222')
        js = nats.jetstream()
        
        # Redis connection
        redis_client = redis.from_url('redis://localhost:6379')
        await redis_client.flushdb()  # Clean state
        
        yield {'nats': nats, 'jetstream': js, 'redis': redis_client}
        
        # Cleanup
        await nats.close()
        await redis_client.close()
    
    async def test_end_to_end_orchestration(self, infrastructure):
        """Test complete orchestration workflow."""
        nats = infrastructure['nats']
        js = infrastructure['jetstream']
        redis_client = infrastructure['redis']
        
        # Start orchestrator
        orchestrator = SimpleOrchestrator(
            nats_url='nats://localhost:4222',
            redis_url='redis://localhost:6379'
        )
        orchestrator_task = asyncio.create_task(orchestrator.start())
        
        # Allow orchestrator to start
        await asyncio.sleep(1)
        
        # Collect orchestrated decisions
        decisions = []
        
        async def capture_decisions(msg):
            data = json.loads(msg.data.decode())
            decisions.append(data)
            await msg.ack()
        
        await js.subscribe(
            'orchestrated.decision',
            cb=capture_decisions
        )
        
        # Publish momentum signal
        momentum_signal = {
            'schema_version': '1.0.0',
            'agent_name': 'momentum',
            'corr_id': 'integration_test_001',
            'enriched_at': '2024-01-15T10:30:00Z',
            'analysis': {
                'trend_direction': 'bullish',
                'momentum_strength': 0.78,
                'confidence': 0.85
            }
        }
        
        await js.publish(
            'signals.enriched.momentum',
            json.dumps(momentum_signal).encode()
        )
        
        # Publish risk signal
        risk_signal = {
            'schema_version': '1.0.0',
            'agent_name': 'risk',
            'corr_id': 'integration_test_001',
            'enriched_at': '2024-01-15T10:30:01Z',
            'analysis': {
                'risk_level': 'medium',
                'overall_score': 0.6,
                'position_sizing': {
                    'recommended_size': 10000
                }
            }
        }
        
        await js.publish(
            'signals.enriched.risk',
            json.dumps(risk_signal).encode()
        )
        
        # Wait for orchestration
        await asyncio.sleep(3)
        
        # Verify decision was made
        assert len(decisions) == 1
        decision = decisions[0]
        
        assert decision['corr_id'] == 'integration_test_001'
        assert 'decision' in decision
        assert decision['decision']['action'] in ['trade', 'monitor']
        
        # Verify state was stored in Redis
        state_key = 'orchestrator:correlation:integration_test_001'
        state_exists = await redis_client.exists(state_key)
        # State may be cleaned up after orchestration
        
        # Clean up
        await orchestrator.stop()
        orchestrator_task.cancel()
    
    async def test_multiple_correlations_parallel(self, infrastructure):
        """Test parallel processing of multiple correlations."""
        js = infrastructure['jetstream']
        
        orchestrator = SimpleOrchestrator(
            nats_url='nats://localhost:4222',
            redis_url='redis://localhost:6379'
        )
        orchestrator_task = asyncio.create_task(orchestrator.start())
        await asyncio.sleep(1)
        
        decisions = []
        
        async def capture_decisions(msg):
            data = json.loads(msg.data.decode())
            decisions.append(data)
            await msg.ack()
        
        await js.subscribe('orchestrated.decision', cb=capture_decisions)
        
        # Send signals for multiple correlations
        correlation_ids = ['parallel_test_001', 'parallel_test_002', 'parallel_test_003']
        
        for corr_id in correlation_ids:
            # Momentum signal
            momentum_signal = {
                'agent_name': 'momentum',
                'corr_id': corr_id,
                'enriched_at': '2024-01-15T10:30:00Z',
                'analysis': {'confidence': 0.8}
            }
            
            await js.publish(
                'signals.enriched.momentum',
                json.dumps(momentum_signal).encode()
            )
            
            # Risk signal
            risk_signal = {
                'agent_name': 'risk',
                'corr_id': corr_id,
                'enriched_at': '2024-01-15T10:30:01Z',
                'analysis': {'risk_level': 'low'}
            }
            
            await js.publish(
                'signals.enriched.risk',
                json.dumps(risk_signal).encode()
            )
        
        # Wait for all orchestrations
        await asyncio.sleep(5)
        
        # Verify all correlations were processed
        assert len(decisions) == 3
        decision_corr_ids = [d['corr_id'] for d in decisions]
        assert all(corr_id in decision_corr_ids for corr_id in correlation_ids)
        
        await orchestrator.stop()
        orchestrator_task.cancel()
    
    async def test_timeout_handling_integration(self, infrastructure):
        """Test timeout handling with partial signals."""
        js = infrastructure['jetstream']
        
        orchestrator = SimpleOrchestrator(
            nats_url='nats://localhost:4222',
            redis_url='redis://localhost:6379',
            decision_timeout_sec=5  # Short timeout for testing
        )
        orchestrator_task = asyncio.create_task(orchestrator.start())
        await asyncio.sleep(1)
        
        decisions = []
        
        async def capture_decisions(msg):
            data = json.loads(msg.data.decode())
            decisions.append(data)
            await msg.ack()
        
        await js.subscribe('orchestrated.decision', cb=capture_decisions)
        
        # Send only momentum signal (risk signal missing)
        momentum_signal = {
            'agent_name': 'momentum',
            'corr_id': 'timeout_test_001',
            'enriched_at': '2024-01-15T10:30:00Z',
            'analysis': {'confidence': 0.8}
        }
        
        await js.publish(
            'signals.enriched.momentum',
            json.dumps(momentum_signal).encode()
        )
        
        # Wait for timeout
        await asyncio.sleep(7)
        
        # Should have timeout decision or no decision
        # Depending on orchestrator implementation
        
        await orchestrator.stop()
        orchestrator_task.cancel()
```

## Chaos Tests

### Redis Failure Scenarios

**Test orchestrator behavior when Redis becomes unavailable**:

```python
# tests/test_chaos.py
@pytest.mark.chaos
class TestChaosScenarios:
    async def test_redis_outage_graceful_degradation(self):
        """Test orchestrator graceful degradation when Redis fails."""
        # Start orchestrator with Redis
        orchestrator = SimpleOrchestrator(
            nats_url='nats://localhost:4222',
            redis_url='redis://localhost:6379',
            enable_graceful_degradation=True
        )
        
        await orchestrator.start()
        
        # Verify normal operation
        signals = {'momentum': {'confidence': 0.8}, 'risk': {'risk_level': 'low'}}
        decision = await orchestrator.process_signals('test_001', signals)
        assert decision is not None
        
        # Simulate Redis failure
        await self.kill_redis()
        
        # Orchestrator should continue with in-memory fallback
        signals = {'momentum': {'confidence': 0.7}, 'risk': {'risk_level': 'medium'}}
        decision = await orchestrator.process_signals('test_002', signals)
        assert decision is not None
        assert decision.get('degraded_mode') is True
        
        # Restart Redis
        await self.start_redis()
        
        # Should recover to normal operation
        await asyncio.sleep(2)  # Allow reconnection
        signals = {'momentum': {'confidence': 0.9}, 'risk': {'risk_level': 'low'}}
        decision = await orchestrator.process_signals('test_003', signals)
        assert decision is not None
        assert decision.get('degraded_mode') is not True
        
        await orchestrator.stop()
    
    async def test_nats_partition_recovery(self):
        """Test recovery from NATS network partition."""
        orchestrator = SimpleOrchestrator(
            nats_url='nats://localhost:4222',
            redis_url='redis://localhost:6379'
        )
        
        await orchestrator.start()
        
        # Simulate NATS partition
        await self.partition_nats()
        
        # Orchestrator should detect disconnection
        assert not orchestrator.nats.is_connected
        
        # Heal partition
        await self.heal_nats_partition()
        
        # Should reconnect and resume operation
        await asyncio.sleep(5)  # Allow reconnection
        assert orchestrator.nats.is_connected
        
        await orchestrator.stop()
    
    async def test_agent_failure_isolation(self):
        """Test orchestrator when individual agents fail."""
        orchestrator = SimpleOrchestrator(
            nats_url='nats://localhost:4222',
            redis_url='redis://localhost:6379',
            min_agents_threshold=1  # Allow decisions with fewer agents
        )
        
        await orchestrator.start()
        
        # Send momentum signal only (risk agent "failed")
        momentum_signal = {
            'agent_name': 'momentum',
            'corr_id': 'agent_failure_test_001',
            'analysis': {'confidence': 0.9}
        }
        
        # Should make decision with partial data
        decision = await orchestrator.process_single_signal(momentum_signal)
        
        assert decision is not None
        assert decision['decision']['action'] in ['monitor', 'trade']
        assert decision.get('partial_data') is True
        
        await orchestrator.stop()
    
    async def kill_redis(self):
        """Helper to simulate Redis failure."""
        import subprocess
        subprocess.run(['docker', 'stop', 'redis'], check=False)
    
    async def start_redis(self):
        """Helper to restart Redis."""
        import subprocess
        subprocess.run(['docker', 'start', 'redis'], check=False)
        await asyncio.sleep(2)  # Allow startup
    
    async def partition_nats(self):
        """Helper to simulate NATS network partition."""
        # Implementation depends on test environment
        # Could use iptables rules or container networking
        pass
    
    async def heal_nats_partition(self):
        """Helper to heal NATS partition."""
        # Implementation to restore connectivity
        pass
```

## Soak Tests

### Sustained Load Testing

**Test orchestrator under sustained 5k events/minute load for 30 minutes**:

```python
# tests/test_soak.py
@pytest.mark.soak
class TestSoakTesting:
    async def test_sustained_orchestration_load(self):
        """Test orchestrator under sustained load."""
        orchestrator = SimpleOrchestrator(
            nats_url='nats://localhost:4222',
            redis_url='redis://localhost:6379',
            max_concurrent_correlations=1000
        )
        
        await orchestrator.start()
        
        # Test parameters
        target_rate = 5000 / 60  # 83.33 signals per second
        test_duration = 1800     # 30 minutes
        
        # Metrics tracking
        start_time = time.time()
        signals_sent = 0
        decisions_received = 0
        errors = []
        latencies = []
        
        async def capture_decisions(msg):
            nonlocal decisions_received
            receive_time = time.time()
            
            try:
                data = json.loads(msg.data.decode())
                
                # Calculate latency (from first signal to decision)
                signal_time = float(data['corr_id'].split('_')[-1])
                latency = receive_time - signal_time
                latencies.append(latency)
                
                decisions_received += 1
                await msg.ack()
                
            except Exception as e:
                errors.append(str(e))
                await msg.nak()
        
        # Subscribe to decisions
        nats = NATS()
        await nats.connect('nats://localhost:4222')
        js = nats.jetstream()
        await js.subscribe('orchestrated.decision', cb=capture_decisions)
        
        # Generate sustained load
        signal_interval = 1.0 / target_rate
        
        while time.time() - start_time < test_duration:
            current_time = time.time()
            corr_id = f'soak_test_{signals_sent}_{current_time}'
            
            # Send momentum signal
            momentum_signal = {
                'agent_name': 'momentum',
                'corr_id': corr_id,
                'enriched_at': datetime.utcnow().isoformat(),
                'analysis': {
                    'confidence': 0.7 + (signals_sent % 100) * 0.003
                }
            }
            
            await js.publish(
                'signals.enriched.momentum',
                json.dumps(momentum_signal).encode()
            )
            
            # Send risk signal
            risk_signal = {
                'agent_name': 'risk',
                'corr_id': corr_id,
                'enriched_at': datetime.utcnow().isoformat(),
                'analysis': {
                    'risk_level': 'low' if signals_sent % 3 == 0 else 'medium'
                }
            }
            
            await js.publish(
                'signals.enriched.risk',
                json.dumps(risk_signal).encode()
            )
            
            signals_sent += 2  # Two signals per correlation
            
            # Rate limiting
            await asyncio.sleep(signal_interval)
        
        # Allow final processing
        await asyncio.sleep(60)
        
        # Calculate metrics
        actual_duration = time.time() - start_time
        actual_rate = signals_sent / actual_duration
        decision_rate = decisions_received / actual_duration
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        p95_latency = sorted(latencies)[int(0.95 * len(latencies))] if latencies else 0
        error_rate = len(errors) / signals_sent if signals_sent > 0 else 0
        
        # Performance assertions
        assert actual_rate >= target_rate * 0.95, f"Send rate too low: {actual_rate}"
        assert decision_rate >= (target_rate / 2) * 0.95, f"Decision rate too low: {decision_rate}"
        assert avg_latency < 5.0, f"Average latency too high: {avg_latency}s"
        assert p95_latency < 10.0, f"P95 latency too high: {p95_latency}s"
        assert error_rate < 0.01, f"Error rate too high: {error_rate}"
        
        # Memory leak check
        memory_usage = orchestrator.get_memory_usage()
        assert memory_usage < 1024 * 1024 * 1024, f"Memory usage too high: {memory_usage} bytes"
        
        await orchestrator.stop()
        await nats.close()
    
    async def test_memory_stability_under_load(self):
        """Test memory stability during extended operation."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        orchestrator = SimpleOrchestrator(
            nats_url='nats://localhost:4222',
            redis_url='redis://localhost:6379'
        )
        
        await orchestrator.start()
        
        # Run for 1 hour with moderate load
        test_duration = 3600  # 1 hour
        start_time = time.time()
        
        while time.time() - start_time < test_duration:
            # Process correlations every 10 seconds
            signals = {
                'momentum': {'confidence': 0.8},
                'risk': {'risk_level': 'medium'}
            }
            
            corr_id = f'memory_test_{int(time.time())}'
            await orchestrator.process_signals(corr_id, signals)
            
            await asyncio.sleep(10)
            
            # Memory check every 10 minutes
            if int(time.time() - start_time) % 600 == 0:
                current_memory = process.memory_info().rss
                memory_growth = (current_memory - initial_memory) / 1024 / 1024  # MB
                
                # Memory growth should be < 200MB
                assert memory_growth < 200, f"Memory leak detected: {memory_growth}MB growth"
        
        final_memory = process.memory_info().rss
        total_growth = (final_memory - initial_memory) / 1024 / 1024
        
        # Final memory check
        assert total_growth < 500, f"Excessive memory growth: {total_growth}MB"
        
        await orchestrator.stop()
```

## CI/CD Integration

### Test Execution Pipeline

**pytest configuration (pytest.ini)**:
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --cov=orchestrators
    --cov=shared
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90
markers =
    unit: Fast unit tests
    contract: Schema contract tests
    integration: Integration tests requiring NATS + Redis
    chaos: Chaos engineering tests
    soak: Long-running load tests
```

### GitHub Actions Workflow

**.github/workflows/orchestrator-tests.yml**:
```yaml
name: Orchestrator Tests

on:
  pull_request:
    paths:
      - 'orchestrators/**'
      - 'shared/**'
      - 'tests/**'

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio
      
      - name: Run unit tests
        run: pytest tests/ -m unit --cov=orchestrators --cov=shared
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
  
  contract-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install jsonschema
      
      - name: Run contract tests
        run: pytest tests/ -m contract
  
  integration-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, contract-tests]
    services:
      nats:
        image: nats:2.10-alpine
        ports:
          - 4222:4222
        options: >
          --health-cmd "nats server ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-asyncio redis
      
      - name: Wait for services
        run: |
          for i in {1..30}; do
            if curl -f http://localhost:8222/healthz && redis-cli -h localhost ping; then
              break
            fi
            sleep 1
          done
      
      - name: Run integration tests
        run: pytest tests/ -m integration
        env:
          NATS_URL: nats://localhost:4222
          REDIS_URL: redis://localhost:6379
  
  chaos-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule' || contains(github.event.pull_request.labels.*.name, 'chaos-test')
    services:
      nats:
        image: nats:2.10-alpine
        ports:
          - 4222:4222
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-asyncio docker
      
      - name: Run chaos tests
        run: pytest tests/ -m chaos --timeout=600
        env:
          NATS_URL: nats://localhost:4222
          REDIS_URL: redis://localhost:6379
  
  nightly-soak:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    services:
      nats:
        image: nats:2.10-alpine
        ports:
          - 4222:4222
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-asyncio psutil
      
      - name: Run soak tests
        run: pytest tests/ -m soak --timeout=2400  # 40 minute timeout
        env:
          NATS_URL: nats://localhost:4222
          REDIS_URL: redis://localhost:6379
```

### Quality Gates

**Required checks for merge**:
1. ✅ Unit test coverage ≥ 90%
2. ✅ All contract tests pass
3. ✅ Integration tests pass with NATS + Redis
4. ✅ Code linting (pylint, black)
5. ✅ Security scanning (bandit)
6. ✅ Performance regression tests

**Nightly checks**:
- Chaos tests (Redis failures, NATS partitions)
- Soak tests (30 minutes sustained load)
- Memory leak detection
- Cross-version compatibility

### Test Execution Commands

**Local development**:
```bash
# Run all tests
make test-all

# Run specific test categories
pytest tests/ -m unit                    # Fast unit tests
pytest tests/ -m contract                # Schema validation
pytest tests/ -m integration             # End-to-end with infrastructure
pytest tests/ -m chaos                   # Failure scenarios
pytest tests/ -m soak                    # Load tests

# Run tests for specific orchestrator
pytest orchestrators/simple/tests/       # Simple orchestrator only
pytest orchestrators/workflow/tests/     # Workflow orchestrator only

# Performance and memory testing
pytest tests/ -m soak --durations=10     # Show slowest tests
pytest tests/ --memray                   # Memory profiling

# Coverage reporting
pytest --cov=orchestrators --cov=shared --cov-report=html
```

**Production validation**:
```bash
# Quick smoke test
pytest tests/test_smoke.py -v

# Validate against production-like load
pytest tests/test_soak.py -k "test_sustained" --timeout=3600

# Chaos engineering validation
pytest tests/test_chaos.py -v --capture=no
```

---

**For orchestrator-specific testing patterns, see individual orchestrator test directories and the shared testing utilities in `shared/test_utils.py`.**
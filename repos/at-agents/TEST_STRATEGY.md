# Test Strategy - Agent Testing

**Comprehensive testing approach for trading agents from unit to soak tests.**

## Testing Philosophy

**Agent-first testing**: All tests validate that agents correctly process market signals, maintain contract compliance, and perform reliably under production conditions. The testing pyramid emphasizes fast feedback loops while ensuring system reliability.

**Test Categories**:
- **Unit tests**: Agent logic and message handling
- **Contract tests**: Schema compliance with at-core
- **Integration tests**: End-to-end NATS message flow
- **Soak tests**: Sustained load and performance validation
- **Chaos tests**: Failure scenarios and recovery

## Test Pyramid

```
    ┌─────────────┐
    │  Soak Tests  │  ← Production-like load
    └──────┬──────┘
          │
    ┌──────┴──────────┐
    │ Integration Tests │  ← Real NATS, full flow
    └────────┬────────┘
              │
    ┌─────────┴─────────────┐
    │    Contract Tests    │  ← Schema validation
    └───────────┬───────────┘
                 │
    ┌─────────────┴────────────────┐
    │         Unit Tests         │  ← Fast, isolated
    └──────────────────────────────┘
```

## Unit Tests

### Agent Logic Tests

**Test agent-specific processing logic in isolation**:

```python
# tests/test_momentum_logic.py
import pytest
from datetime import datetime
from agents.momentum.handler import MomentumHandler
from agents.momentum.config import MomentumConfig

class TestMomentumLogic:
    def setup_method(self):
        self.config = MomentumConfig()
        self.handler = MomentumHandler(self.config)
    
    def test_bullish_momentum_detection(self):
        """Test detection of bullish momentum conditions."""
        signal = {
            'corr_id': 'test_123',
            'instrument': 'EURUSD',
            'price': 1.1000,  # Above recent average
            'side': 'buy',
            'timestamp': '2024-01-15T10:30:00Z'
        }
        
        # Mock historical data showing uptrend
        self.handler._price_history = {
            'EURUSD': [1.0950, 1.0960, 1.0970, 1.0980, 1.0990]
        }
        
        result = await self.handler._process_signal(signal)
        
        assert result['analysis']['trend_direction'] == 'bullish'
        assert result['analysis']['momentum_strength'] > 0.6
        assert result['analysis']['confidence'] > 0.7
    
    def test_bearish_momentum_detection(self):
        """Test detection of bearish momentum conditions."""
        signal = {
            'corr_id': 'test_124',
            'instrument': 'EURUSD',
            'price': 1.0900,  # Below recent average
            'side': 'sell',
            'timestamp': '2024-01-15T10:30:00Z'
        }
        
        # Mock historical data showing downtrend
        self.handler._price_history = {
            'EURUSD': [1.1050, 1.1040, 1.1030, 1.1020, 1.1010]
        }
        
        result = await self.handler._process_signal(signal)
        
        assert result['analysis']['trend_direction'] == 'bearish'
        assert result['analysis']['momentum_strength'] > 0.6
    
    def test_sideways_market_detection(self):
        """Test handling of sideways/ranging markets."""
        signal = {
            'corr_id': 'test_125',
            'instrument': 'EURUSD',
            'price': 1.0975,
            'timestamp': '2024-01-15T10:30:00Z'
        }
        
        # Mock sideways price action
        self.handler._price_history = {
            'EURUSD': [1.0970, 1.0980, 1.0975, 1.0972, 1.0978]
        }
        
        result = await self.handler._process_signal(signal)
        
        assert result['analysis']['trend_direction'] == 'sideways'
        assert result['analysis']['momentum_strength'] < 0.4
    
    def test_insufficient_data_handling(self):
        """Test behavior when insufficient historical data."""
        signal = {
            'corr_id': 'test_126',
            'instrument': 'NEWPAIR',
            'price': 1.0000,
            'timestamp': '2024-01-15T10:30:00Z'
        }
        
        # No historical data
        self.handler._price_history = {}
        
        result = await self.handler._process_signal(signal)
        
        assert result['analysis']['trend_direction'] == 'unknown'
        assert result['analysis']['confidence'] < 0.5
    
    def test_correlation_id_preservation(self):
        """Test that correlation ID is preserved through processing."""
        signal = {
            'corr_id': 'unique_test_corr_id_789',
            'instrument': 'GBPUSD',
            'price': 1.2500,
            'timestamp': '2024-01-15T10:30:00Z'
        }
        
        result = await self.handler._process_signal(signal)
        
        assert result['corr_id'] == 'unique_test_corr_id_789'
    
    def test_agent_metadata_inclusion(self):
        """Test that agent metadata is included in output."""
        signal = {
            'corr_id': 'test_127',
            'instrument': 'BTCUSD',
            'price': 45000,
            'timestamp': '2024-01-15T10:30:00Z'
        }
        
        result = await self.handler._process_signal(signal)
        
        assert result['agent_name'] == 'momentum'
        assert 'agent_version' in result
        assert 'schema_version' in result
        assert 'enriched_at' in result
```

### Configuration Tests

```python
# tests/test_agent_config.py
import os
import pytest
from agents.momentum.config import MomentumConfig

class TestMomentumConfig:
    def test_default_configuration(self):
        """Test default configuration values."""
        config = MomentumConfig()
        
        assert config.nats_url == 'nats://localhost:4222'
        assert config.agent_name == 'momentum'
        assert config.lookback_periods == 20
        assert config.rsi_threshold_high == 70
        assert config.rsi_threshold_low == 30
    
    def test_environment_override(self):
        """Test configuration from environment variables."""
        os.environ['MOMENTUM_LOOKBACK_PERIODS'] = '50'
        os.environ['MOMENTUM_RSI_THRESHOLD_HIGH'] = '80'
        
        config = MomentumConfig()
        
        assert config.lookback_periods == 50
        assert config.rsi_threshold_high == 80
        
        # Cleanup
        del os.environ['MOMENTUM_LOOKBACK_PERIODS']
        del os.environ['MOMENTUM_RSI_THRESHOLD_HIGH']
    
    def test_invalid_configuration(self):
        """Test handling of invalid configuration values."""
        os.environ['MOMENTUM_LOOKBACK_PERIODS'] = 'invalid'
        
        with pytest.raises(ValueError):
            MomentumConfig()
        
        del os.environ['MOMENTUM_LOOKBACK_PERIODS']
```

### Error Handling Tests

```python
# tests/test_error_handling.py
class TestErrorHandling:
    def test_invalid_message_format(self):
        """Test handling of malformed messages."""
        handler = MomentumHandler(MomentumConfig())
        
        invalid_message = "not json"
        
        with pytest.raises(json.JSONDecodeError):
            await handler.handle_message_data(invalid_message)
    
    def test_missing_required_fields(self):
        """Test handling of messages missing required fields."""
        handler = MomentumHandler(MomentumConfig())
        
        incomplete_signal = {
            'corr_id': 'test_128'
            # Missing instrument, price, timestamp
        }
        
        with pytest.raises(ValidationError):
            await handler._validate_input(incomplete_signal)
    
    def test_processing_exception_handling(self):
        """Test graceful handling of processing exceptions."""
        handler = MomentumHandler(MomentumConfig())
        
        # Mock an exception in processing
        original_process = handler._calculate_momentum
        handler._calculate_momentum = lambda x: exec('raise Exception("Test error")')
        
        signal = {
            'corr_id': 'test_129',
            'instrument': 'EURUSD',
            'price': 1.1000,
            'timestamp': '2024-01-15T10:30:00Z'
        }
        
        with pytest.raises(Exception):
            await handler._process_signal(signal)
        
        # Restore original method
        handler._calculate_momentum = original_process
```

## Contract Tests

### Schema Validation Tests

**Ensure compliance with at-core schemas**:

```python
# tests/test_contract_compliance.py
import json
import pytest
from jsonschema import validate, ValidationError
from pathlib import Path

class TestContractCompliance:
    @classmethod
    def setup_class(cls):
        # Load schemas from at-core
        schema_path = Path('../at-core/schemas')
        
        with open(schema_path / 'signals.normalized.schema.json') as f:
            cls.input_schema = json.load(f)
    
    def test_valid_input_acceptance(self):
        """Test that agents accept valid normalized signals."""
        valid_signal = {
            'corr_id': 'test_contract_001',
            'source': 'tradingview',
            'instrument': 'EURUSD',
            'price': 1.0945,
            'side': 'buy',
            'strength': 0.75,
            'timestamp': '2024-01-15T10:30:00Z',
            'normalized_at': '2024-01-15T10:30:01Z'
        }
        
        # Should not raise exception
        validate(instance=valid_signal, schema=self.input_schema)
    
    def test_enriched_output_schema(self):
        """Test that agent output matches enriched schema."""
        handler = MomentumHandler(MomentumConfig())
        
        signal = {
            'corr_id': 'test_contract_002',
            'source': 'tradingview',
            'instrument': 'EURUSD',
            'price': 1.0945,
            'timestamp': '2024-01-15T10:30:00Z',
            'normalized_at': '2024-01-15T10:30:01Z'
        }
        
        result = await handler._process_signal(signal)
        
        # Validate against enriched schema
        required_fields = [
            'schema_version', 'agent_name', 'agent_version',
            'corr_id', 'source_signal', 'enriched_at', 'analysis'
        ]
        
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
        
        # Validate analysis structure
        analysis = result['analysis']
        momentum_fields = [
            'momentum_strength', 'trend_direction', 'confidence'
        ]
        
        for field in momentum_fields:
            assert field in analysis, f"Missing analysis field: {field}"
    
    def test_backwards_compatibility(self):
        """Test that agents handle older schema versions."""
        # Test with minimal required fields (v1.0.0 schema)
        minimal_signal = {
            'corr_id': 'test_contract_003',
            'source': 'test',
            'instrument': 'EURUSD',
            'price': 1.0945,
            'timestamp': '2024-01-15T10:30:00Z',
            'normalized_at': '2024-01-15T10:30:01Z'
        }
        
        handler = MomentumHandler(MomentumConfig())
        result = await handler._process_signal(minimal_signal)
        
        # Should process successfully
        assert result['corr_id'] == 'test_contract_003'
```

### Cross-Agent Contract Tests

```python
# tests/test_cross_agent_contracts.py
class TestCrossAgentContracts:
    def test_enriched_signal_compatibility(self):
        """Test that enriched signals can be consumed by other agents."""
        momentum_handler = MomentumHandler(MomentumConfig())
        risk_handler = RiskHandler(RiskConfig())
        
        # Original signal
        signal = {
            'corr_id': 'test_cross_001',
            'instrument': 'EURUSD',
            'price': 1.0945,
            'timestamp': '2024-01-15T10:30:00Z',
            'normalized_at': '2024-01-15T10:30:01Z'
        }
        
        # Process through momentum agent
        momentum_result = await momentum_handler._process_signal(signal)
        
        # Risk agent should be able to process original signal
        risk_result = await risk_handler._process_signal(signal)
        
        # Both should have same correlation ID
        assert momentum_result['corr_id'] == risk_result['corr_id']
        assert momentum_result['corr_id'] == signal['corr_id']
```

## Integration Tests

### End-to-End NATS Flow

**Test complete message flow with real NATS**:

```python
# tests/test_integration.py
import asyncio
import json
import pytest
from nats.aio.client import Client as NATS
from agents.momentum.agent import MomentumAgent

@pytest.mark.integration
class TestIntegration:
    @pytest.fixture
    async def nats_connection(self):
        """Set up NATS connection for testing."""
        nats = NATS()
        await nats.connect('nats://localhost:4222')
        js = nats.jetstream()
        
        yield js
        
        await nats.close()
    
    async def test_end_to_end_signal_processing(self, nats_connection):
        """Test complete signal processing flow."""
        js = nats_connection
        
        # Start momentum agent
        agent = MomentumAgent()
        agent_task = asyncio.create_task(agent.start())
        
        # Allow agent to start
        await asyncio.sleep(1)
        
        # Publish test signal
        test_signal = {
            'corr_id': 'integration_test_001',
            'source': 'test',
            'instrument': 'EURUSD',
            'price': 1.0945,
            'side': 'buy',
            'timestamp': '2024-01-15T10:30:00Z',
            'normalized_at': '2024-01-15T10:30:01Z'
        }
        
        await js.publish(
            subject='signals.normalized',
            payload=json.dumps(test_signal).encode()
        )
        
        # Subscribe to enriched output
        received_messages = []
        
        async def capture_message(msg):
            data = json.loads(msg.data.decode())
            received_messages.append(data)
            await msg.ack()
        
        await js.subscribe(
            subject='signals.enriched.momentum',
            cb=capture_message
        )
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Verify enriched signal was published
        assert len(received_messages) == 1
        enriched = received_messages[0]
        
        assert enriched['corr_id'] == 'integration_test_001'
        assert enriched['agent_name'] == 'momentum'
        assert 'analysis' in enriched
        
        # Clean up
        await agent.stop()
        agent_task.cancel()
    
    async def test_multiple_agents_parallel_processing(self, nats_connection):
        """Test multiple agents processing same signal."""
        js = nats_connection
        
        # Start multiple agents
        momentum_agent = MomentumAgent()
        risk_agent = RiskAgent()
        
        momentum_task = asyncio.create_task(momentum_agent.start())
        risk_task = asyncio.create_task(risk_agent.start())
        
        await asyncio.sleep(1)
        
        # Publish signal
        test_signal = {
            'corr_id': 'parallel_test_001',
            'source': 'test',
            'instrument': 'EURUSD',
            'price': 1.0945,
            'timestamp': '2024-01-15T10:30:00Z',
            'normalized_at': '2024-01-15T10:30:01Z'
        }
        
        await js.publish(
            subject='signals.normalized',
            payload=json.dumps(test_signal).encode()
        )
        
        # Collect outputs from both agents
        momentum_messages = []
        risk_messages = []
        
        async def capture_momentum(msg):
            data = json.loads(msg.data.decode())
            momentum_messages.append(data)
            await msg.ack()
        
        async def capture_risk(msg):
            data = json.loads(msg.data.decode())
            risk_messages.append(data)
            await msg.ack()
        
        await js.subscribe('signals.enriched.momentum', cb=capture_momentum)
        await js.subscribe('signals.enriched.risk', cb=capture_risk)
        
        await asyncio.sleep(3)
        
        # Verify both agents processed the signal
        assert len(momentum_messages) == 1
        assert len(risk_messages) == 1
        
        # Both should have same correlation ID
        assert momentum_messages[0]['corr_id'] == 'parallel_test_001'
        assert risk_messages[0]['corr_id'] == 'parallel_test_001'
        
        # Clean up
        await momentum_agent.stop()
        await risk_agent.stop()
        momentum_task.cancel()
        risk_task.cancel()
    
    async def test_error_recovery(self, nats_connection):
        """Test agent recovery from processing errors."""
        js = nats_connection
        
        # Start agent
        agent = MomentumAgent()
        agent_task = asyncio.create_task(agent.start())
        await asyncio.sleep(1)
        
        # Send invalid signal (should cause processing error)
        invalid_signal = {
            'corr_id': 'error_test_001',
            'invalid_field': 'bad_data'
        }
        
        await js.publish(
            subject='signals.normalized',
            payload=json.dumps(invalid_signal).encode()
        )
        
        # Send valid signal after error
        valid_signal = {
            'corr_id': 'error_test_002',
            'source': 'test',
            'instrument': 'EURUSD',
            'price': 1.0945,
            'timestamp': '2024-01-15T10:30:00Z',
            'normalized_at': '2024-01-15T10:30:01Z'
        }
        
        await js.publish(
            subject='signals.normalized',
            payload=json.dumps(valid_signal).encode()
        )
        
        # Verify agent recovers and processes valid signal
        received_messages = []
        
        async def capture_message(msg):
            data = json.loads(msg.data.decode())
            received_messages.append(data)
            await msg.ack()
        
        await js.subscribe('signals.enriched.momentum', cb=capture_message)
        await asyncio.sleep(3)
        
        # Should only receive the valid signal output
        assert len(received_messages) == 1
        assert received_messages[0]['corr_id'] == 'error_test_002'
        
        # Clean up
        await agent.stop()
        agent_task.cancel()
```

## Soak Tests

### Sustained Load Testing

**Test agents under production-like load for extended periods**:

```python
# tests/test_soak.py
import asyncio
import json
import time
import pytest
from nats.aio.client import Client as NATS
from agents.momentum.agent import MomentumAgent

@pytest.mark.soak
class TestSoakTesting:
    async def test_sustained_message_processing(self):
        """Test agent under sustained 1k msg/sec for 10 minutes."""
        nats = NATS()
        await nats.connect('nats://localhost:4222')
        js = nats.jetstream()
        
        # Start agent
        agent = MomentumAgent()
        agent_task = asyncio.create_task(agent.start())
        await asyncio.sleep(2)
        
        # Test parameters
        target_rate = 1000  # messages per second
        test_duration = 600  # 10 minutes
        total_messages = target_rate * test_duration
        
        # Track metrics
        start_time = time.time()
        messages_sent = 0
        messages_received = 0
        processing_times = []
        
        async def capture_outputs(msg):
            nonlocal messages_received
            data = json.loads(msg.data.decode())
            
            # Calculate processing time
            sent_time = float(data['corr_id'].split('_')[-1])
            receive_time = time.time()
            processing_time = receive_time - sent_time
            processing_times.append(processing_time)
            
            messages_received += 1
            await msg.ack()
        
        await js.subscribe('signals.enriched.momentum', cb=capture_outputs)
        
        # Send messages at target rate
        message_interval = 1.0 / target_rate
        
        while time.time() - start_time < test_duration:
            current_time = time.time()
            
            signal = {
                'corr_id': f'soak_test_{messages_sent}_{current_time}',
                'source': 'test',
                'instrument': 'EURUSD',
                'price': 1.0945 + (messages_sent % 100) * 0.0001,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'normalized_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            
            await js.publish(
                subject='signals.normalized',
                payload=json.dumps(signal).encode()
            )
            
            messages_sent += 1
            
            # Rate limiting
            await asyncio.sleep(message_interval)
        
        # Allow processing to complete
        await asyncio.sleep(30)
        
        # Verify performance metrics
        actual_duration = time.time() - start_time
        actual_rate = messages_sent / actual_duration
        processing_rate = messages_received / actual_duration
        
        # Calculate statistics
        avg_processing_time = sum(processing_times) / len(processing_times)
        p95_processing_time = sorted(processing_times)[int(0.95 * len(processing_times))]
        
        # Assertions
        assert actual_rate >= target_rate * 0.95, f"Send rate too low: {actual_rate}"
        assert processing_rate >= target_rate * 0.95, f"Processing rate too low: {processing_rate}"
        assert avg_processing_time < 0.1, f"Average processing time too high: {avg_processing_time}"
        assert p95_processing_time < 0.2, f"P95 processing time too high: {p95_processing_time}"
        assert messages_received >= messages_sent * 0.99, "Message loss detected"
        
        # Clean up
        await agent.stop()
        agent_task.cancel()
        await nats.close()
    
    async def test_memory_leak_detection(self):
        """Test for memory leaks during extended operation."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        nats = NATS()
        await nats.connect('nats://localhost:4222')
        js = nats.jetstream()
        
        agent = MomentumAgent()
        agent_task = asyncio.create_task(agent.start())
        await asyncio.sleep(2)
        
        # Send messages for 30 minutes
        test_duration = 1800  # 30 minutes
        start_time = time.time()
        message_count = 0
        
        while time.time() - start_time < test_duration:
            signal = {
                'corr_id': f'memory_test_{message_count}',
                'source': 'test',
                'instrument': 'EURUSD',
                'price': 1.0945,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'normalized_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            
            await js.publish(
                subject='signals.normalized',
                payload=json.dumps(signal).encode()
            )
            
            message_count += 1
            await asyncio.sleep(0.1)  # 10 msg/sec
            
            # Check memory every 5 minutes
            if message_count % 3000 == 0:
                current_memory = process.memory_info().rss
                memory_growth = (current_memory - initial_memory) / 1024 / 1024  # MB
                
                # Memory growth should be < 100MB
                assert memory_growth < 100, f"Memory leak detected: {memory_growth}MB growth"
        
        final_memory = process.memory_info().rss
        total_growth = (final_memory - initial_memory) / 1024 / 1024
        
        # Final memory check
        assert total_growth < 200, f"Excessive memory growth: {total_growth}MB"
        
        await agent.stop()
        agent_task.cancel()
        await nats.close()
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
    --cov=agents
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=85
markers =
    unit: Fast unit tests
    contract: Schema contract tests
    integration: Integration tests requiring NATS
    soak: Long-running load tests
    chaos: Failure scenario tests
```

### GitHub Actions Workflow

**.github/workflows/agent-tests.yml**:
```yaml
name: Agent Tests

on:
  pull_request:
    paths:
      - 'agents/**'
      - 'tests/**'
      - 'shared/**'

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
        run: pytest tests/ -m unit --cov=agents
      
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
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-asyncio
      
      - name: Wait for NATS
        run: |
          for i in {1..30}; do
            if curl -f http://localhost:8222/healthz; then
              break
            fi
            sleep 1
          done
      
      - name: Run integration tests
        run: pytest tests/ -m integration
        env:
          NATS_URL: nats://localhost:4222
```

### Quality Gates

**Required checks before merge**:
1. ✅ Unit test coverage ≥ 85%
2. ✅ All contract tests pass
3. ✅ Integration tests pass with NATS
4. ✅ Code linting (pylint, black)
5. ✅ Security scanning (bandit)
6. ✅ Performance regression tests

**Optional checks for production releases**:
- Soak tests under sustained load
- Chaos engineering tests
- Cross-agent compatibility tests
- Load balancing and failover tests

### Test Execution Commands

**Local development**:
```bash
# Run all tests
make test-all

# Run specific test categories
pytest tests/ -m unit                    # Fast unit tests
pytest tests/ -m contract                # Schema validation
pytest tests/ -m integration             # End-to-end with NATS
pytest tests/ -m "soak and not slow"     # Quick load tests

# Run tests for specific agent
pytest agents/momentum/tests/            # Momentum agent only
pytest agents/risk/tests/                # Risk agent only

# Performance testing
pytest tests/ -m soak --durations=10     # Long-running tests

# Coverage reporting
pytest --cov=agents --cov-report=html
```

**Continuous testing**:
```bash
# Watch mode for development
ptw tests/ -m unit                       # Rerun on file changes

# Parallel execution
pytest tests/ -n auto                    # Use all CPU cores

# Stress testing
for i in {1..100}; do pytest tests/test_integration.py; done
```

---

**For agent-specific testing patterns, see individual agent test directories and the shared testing utilities in `shared/test_utils.py`.**
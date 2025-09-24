# Execution Simulator Test Strategy

## Test Matrix

| Test Area | Test Case | Expected Result | Error Code | Metrics Asserted | Notes |
|-----------|-----------|-----------------|------------|-------------------|-------|
| Event Processing | Valid order intent event | Fill and reconcile events published | - | `exec_sim_orders_received_total{status="success"}`, `exec_sim_fills_generated_total{fill_type="full"}` | Happy path processing |
| Event Processing | Partial fill simulation | Partial fill event with reduced quantity | - | `exec_sim_fills_generated_total{fill_type="partial"}`, `exec_sim_simulation_results_total{result="partial_fill"}` | Configurable probability |
| Schema Validation | Missing required fields | No fill events generated | EXEC-001 | `exec_sim_validation_errors_total{type="schema"}`, `exec_sim_orders_received_total{status="validation_error"}` | Order intent missing corr_id |
| Schema Validation | Invalid field types | No fill events generated | EXEC-001 | Same as above | Quantity as string instead of number |
| Schema Validation | Invalid instrument format | No fill events generated | EXEC-001 | `exec_sim_validation_errors_total{type="instrument"}` | Malformed instrument identifier |
| Correlation ID | Missing correlation ID | Synthetic ID generated, processing continues | EXEC-003 | `exec_sim_validation_errors_total{type="correlation_id"}` | Fallback behavior |
| Correlation ID | Duplicate correlation ID | Identical fill generated (idempotent) | - | Same fill_id and values returned | Prevents duplicate executions |
| NATS Integration | NATS publishing failure | Event buffered for retry | EXEC-002 | `exec_sim_nats_publish_errors_total{subject="executions.fill"}` | Cannot publish to NATS |
| NATS Integration | NATS consumer lag | Graceful degradation | - | `exec_sim_pending_events_count` increases | High event volume handling |
| Simulation Logic | Market order slippage | Fill price includes simulated slippage | - | `exec_sim_simulation_duration_seconds` recorded | Realistic execution simulation |
| Simulation Logic | Execution delay simulation | Fill timestamp after order timestamp | - | Delay within min/max range configured | Timing simulation |
| Health Check | NATS connected | Health returns ok:true, nats:"connected" | - | - | Normal operation status |
| Health Check | NATS disconnected | Health returns ok:false, nats:"disconnected" | - | - | Degraded operation status |
| Health Check | High pending events | Health shows pending_events count | - | `exec_sim_pending_events_count` | Buffer monitoring |

## Unit Tests

### Event Validation (test_validation.py)
```python
def test_valid_order_intent():
    # Test schema validation with complete order intent
    # Assert successful validation and processing

def test_missing_correlation_id():
    # Test handling of order intent without corr_id
    # Assert synthetic ID generation and warning log

def test_invalid_instrument_format():
    # Test rejection of malformed instrument identifiers
    # Assert EXEC-001 error and metrics increment

def test_invalid_quantity_type():
    # Test rejection of non-numeric quantity values
    # Assert schema validation failure

def test_missing_required_fields():
    # Test rejection when required fields absent
    # Assert validation error and no downstream processing
```

### Simulation Logic (test_simulation.py)
```python
def test_full_fill_simulation():
    # Test complete order fill scenario
    # Assert quantity_filled equals quantity_requested

def test_partial_fill_simulation():
    # Test partial fill with configurable probability
    # Assert quantity_filled < quantity_requested

def test_market_order_slippage():
    # Test slippage application to market orders
    # Assert fill_price differs from market_price within bounds

def test_limit_order_no_slippage():
    # Test that limit orders execute at specified price
    # Assert fill_price equals limit_price

def test_execution_delay_simulation():
    # Test realistic execution timing
    # Assert fill_timestamp after order_timestamp within delay range

def test_simulation_determinism():
    # Test that same input produces same output (for given seed)
    # Assert idempotent behavior for duplicate orders
```

### NATS Integration (test_nats.py)
```python
def test_order_intent_consumption():
    # Test consuming order intent events from NATS
    # Assert correct subject subscription and message parsing

def test_fill_event_publishing():
    # Test publishing fill events to executions.fill subject
    # Assert correct event structure and correlation ID propagation

def test_reconcile_event_publishing():
    # Test publishing reconcile events to executions.reconcile subject
    # Assert position delta and reconcile metadata

def test_nats_connection_failure():
    # Test behavior when NATS is unavailable
    # Assert event buffering and retry logic

def test_event_buffering():
    # Test in-memory buffering during NATS outages
    # Assert buffer size limits and overflow handling

def test_correlation_id_propagation():
    # Test correlation ID flows from input to output events
    # Assert same corr_id in order intent, fill, and reconcile
```

### Metrics and Observability (test_metrics.py)
```python
def test_success_metrics():
    # Test metrics incremented for successful processing
    # Assert exec_sim_orders_received_total{status="success"}

def test_error_metrics():
    # Test metrics incremented for validation failures
    # Assert exec_sim_validation_errors_total counters

def test_duration_metrics():
    # Test simulation duration histogram recording
    # Assert exec_sim_simulation_duration_seconds values

def test_pending_events_gauge():
    # Test pending events gauge accuracy
    # Assert exec_sim_pending_events_count reflects buffer state

def test_nats_error_metrics():
    # Test NATS publishing error metrics
    # Assert exec_sim_nats_publish_errors_total increments
```

## Contract Tests

### Schema Compliance (test_schemas.py)
```python
def test_order_intent_schema_validation():
    # Test strict validation against at-core schemas
    # Use real schema files from at-core repository

def test_fill_event_schema_compliance():
    # Test generated fill events match expected schema
    # Assert all required fields present and correctly typed

def test_reconcile_event_schema_compliance():
    # Test generated reconcile events match expected schema
    # Assert position tracking fields accurate

def test_schema_version_compatibility():
    # Test handling of different schema versions
    # Assert backward compatibility during migrations
```

### NATS Subject Contracts (test_subjects.py)
```python
def test_order_intent_subject_subscription():
    # Test subscription to correct NATS subject
    # Assert decisions.order_intent subject consumption

def test_fill_event_subject_publishing():
    # Test publishing to correct fill subject
    # Assert executions.fill subject publication

def test_reconcile_event_subject_publishing():
    # Test publishing to correct reconcile subject
    # Assert executions.reconcile subject publication

def test_subject_configuration():
    # Test subject names configurable via environment
    # Assert NATS_SUBJECT_* environment variables respected
```

## Integration Tests

### End-to-End Processing (test_e2e.py)
```python
def test_complete_execution_flow():
    # Test full order intent -> fill -> reconcile flow
    # Assert events published to NATS with correct timing

def test_multiple_concurrent_orders():
    # Test handling multiple order intents simultaneously
    # Assert correct processing without race conditions

def test_different_instrument_types():
    # Test processing orders for various instruments (FX, crypto, stocks)
    # Assert instrument-specific simulation parameters

def test_order_type_handling():
    # Test different order types (market, limit, stop)
    # Assert appropriate simulation logic for each type
```

### NATS Integration (test_nats_integration.py)
```python
def test_nats_jetstream_integration():
    # Test integration with NATS JetStream
    # Require real NATS server for integration test environment

def test_durable_consumer_behavior():
    # Test durable consumer creation and message acknowledgment
    # Assert no message loss during service restarts

def test_nats_reconnection():
    # Test automatic reconnection after NATS failure
    # Assert service recovery and buffered event processing

def test_consumer_lag_handling():
    # Test behavior under high message volume
    # Assert graceful degradation and backpressure
```

### Performance Tests (test_performance.py)
```python
def test_throughput_capacity():
    # Test sustained processing rate
    # Assert >1000 orders/second processing capacity

def test_memory_usage_stability():
    # Test memory usage under sustained load
    # Assert no memory leaks during extended operation

def test_latency_distribution():
    # Test simulation latency percentiles
    # Assert p95 latency within acceptable bounds

def test_concurrent_processing():
    # Test multi-threaded processing if implemented
    # Assert thread safety and correct event ordering
```

## Soak Tests

### Extended Operation (test_soak.py)
```python
def test_24_hour_operation():
    # Test continuous operation for 24 hours
    # Assert stable performance and resource usage

def test_high_volume_sustained():
    # Test sustained high-volume processing
    # Send 10M orders over 24 hours, assert consistent performance

def test_memory_leak_detection():
    # Test for memory leaks during extended operation
    # Assert memory usage remains stable over time

def test_nats_stability():
    # Test NATS connection stability over extended periods
    # Assert automatic recovery from intermittent failures
```

### Failure Scenarios (test_failure_scenarios.py)
```python
def test_nats_outage_recovery():
    # Test recovery from extended NATS outages
    # Simulate 10-minute NATS downtime, assert full recovery

def test_partial_nats_failure():
    # Test handling of publishing failures while consuming succeeds
    # Assert proper buffering and retry behavior

def test_high_error_rate_handling():
    # Test resilience to high validation error rates
    # Send 50% invalid orders, assert service stability

def test_resource_exhaustion():
    # Test behavior when approaching resource limits
    # Assert graceful degradation before failure
```

## Test Environment Setup

### Dependencies
```bash
# Required for integration tests
docker compose -f ../../docker-compose.dev.yml up -d nats

# Python test dependencies
pip install pytest pytest-asyncio pytest-mock pytest-benchmark
pip install testcontainers  # For containerized NATS in tests
```

### Test Configuration
```python
# test_config.py
NATS_URL_TEST = "nats://localhost:4222"
NATS_STREAM_TEST = "trading-events-test"
TEST_TIMEOUT_SEC = 30
SOAK_TEST_DURATION_SEC = 86400  # 24 hours
HIGH_VOLUME_ORDERS_COUNT = 10_000_000
```

### Test Data
```python
# test_fixtures.py
VALID_ORDER_INTENT = {
    "corr_id": "test_123",
    "agent_id": "test_agent",
    "instrument": "EURUSD",
    "side": "buy",
    "quantity": 10000,
    "order_type": "market",
    "timestamp": "2024-01-15T10:30:00Z"
}

INVALID_ORDER_INTENTS = [
    # Missing corr_id
    {"agent_id": "test", "instrument": "EURUSD", ...},
    # Invalid quantity type
    {"corr_id": "test", "quantity": "invalid", ...},
    # Malformed instrument
    {"corr_id": "test", "instrument": "INVALID", ...}
]
```

## Test Execution Strategy

### CI/CD Pipeline
1. **Unit Tests**: Run on every commit (fast feedback)
2. **Contract Tests**: Run on pull requests (schema compliance)
3. **Integration Tests**: Run on main branch merges (NATS integration)
4. **Performance Tests**: Run nightly (capacity verification)
5. **Soak Tests**: Run weekly (stability verification)

### Test Parallelization
- Unit tests: Parallel execution per test module
- Integration tests: Sequential (shared NATS instance)
- Performance tests: Isolated environment required
- Soak tests: Dedicated infrastructure for extended runs

### Coverage Targets
- **Unit Tests**: >95% code coverage
- **Contract Tests**: 100% schema field coverage
- **Integration Tests**: All NATS integration paths
- **Performance Tests**: All major execution scenarios
# Gateway Test Strategy

## Test Matrix

| Test Area | Test Case | Expected Status | Error Code | Metrics Asserted | Notes |
|-----------|-----------|-----------------|------------|-------------------|-------|
| Authentication | Valid HMAC signature | 202 | - | `gateway_webhooks_received_total{status="2xx"}` | Happy path |
| Authentication | Invalid signature | 401 | GW-001 | `gateway_validation_errors_total{type="signature"}`, `gateway_webhook_duration_seconds{status_class="4xx"}` | Bad HMAC |
| Authentication | Malformed signature header | 401 | GW-001 | Same as above | Missing "sha256=" prefix |
| Replay Protection | Timestamp >300s old | 401 | GW-002 | `gateway_validation_errors_total{type="replay"}`, `gateway_webhook_duration_seconds{status_class="4xx"}` | Outside REPLAY_WINDOW_SEC |
| Replay Protection | Reused nonce | 401 | GW-002 | Same as above | Duplicate nonce within window |
| Source Validation | Disallowed source | 400 | GW-007 | `gateway_validation_errors_total{type="source"}`, `gateway_webhook_duration_seconds{status_class="4xx"}` | Not in ALLOWED_SOURCES |
| Payload Size | Body >1MB | 413 | GW-008 | `gateway_validation_errors_total{type="size"}`, `gateway_webhook_duration_seconds{status_class="4xx"}` | Exceed max size |
| Schema Validation | Missing required fields | 422 | GW-003 | `gateway_validation_errors_total{type="schema"}`, `gateway_webhook_duration_seconds{status_class="4xx"}` | TradingView missing "ticker" |
| Schema Validation | Invalid field types | 422 | GW-003 | Same as above | Price as string instead of number |
| Idempotency | Duplicate same payload | 202 | - | Same `corr_id` returned | Idempotent behavior |
| Idempotency | Duplicate key different payload | 409 | GW-006 | `gateway_idempotency_conflicts_total`, `gateway_webhook_duration_seconds{status_class="4xx"}` | Key collision |
| Rate Limiting | Exceed RATE_LIMIT_RPS | 429 | GW-004 | `gateway_rate_limit_exceeded_total{source}`, `gateway_webhook_duration_seconds{status_class="4xx"}` | Include Retry-After header |
| NATS Integration | NATS unavailable | 503 | GW-005 | `gateway_nats_errors_total{type="connection"}`, `gateway_webhook_duration_seconds{status_class="5xx"}` | Cannot publish events |
| Maintenance Mode | MAINTENANCE_MODE=true | 503 | GW-011 | `gateway_maintenance_mode_total`, `gateway_webhook_duration_seconds{status_class="5xx"}` | Include Retry-After header |
| Health Check | NATS connected | 200 | - | - | nats: "connected" |
| Health Check | NATS degraded | 200 | - | - | nats: "degraded" |
| Health Check | NATS disconnected | 200 | - | - | nats: "disconnected" |

## Unit Tests

### Authentication (test_signature.py)
```python
def test_valid_hmac_signature():
    # Test HMAC-SHA256 verification with known inputs
    # Assert 202 response with valid corr_id

def test_invalid_signature():
    # Test rejection of incorrect HMAC
    # Assert 401 GW-001 with proper error shape

def test_malformed_signature_header():
    # Test missing "sha256=" prefix
    # Assert 401 GW-001

def test_missing_signature_header():
    # Test completely missing X-Signature
    # Assert 401 GW-001
```

### Replay Protection (test_replay.py)
```python
def test_timestamp_within_window():
    # Test valid timestamp within REPLAY_WINDOW_SEC
    # Assert 202 response

def test_timestamp_too_old():
    # Test timestamp >REPLAY_WINDOW_SEC old
    # Assert 401 GW-002

def test_timestamp_too_future():
    # Test timestamp >30s in future (clock skew)
    # Assert 401 GW-002

def test_nonce_reuse():
    # Test same nonce within replay window
    # Assert 401 GW-002

def test_nonce_expiration():
    # Test nonce cache cleanup after REPLAY_WINDOW_SEC
    # Assert nonce can be reused after TTL
```

### Idempotency (test_idempotency.py)
```python
def test_key_derivation():
    # Test automatic key generation from source+instrument+timestamp
    # Verify deterministic output

def test_duplicate_detection():
    # Test 202 for duplicate with same payload
    # Assert same corr_id returned

def test_key_conflict():
    # Test 409 for same key with different payload
    # Assert GW-006 error code

def test_key_expiration():
    # Test key cleanup after IDEMPOTENCY_TTL_SEC
    # Assert key can be reused after TTL
```

### Rate Limiting (test_rate_limit.py)
```python
def test_rate_limit_enforcement():
    # Send requests exceeding RATE_LIMIT_RPS
    # Assert 429 GW-004 with Retry-After header

def test_rate_limit_recovery():
    # Test normal operation after rate limit reset
    # Assert 202 responses resume

def test_per_source_limiting():
    # Test rate limits applied per source
    # Assert one source blocked doesn't affect others
```

### Normalization (test_normalization.py)
```python
def test_tradingview_mapping():
    # Test TradingView → signals.normalized conversion
    # Assert field mappings: ticker→instrument, action→side, etc.

def test_generic_passthrough():
    # Test generic webhook handling
    # Assert payload preserved in normalized event

def test_missing_optional_fields():
    # Test behavior with optional fields absent
    # Assert graceful handling, no crashes

def test_normalization_failure():
    # Test invalid data causing normalization error
    # Assert 500 GW-009
```

### Error Response Format (test_error_shapes.py)
```python
def test_401_error_shape():
    # Test GW-001 response matches API_SPEC schema
    # Assert: error, code, message, corr_id, timestamp, details

def test_422_error_shape():
    # Test GW-003 response with validation_errors in details

def test_429_error_shape():
    # Test GW-004 response with rate limit details and Retry-After

def test_503_error_shape():
    # Test GW-005 and GW-011 response formats
```

## Contract Tests

### Schema Validation (test_signals_raw_schema.py)
```python
def test_signals_raw_schema_compliance():
    # Validate emitted signals.raw events against at-core schema
    # Assert all required fields present with correct types

def test_signals_raw_correlation_id():
    # Verify corr_id propagation from request to event

def test_signals_raw_idempotency_key():
    # Verify idempotency_key included in event
```

### Schema Validation (test_signals_normalized_schema.py)
```python
def test_signals_normalized_schema_compliance():
    # Validate emitted signals.normalized events against at-core schema
    # Assert normalization produces valid canonical format

def test_signals_normalized_field_mapping():
    # Verify TradingView fields correctly mapped
    # Assert: ticker→instrument, time→timestamp, etc.

def test_signals_normalized_source_addition():
    # Verify source="tradingview" added automatically
    # Assert normalized_at timestamp present
```

### Backward Compatibility (test_backward_compat.py)
```python
def test_schema_evolution_compatibility():
    # Load previous schema version from at-core
    # Verify current events still validate against older schemas
    # Skip if no previous versions exist

def test_optional_field_addition():
    # Test that new optional fields don't break old consumers
    # Generate events with and without new fields
```

### Golden Samples
**Location**: `tests/fixtures/`
- `tradingview_valid.json`: Valid TradingView webhook samples
- `tradingview_invalid.json`: Invalid payloads for negative testing
- `generic_valid.json`: Valid generic webhook samples
- `generic_invalid.json`: Invalid generic payloads
- `normalized_expected.json`: Expected normalization outputs
- `schema_samples/`: Reference events for contract testing

## Integration Tests

### NATS Integration (test_webhook_to_nats.py)
**Setup**: Use testcontainers with JetStream-enabled NATS

```python
@pytest.fixture
def nats_container():
    # Start NATS with JetStream in test container
    # Configure stream and subjects for testing

def test_webhook_publishes_events(nats_container):
    # POST valid webhook → verify exactly one signals.raw and one signals.normalized published
    # Assert events contain expected fields and corr_id

def test_correlation_id_propagation(nats_container):
    # Verify corr_id flows from HTTP request to NATS event headers

def test_event_ordering(nats_container):
    # Verify signals.raw published before signals.normalized
```

### Idempotency Integration (test_idempotency_integration.py)
```python
def test_duplicate_requests_single_publish(nats_container):
    # Send same payload twice → verify only one NATS event published
    # Assert second request returns same corr_id

def test_different_payload_same_key_conflict(nats_container):
    # Test 409 response for key reuse with different data
    # Assert no NATS events published for conflicted request
```

### NATS Outage (test_nats_outage.py)
```python
def test_nats_unavailable_503_response(nats_container):
    # Stop NATS container → test 503 GW-005 response
    # Assert proper error format and no crashes

def test_nats_recovery_after_outage(nats_container):
    # Stop NATS, send requests (get 503), restart NATS, verify recovery
    # Assert 202 responses resume after reconnection

def test_buffering_during_outage():
    # Test in-memory buffering behavior when NATS unavailable
    # Assert buffer limits respected (1000 messages)
```

## Soak Tests

### Sustained Load (test_sustained_load.py)

#### Test Configuration
- **Duration**: 5-10 minutes
- **Target RPS**: 80% of `RATE_LIMIT_RPS` (e.g., 80 RPS if limit is 100)
- **Payload Mix**: 60% TradingView, 40% generic webhooks
- **Authentication**: Valid signatures with realistic timing variation

#### Fault Injection Scenarios
```python
def test_nats_outage_during_load():
    # Start sustained load → pause NATS for 30-60s → resume
    # Expect: temporary 503s, no crashes, recovery within 60s

def test_rate_limit_spike_handling():
    # Burst to 150% of rate limit mid-test
    # Expect: 429 responses, then recovery

def test_memory_stability_under_load():
    # Monitor memory usage throughout test
    # Assert: no continuous growth >10MB/hour
```

#### Pass Criteria
- **Response latency**: p95 <100ms, p99 <500ms
- **Error rate**: <0.5% for valid requests (excluding fault injection periods)
- **Memory usage**: Stable, no continuous growth
- **NATS consumer lag**: <100 messages after recovery
- **Recovery time**: <60s after NATS restoration

#### Monitoring During Soak
- **Metrics collection**: Sample every 5s during test
- **Log analysis**: Verify structured logging continues under load
- **Resource usage**: CPU <80%, memory stable
- **Circuit breaker**: No false positives during normal operation

## Test Fixtures

### Environment Configuration
**File**: `tests/fixtures/.env.test.example`
```
# Gateway Configuration
PORT=8001
LOG_LEVEL=DEBUG
SERVICE_NAME=at-gateway-test

# Authentication
API_KEY_HMAC_SECRET=test-secret-256-bits-long-for-testing-only-12345678

# NATS Configuration
NATS_URL=nats://localhost:4223
NATS_STREAM=test-trading-events
NATS_SUBJECT_SIGNALS_RAW=signals.raw
NATS_SUBJECT_SIGNALS_NORMALIZED=signals.normalized
NATS_DURABLE=test-gateway-consumer

# Rate Limiting
RATE_LIMIT_RPS=1000
ALLOWED_SOURCES=tradingview,test,generic

# Security
REPLAY_WINDOW_SEC=60
IDEMPOTENCY_TTL_SEC=300

# Testing
MAINTENANCE_MODE=false
```

### Sample Payloads
**TradingView Valid** (`tradingview_valid.json`):
```json
[
  {
    "ticker": "EURUSD",
    "action": "buy",
    "price": 1.0945,
    "time": "2024-01-15T10:30:00Z",
    "strategy": "test_momentum",
    "strength": 0.75
  },
  {
    "ticker": "BTCUSD",
    "action": "sell",
    "price": 45000.0,
    "time": "2024-01-15T10:31:00Z"
  }
]
```

**TradingView Invalid** (`tradingview_invalid.json`):
```json
[
  {
    "action": "buy",
    "price": 1.0945,
    "time": "2024-01-15T10:30:00Z"
  },
  {
    "ticker": "EURUSD",
    "action": "invalid_action",
    "price": -1.0,
    "time": "not-iso8601"
  }
]
```

**Generic Valid** (`generic_valid.json`):
```json
[
  {
    "source": "test",
    "instrument": "GBPUSD",
    "timestamp": "2024-01-15T10:30:00Z",
    "payload": {
      "price": 1.2650,
      "volume": 1000,
      "signal_type": "breakout"
    }
  }
]
```

### Test Helpers
**File**: `tests/helpers/auth.py`
```python
import hashlib
import hmac
from datetime import datetime
from uuid import uuid4

def generate_test_signature(body: str, secret: str) -> dict:
    """Generate valid authentication headers for testing."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    nonce = str(uuid4())
    signature = hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": f"sha256={signature}",
        "Content-Type": "application/json; charset=utf-8"
    }
```

## Observability Assertions

For each test case, verify observability data:

### Metrics Verification
```python
def assert_metrics_incremented(test_case, expected_metrics):
    """Verify expected metrics were incremented during test."""
    # Check counter increments
    # Verify histogram recordings with correct labels
    # Assert status_class labels match HTTP response
```

### Log Verification
```python
def assert_structured_logs(test_case, expected_fields):
    """Verify structured logs contain required fields."""
    # Check corr_id presence
    # Verify client_ip logged
    # Assert error details match ERROR_CATALOG expectations
```

## Pytest Layout

```
tests/
├── unit/
│   ├── test_signature.py
│   ├── test_replay.py
│   ├── test_idempotency.py
│   ├── test_rate_limit.py
│   ├── test_normalization.py
│   └── test_error_shapes.py
├── contract/
│   ├── test_signals_raw_schema.py
│   ├── test_signals_normalized_schema.py
│   └── test_backward_compat.py
├── integration/
│   ├── test_webhook_to_nats.py
│   ├── test_idempotency_integration.py
│   └── test_nats_outage.py
├── soak/
│   └── test_sustained_load.py
├── fixtures/
│   ├── tradingview_valid.json
│   ├── tradingview_invalid.json
│   ├── generic_valid.json
│   ├── generic_invalid.json
│   ├── normalized_expected.json
│   ├── .env.test.example
│   └── schema_samples/
│       ├── signals_raw_v1.0.0.json
│       └── signals_normalized_v1.0.0.json
└── helpers/
    ├── auth.py
    ├── nats.py
    └── metrics.py
```

## Make Targets

```makefile
# Unit tests - fast feedback
test-unit:
	pytest tests/unit/ -v --tb=short

# Contract tests - schema validation
test-contract:
	pytest tests/contract/ -v

# Integration tests - requires infrastructure
test-integration:
	docker compose -f docker-compose.test.yml up -d
	pytest tests/integration/ -v
	docker compose -f docker-compose.test.yml down

# Soak tests - extended duration
test-soak:
	docker compose -f docker-compose.test.yml up -d
	pytest tests/soak/ -v --duration=600 --tb=line
	docker compose -f docker-compose.test.yml down

# All tests except soak
test-all:
	make test-unit test-contract test-integration

# Quick iteration on specific endpoint
test-webhook:
	pytest tests/ -k "webhook" -v --maxfail=1 -x

# Coverage report
test-coverage:
	pytest tests/unit/ tests/contract/ --cov=at_gateway --cov-report=html

# Performance baseline
test-perf:
	pytest tests/soak/ -v --benchmark-only --benchmark-save=baseline
```

## CI/CD Gates

### Required for PR Merge
- **Unit tests**: 100% pass rate
- **Contract tests**: 100% pass rate, schema compliance verified
- **Error shape tests**: All error responses match API_SPEC.md schema
- **Code coverage**: >90% line coverage
- **Linting**: pylint score >8.0, black formatting enforced
- **Type checking**: mypy passes with no errors
- **Contract drift check**: Emitted events validate against at-core schemas

### Nightly CI
- **Integration tests**: Run against ephemeral NATS infrastructure
- **Coverage upload**: Send coverage reports to monitoring
- **Performance regression**: Compare latency against baseline
- **Security scanning**: Check dependencies for vulnerabilities

### Weekly CI
- **Extended soak test**: 30-minute run with fault injection
- **Memory profiling**: Generate heap dumps and analyze growth
- **Load test reporting**: Produce latency percentiles and error summaries
- **Contract compatibility**: Test against multiple at-core schema versions

### Contract Drift Detection
```python
# Fail CI if event structure changes without schema update
def test_event_schema_compatibility():
    # Load current at-core schemas
    # Generate sample events from gateway
    # Assert events validate against schemas
    # Fail if validation errors occur
```

## Developer Tips

### Fast Iteration
```bash
# Run specific test during development
pytest tests/unit/test_signature.py::test_valid_hmac_signature -v -s

# Run tests matching pattern
pytest -k "signature or replay" --maxfail=1 -x

# Debug mode with local gateway
LOG_LEVEL=DEBUG uvicorn at_gateway.app:app --port 8001 --reload &
pytest tests/integration/ -v -s
```

### Test Data Generation
```python
# Generate valid test signatures programmatically
from tests.helpers.auth import generate_test_signature

headers = generate_test_signature(
    body='{"ticker":"EURUSD","price":1.0945}',
    secret="test-secret"
)
```

### Debugging Failed Tests
```bash
# Capture detailed logs during test failure
pytest tests/integration/ --log-cli-level=DEBUG --tb=long

# Run single test with pdb breakpoint
pytest tests/unit/test_signature.py::test_invalid_signature --pdb

# Monitor metrics during integration tests
curl -s http://localhost:8001/metrics | grep gateway_webhooks
```

### Local Development
```bash
# Start dependencies
docker compose -f docker-compose.dev.yml up -d nats

# Run gateway with test config
export $(cat tests/fixtures/.env.test.example | xargs)
uvicorn at_gateway.app:app --port 8001 --reload

# Run quick validation
make test-unit
```
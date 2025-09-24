# Testing Strategy and Practices

Comprehensive testing guide for the Agentic Trading Architecture.

## Testing Philosophy

We follow the **Test Pyramid** approach with emphasis on:
- Fast, reliable unit tests at the base
- Integration tests for service boundaries
- E2E tests for critical user journeys
- Contract tests for API compatibility

```
       ┌─────────────┐
       │  E2E Tests  │      5%  - Full system flows
       ├─────────────┤
       │ Integration │     15%  - Service interactions
       ├─────────────┤
       │  Contract   │     20%  - API contracts
       ├─────────────┤
       │    Unit     │     60%  - Business logic
       └─────────────┘
```

## Test Categories

### 1. Unit Tests

**Purpose**: Test individual functions and classes in isolation

**Location**: `repos/*/tests/unit/`

**Naming Convention**: `test_{module}_{functionality}.py`

#### Example Unit Test
```python
# repos/at-exec-sim/tests/unit/test_validator.py
import pytest
from at_exec_sim.validator import validate_order_schema

class TestOrderValidator:
    def test_valid_market_order(self):
        """Market orders should pass validation"""
        order = {
            "corr_id": "test_123",
            "agent_id": "test_agent",
            "instrument": "AAPL",
            "side": "buy",
            "quantity": 100,
            "order_type": "market",
            "timestamp": "2025-01-15T10:30:00Z"
        }
        result = validate_order_schema(order)
        assert result["valid"] is True
        assert "error" not in result

    def test_invalid_instrument_format(self):
        """Invalid instrument format should fail"""
        order = {
            "corr_id": "test_123",
            "instrument": "invalid-symbol",  # Should be uppercase
            "side": "buy",
            "quantity": 100,
            "order_type": "market",
            "timestamp": "2025-01-15T10:30:00Z"
        }
        result = validate_order_schema(order)
        assert result["valid"] is False
        assert "instrument" in result["error"]

    @pytest.mark.parametrize("missing_field", [
        "corr_id", "instrument", "side", "quantity", "order_type"
    ])
    def test_missing_required_fields(self, missing_field):
        """Missing required fields should fail validation"""
        order = {
            "corr_id": "test_123",
            "instrument": "AAPL",
            "side": "buy",
            "quantity": 100,
            "order_type": "market",
            "timestamp": "2025-01-15T10:30:00Z"
        }
        del order[missing_field]

        result = validate_order_schema(order)
        assert result["valid"] is False
```

### 2. Integration Tests

**Purpose**: Test service interactions and NATS messaging

**Location**: `repos/*/tests/integration/`

#### Example Integration Test
```python
# repos/at-exec-sim/tests/integration/test_nats_consumer.py
import asyncio
import pytest
import nats
from at_exec_sim.nats_client import NATSClient

@pytest.mark.asyncio
async def test_consumer_processes_order():
    """Test that consumer correctly processes order from NATS"""
    # Setup
    nc = await nats.connect("nats://localhost:4222")
    js = nc.jetstream()

    # Publish test message
    test_order = {
        "corr_id": "integ_test_001",
        "agent_id": "test",
        "instrument": "AAPL",
        "side": "buy",
        "quantity": 100,
        "order_type": "market",
        "timestamp": "2025-01-15T10:30:00Z"
    }

    await js.publish(
        "decisions.order_intent",
        json.dumps(test_order).encode()
    )

    # Wait for processing
    await asyncio.sleep(1)

    # Verify fill was published
    # (Check by subscribing to executions.fill or checking metrics)

    await nc.close()
```

### 3. Contract Tests

**Purpose**: Ensure API contracts between services are maintained

**Location**: `tests/contracts/`

#### Example Contract Test
```python
# tests/contracts/test_gateway_contract.py
import pytest
import requests
from jsonschema import validate

class TestGatewayWebhookContract:
    def test_webhook_request_schema(self):
        """Webhook accepts valid market signal"""
        request_body = {
            "instrument": "AAPL",
            "price": 150.25,
            "signal": "buy",
            "strength": 0.85
        }

        # Validate against contract
        schema = load_schema("webhook_request.json")
        validate(request_body, schema)

        # Send actual request
        response = requests.post(
            "http://localhost:8001/webhook/test",
            json=request_body,
            headers=generate_hmac_headers(request_body)
        )

        assert response.status_code == 200

    def test_webhook_response_schema(self):
        """Webhook returns expected response format"""
        response = send_valid_webhook()

        expected_schema = {
            "type": "object",
            "required": ["status", "corr_id", "timestamp"],
            "properties": {
                "status": {"type": "string", "enum": ["accepted"]},
                "corr_id": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$"},
                "timestamp": {"type": "string", "format": "date-time"}
            }
        }

        validate(response.json(), expected_schema)
```

### 4. End-to-End Tests

**Purpose**: Validate complete user journeys

**Location**: `tests/e2e/`

#### Example E2E Test
```python
# tests/e2e/test_signal_to_fill.py
import pytest
import time
from helpers import send_webhook, get_metrics, wait_for_condition

def test_complete_trading_flow():
    """Test signal → decision → execution flow"""
    # Get initial metrics
    initial_metrics = get_metrics("exec_sim_orders_received_total")

    # Send market signal
    response = send_webhook({
        "instrument": "TSLA",
        "price": 850.00,
        "signal": "buy",
        "strength": 0.95
    })

    assert response["status"] == "accepted"
    corr_id = response["corr_id"]

    # Wait for processing (with timeout)
    def check_order_processed():
        current = get_metrics("exec_sim_orders_received_total")
        return current > initial_metrics

    assert wait_for_condition(check_order_processed, timeout=10)

    # Verify fill was generated
    fills = get_metrics("exec_sim_fills_generated_total")
    assert fills > 0
```

## Testing Tools and Frameworks

### Python Testing Stack
```yaml
Unit Testing:
  - pytest: Test framework
  - pytest-asyncio: Async test support
  - pytest-mock: Mocking support
  - pytest-cov: Coverage reporting

Integration Testing:
  - testcontainers: Docker container management
  - pytest-docker: Docker fixtures
  - aioresponses: Mock async HTTP

Load Testing:
  - locust: Load testing framework
  - k6: Modern load testing tool

Contract Testing:
  - jsonschema: Schema validation
  - pact-python: Consumer-driven contracts
```

### Testing Infrastructure
```yaml
CI/CD Pipeline:
  - GitHub Actions: CI automation
  - Docker Compose: Test environment
  - SonarQube: Code quality
  - CodeCov: Coverage tracking
```

## Running Tests

### Local Development

```bash
# Run all tests for a service
cd repos/at-exec-sim
pytest

# Run only unit tests
pytest tests/unit/

# Run with coverage
pytest --cov=at_exec_sim --cov-report=html

# Run specific test
pytest tests/unit/test_validator.py::test_valid_market_order

# Run with verbose output
pytest -v

# Run in parallel
pytest -n auto
```

### Docker Test Environment

```bash
# Run tests in Docker
docker compose -f docker-compose.test.yml up --abort-on-container-exit

# Run specific service tests
docker compose -f docker-compose.test.yml run exec-sim-tests

# Clean up after tests
docker compose -f docker-compose.test.yml down -v
```

### CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements-test.txt
      - run: pytest tests/unit/ --cov

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: docker compose -f docker-compose.test.yml up --abort-on-container-exit

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: docker compose -f docker-compose.dev.yml up -d
      - run: ./test_smoke_ci.sh
```

## Test Data Management

### Fixtures
```python
# conftest.py
import pytest
import json

@pytest.fixture
def valid_order():
    """Provide valid order for testing"""
    return {
        "corr_id": "test_123",
        "agent_id": "test_agent",
        "instrument": "AAPL",
        "side": "buy",
        "quantity": 100,
        "order_type": "market",
        "timestamp": "2025-01-15T10:30:00Z"
    }

@pytest.fixture
async def nats_connection():
    """Provide NATS connection for integration tests"""
    import nats
    nc = await nats.connect("nats://localhost:4222")
    yield nc
    await nc.close()

@pytest.fixture
def mock_time(monkeypatch):
    """Mock time for deterministic tests"""
    import time
    monkeypatch.setattr(time, 'time', lambda: 1642250400.0)
```

### Test Data Files
```
tests/
├── fixtures/
│   ├── valid_order.json
│   ├── invalid_orders.json
│   ├── market_signals.json
│   └── expected_fills.json
```

## Mocking Strategies

### External Services
```python
# Mock broker API
@pytest.fixture
def mock_broker(mocker):
    broker = mocker.patch('at_exec_sim.broker.BrokerAPI')
    broker.submit_order.return_value = {
        "order_id": "123",
        "status": "submitted"
    }
    return broker

# Mock NATS
@pytest.fixture
def mock_nats(mocker):
    nats = mocker.patch('at_exec_sim.nats_client.NATSClient')
    nats.publish.return_value = asyncio.Future()
    nats.publish.return_value.set_result(None)
    return nats
```

## Performance Testing

### Load Test Script
```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between

class TradingUser(HttpUser):
    wait_time = between(1, 3)

    @task(10)
    def send_signal(self):
        self.client.post(
            "/webhook/test",
            json={
                "instrument": "AAPL",
                "price": 150.25,
                "signal": "buy",
                "strength": 0.85
            },
            headers=self.generate_hmac_headers()
        )

    @task(2)
    def check_health(self):
        self.client.get("/healthz")

    @task(1)
    def get_metrics(self):
        self.client.get("/metrics")
```

### Running Load Tests
```bash
# Start Locust
locust -f tests/performance/locustfile.py --host http://localhost:8001

# Run headless
locust -f tests/performance/locustfile.py \
    --host http://localhost:8001 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 60s \
    --headless
```

## Test Coverage Requirements

### Minimum Coverage Targets
```yaml
Overall: 80%
Critical Paths: 95%

By Component:
  - Business Logic: 90%
  - API Endpoints: 85%
  - Validators: 95%
  - NATS Handlers: 80%
  - Utilities: 70%
```

### Coverage Reporting
```bash
# Generate coverage report
pytest --cov=at_exec_sim --cov-report=term-missing

# Generate HTML report
pytest --cov=at_exec_sim --cov-report=html
open htmlcov/index.html

# Generate XML for CI
pytest --cov=at_exec_sim --cov-report=xml
```

## Test Patterns and Anti-patterns

### ✅ Good Patterns
```python
# Descriptive test names
def test_market_order_with_valid_instrument_creates_fill():
    pass

# Arrange-Act-Assert
def test_order_processing():
    # Arrange
    order = create_valid_order()
    processor = OrderProcessor()

    # Act
    result = processor.process(order)

    # Assert
    assert result.status == "success"

# Use fixtures for common data
def test_with_fixture(valid_order):
    assert validate(valid_order) is True

# Test one thing
def test_single_responsibility():
    # Good: Tests only validation
    assert validate_instrument("AAPL") is True
```

### ❌ Anti-patterns
```python
# Avoid: Unclear test names
def test1():
    pass

# Avoid: Multiple assertions for different things
def test_everything():
    result = process_order(order)
    assert result.status == "success"  # Order processing
    assert len(get_metrics()) > 0      # Metrics
    assert check_audit() is True       # Audit

# Avoid: Test interdependencies
def test_depends_on_previous():
    # Assumes test_create_order ran first
    order = get_last_order()
    assert order is not None

# Avoid: Hardcoded waits
def test_with_sleep():
    send_message()
    time.sleep(5)  # Bad: Use wait_for_condition instead
    assert check_result()
```

## Debugging Failed Tests

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| NATS not connected | Ensure Docker services are running |
| Port already in use | Check for orphaned processes |
| Schema validation fails | Verify CONTRACT.md is up to date |
| Timeout in integration tests | Increase timeout or check service health |
| Flaky tests | Add proper wait conditions, avoid hardcoded delays |

### Debug Commands
```bash
# View service logs during test
docker logs -f agentic-trading-architecture-full-exec-1

# Check NATS messages
docker exec -it agentic-trading-architecture-full-nats-1 \
    nats sub ">" --headers

# Interactive debugging
pytest -s --pdb tests/unit/test_failing.py

# Run with increased verbosity
pytest -vvv tests/integration/
```

## Continuous Improvement

### Test Metrics to Track
- Test execution time
- Flaky test rate
- Coverage trends
- Failed test patterns
- Time to fix failing tests

### Regular Reviews
- Weekly: Review failing tests
- Monthly: Update test data
- Quarterly: Refactor test suite
- Yearly: Review testing strategy

## Resources

### Documentation
- [pytest documentation](https://docs.pytest.org/)
- [Testing best practices](https://testdriven.io/blog/testing-python/)
- [Contract testing](https://pact.io/)

### Tools
- [pytest-xdist](https://github.com/pytest-dev/pytest-xdist): Parallel execution
- [pytest-timeout](https://github.com/pytest-dev/pytest-timeout): Test timeouts
- [hypothesis](https://hypothesis.works/): Property-based testing

---

*Remember: Tests are documentation of how your code should behave. Write them clearly!*
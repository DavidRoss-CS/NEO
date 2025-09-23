# Test Strategy - Core Contracts

**Comprehensive testing approach for schema validation and contract enforcement.**

## Testing Philosophy

**Contract-first testing**: All tests validate that schemas enforce the intended contracts and that changes don't break existing integrations.

**Test pyramid**:
- **Unit tests**: Schema structure and validation rules
- **Contract tests**: Backwards compatibility and version migration
- **Integration tests**: End-to-end validation with real service payloads
- **Performance tests**: Schema validation under load

## Unit Tests

### Schema Structure Tests

**Validate schema syntax and completeness**:

```python
# tests/test_schema_structure.py
import json
import pytest
from jsonschema import Draft202012Validator

def test_signals_raw_schema_valid():
    """Schema itself is valid JSON Schema Draft 2020-12."""
    with open('schemas/signals.raw.schema.json') as f:
        schema = json.load(f)
    
    # Validate schema syntax
    Draft202012Validator.check_schema(schema)
    
    # Verify required metadata
    assert '$schema' in schema
    assert '$id' in schema
    assert 'version' in schema
    assert 'examples' in schema
    assert len(schema['examples']) >= 1

def test_required_fields_present():
    """All schemas define required fields."""
    schema_files = [
        'schemas/signals.raw.schema.json',
        'schemas/signals.normalized.schema.json'
    ]
    
    for schema_file in schema_files:
        with open(schema_file) as f:
            schema = json.load(f)
        
        assert 'required' in schema, f"{schema_file} missing 'required' field"
        assert len(schema['required']) > 0, f"{schema_file} has empty required fields"
        assert 'additionalProperties' in schema, f"{schema_file} missing additionalProperties"
        assert schema['additionalProperties'] is False, f"{schema_file} should set additionalProperties: false"
```

### Validation Tests

**Test valid and invalid payloads**:

```python
# tests/test_validation.py
import json
import pytest
from jsonschema import validate, ValidationError

class TestSignalsRawValidation:
    @classmethod
    def setup_class(cls):
        with open('schemas/signals.raw.schema.json') as f:
            cls.schema = json.load(f)
    
    def test_valid_signals_pass(self):
        """All schema examples should validate successfully."""
        for example in self.schema['examples']:
            validate(instance=example, schema=self.schema)
    
    def test_missing_required_fields_fail(self):
        """Signals missing required fields should fail validation."""
        incomplete_signal = {
            "corr_id": "test_123",
            "source": "test"
            # Missing 'received_at' and 'payload'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate(instance=incomplete_signal, schema=self.schema)
        
        assert "required" in str(exc_info.value)
    
    def test_invalid_source_fails(self):
        """Unknown source values should fail validation."""
        invalid_signal = {
            "corr_id": "test_123",
            "source": "unknown_source",  # Invalid enum value
            "received_at": "2024-01-15T10:30:00Z",
            "payload": {"test": "data"}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate(instance=invalid_signal, schema=self.schema)
        
        assert "enum" in str(exc_info.value)
    
    def test_invalid_timestamp_format(self):
        """Non-ISO8601 timestamps should fail validation."""
        invalid_signal = {
            "corr_id": "test_123",
            "source": "test",
            "received_at": "2024-01-15 10:30:00",  # Wrong format
            "payload": {"test": "data"}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate(instance=invalid_signal, schema=self.schema)
        
        assert "format" in str(exc_info.value)
    
    def test_empty_payload_fails(self):
        """Empty payload should fail minProperties validation."""
        invalid_signal = {
            "corr_id": "test_123",
            "source": "test",
            "received_at": "2024-01-15T10:30:00Z",
            "payload": {}  # Empty object
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_signal, schema=self.schema)
    
    def test_additional_properties_allowed_in_payload(self):
        """Payload should allow arbitrary additional properties."""
        signal_with_extra_fields = {
            "corr_id": "test_123",
            "source": "test",
            "received_at": "2024-01-15T10:30:00Z",
            "payload": {
                "standard_field": "value",
                "custom_field_1": 123,
                "custom_field_2": ["array", "data"],
                "nested": {"arbitrary": "structure"}
            }
        }
        
        # Should not raise exception
        validate(instance=signal_with_extra_fields, schema=self.schema)
```

### Edge Case Tests

```python
# tests/test_edge_cases.py
class TestEdgeCases:
    def test_correlation_id_patterns(self):
        """Test various correlation ID formats."""
        valid_corr_ids = [
            "req_abc123",
            "webhook_20240115_103045",
            "test-signal-001",
            "a1b2c3d4e5f6",
            "CAPITAL_LETTERS_123"
        ]
        
        for corr_id in valid_corr_ids:
            signal = {
                "corr_id": corr_id,
                "source": "test",
                "received_at": "2024-01-15T10:30:00Z",
                "payload": {"test": "data"}
            }
            validate(instance=signal, schema=self.raw_schema)
    
    def test_price_boundaries(self):
        """Test price field edge cases in normalized schema."""
        with open('schemas/signals.normalized.schema.json') as f:
            schema = json.load(f)
        
        # Very small positive price
        signal = {
            "corr_id": "test_123",
            "source": "test",
            "instrument": "BTCUSD",
            "price": 0.000001,  # Very small but > 0
            "timestamp": "2024-01-15T10:30:00Z",
            "normalized_at": "2024-01-15T10:30:01Z"
        }
        validate(instance=signal, schema=schema)
        
        # Zero price should fail (exclusiveMinimum: 0)
        signal["price"] = 0
        with pytest.raises(ValidationError):
            validate(instance=signal, schema=schema)
        
        # Negative price should fail
        signal["price"] = -1.50
        with pytest.raises(ValidationError):
            validate(instance=signal, schema=schema)
```

## Contract Tests

### Backwards Compatibility Tests

**Ensure schema changes don't break existing clients**:

```python
# tests/test_backwards_compatibility.py
import json
import pytest
from pathlib import Path

class TestBackwardsCompatibility:
    def setup_method(self):
        """Load current and previous schema versions."""
        # Load golden samples from previous versions
        self.golden_samples_dir = Path('fixtures/golden_samples')
        
        # Load current schemas
        with open('schemas/signals.raw.schema.json') as f:
            self.current_raw_schema = json.load(f)
    
    def test_v1_samples_validate_against_current_schema(self):
        """Historical samples should validate against current schema."""
        golden_files = [
            'fixtures/golden_samples/signals_raw_v1.0.0_samples.json',
            'fixtures/golden_samples/signals_raw_v1.1.0_samples.json'
        ]
        
        for golden_file in golden_files:
            if Path(golden_file).exists():
                with open(golden_file) as f:
                    historical_samples = json.load(f)
                
                for sample in historical_samples:
                    # Historical samples should validate against current schema
                    validate(instance=sample, schema=self.current_raw_schema)
    
    def test_schema_version_increases_monotonically(self):
        """Schema version should increase from previous versions."""
        # Compare with previous schema versions stored in git
        # This would typically use git to check previous versions
        pass
    
    def test_required_fields_not_removed(self):
        """Required fields should never be removed in minor versions."""
        # Load schema history and verify required fields are preserved
        pass
```

### Migration Tests

**Test schema migration scenarios**:

```python
# tests/test_migration.py
class TestSchemaMigration:
    def test_dual_schema_support(self):
        """During migration, both old and new schemas should work."""
        # Load both v1 and v2 schemas (when v2 exists)
        # Test that services can validate against both
        pass
    
    def test_migration_tools(self):
        """Schema migration utilities should convert data correctly."""
        # Test any migration scripts or utilities
        pass
```

## Integration Tests

### End-to-End Validation

**Test with real service payloads**:

```python
# tests/test_integration.py
import requests
import json

class TestIntegrationValidation:
    def test_gateway_to_core_validation(self):
        """Gateway should validate signals using core schemas."""
        # Send webhook to gateway
        webhook_payload = {
            "ticker": "EURUSD",
            "action": "buy",
            "price": 1.0945
        }
        
        response = requests.post(
            'http://localhost:8001/webhook/tradingview',
            json=webhook_payload,
            headers={
                'X-Timestamp': '2024-01-15T10:30:00Z',
                'X-Nonce': 'test_nonce_123',
                'X-Signature': 'sha256=test_signature'
            }
        )
        
        # Gateway should validate and return success
        assert response.status_code == 202
        
        # Verify NATS message validates against normalized schema
        # This would require NATS consumer to check published message
    
    def test_error_response_format(self):
        """Error responses should match ERROR_CATALOG format."""
        # Send invalid payload
        invalid_payload = {"invalid": "data"}
        
        response = requests.post(
            'http://localhost:8001/webhook/tradingview',
            json=invalid_payload
        )
        
        assert response.status_code == 400
        error_data = response.json()
        
        # Verify error format matches catalog
        required_fields = ['error', 'code', 'message', 'corr_id', 'details']
        for field in required_fields:
            assert field in error_data
        
        assert error_data['code'].startswith('CORE-')
```

## Performance Tests

### Schema Validation Load Tests

```python
# tests/test_performance.py
import time
import json
from concurrent.futures import ThreadPoolExecutor

class TestSchemaPerformance:
    def test_validation_speed(self):
        """Schema validation should complete within acceptable time."""
        with open('schemas/signals.raw.schema.json') as f:
            schema = json.load(f)
        
        test_payload = {
            "corr_id": "perf_test_123",
            "source": "test",
            "received_at": "2024-01-15T10:30:00Z",
            "payload": {"test": "data"}
        }
        
        # Validate 1000 payloads and measure time
        start_time = time.time()
        for _ in range(1000):
            validate(instance=test_payload, schema=schema)
        end_time = time.time()
        
        avg_time_ms = (end_time - start_time) * 1000 / 1000
        assert avg_time_ms < 1.0, f"Validation too slow: {avg_time_ms}ms average"
    
    def test_concurrent_validation(self):
        """Schema validation should work under concurrent load."""
        def validate_payload(payload):
            with open('schemas/signals.raw.schema.json') as f:
                schema = json.load(f)
            validate(instance=payload, schema=schema)
            return True
        
        test_payload = {
            "corr_id": "concurrent_test",
            "source": "test",
            "received_at": "2024-01-15T10:30:00Z",
            "payload": {"test": "data"}
        }
        
        # Run 100 concurrent validations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_payload, test_payload) for _ in range(100)]
            results = [f.result() for f in futures]
        
        assert all(results), "Some concurrent validations failed"
```

## Test Fixtures

### Sample Data Files

**fixtures/valid_raw.json**:
```json
[
  {
    "corr_id": "fixture_001",
    "source": "tradingview",
    "received_at": "2024-01-15T10:30:00Z",
    "payload": {
      "ticker": "EURUSD",
      "action": "buy",
      "price": 1.0945,
      "time": "2024-01-15T10:29:55Z"
    }
  },
  {
    "corr_id": "fixture_002",
    "source": "custom",
    "received_at": "2024-01-15T14:22:10Z",
    "payload": {
      "symbol": "BTC/USD",
      "side": "sell",
      "quantity": 0.5,
      "limit_price": 42500.00
    }
  }
]
```

**fixtures/valid_normalized.json**:
```json
[
  {
    "corr_id": "fixture_001",
    "source": "tradingview",
    "instrument": "EURUSD",
    "price": 1.0945,
    "side": "buy",
    "strength": 0.78,
    "timestamp": "2024-01-15T10:29:55Z",
    "normalized_at": "2024-01-15T10:30:00.123Z"
  }
]
```

**fixtures/invalid_samples.json**:
```json
[
  {
    "description": "Missing required corr_id",
    "data": {
      "source": "test",
      "received_at": "2024-01-15T10:30:00Z",
      "payload": {"test": "data"}
    },
    "expected_error": "CORE-001"
  },
  {
    "description": "Invalid source enum",
    "data": {
      "corr_id": "test_123",
      "source": "unknown",
      "received_at": "2024-01-15T10:30:00Z",
      "payload": {"test": "data"}
    },
    "expected_error": "CORE-001"
  }
]
```

## CI/CD Integration

### Automated Testing Pipeline

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
    --cov=schemas
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=95
markers =
    unit: Unit tests for individual schemas
    contract: Contract and compatibility tests
    integration: Integration tests with services
    performance: Performance and load tests
```

### GitHub Actions Workflow

**.github/workflows/schema-validation.yml**:
```yaml
name: Schema Validation

on:
  pull_request:
    paths:
      - 'schemas/**'
      - 'tests/**'
      - 'fixtures/**'

jobs:
  validate-schemas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install jsonschema pytest pytest-cov
      
      - name: Validate schema syntax
        run: |
          python -c "import json; from jsonschema import Draft202012Validator; 
          [Draft202012Validator.check_schema(json.load(open(f))) 
           for f in ['schemas/signals.raw.schema.json', 'schemas/signals.normalized.schema.json']]"
      
      - name: Run unit tests
        run: pytest tests/ -m unit
      
      - name: Run contract tests
        run: pytest tests/ -m contract
      
      - name: Check backwards compatibility
        run: |
          # Custom script to check schema compatibility
          python scripts/check_backwards_compatibility.py
      
      - name: Validate examples
        run: |
          python scripts/validate_schema_examples.py
```

### Test Execution Commands

**Local development**:
```bash
# Run all tests
make test-all

# Run specific test categories
pytest tests/ -m unit              # Unit tests only
pytest tests/ -m contract          # Contract tests only
pytest tests/ -m integration       # Integration tests only
pytest tests/ -m performance       # Performance tests only

# Run with coverage
pytest tests/ --cov=schemas --cov-report=html

# Validate specific schema
python scripts/validate_single_schema.py schemas/signals.raw.schema.json

# Check backwards compatibility
python scripts/check_backwards_compatibility.py
```

### Quality Gates

**Required checks before merge**:
1. ✅ Schema syntax validation passes
2. ✅ All schema examples validate successfully
3. ✅ Unit test coverage ≥ 95%
4. ✅ Contract tests pass (no breaking changes)
5. ✅ Integration tests pass with gateway
6. ✅ Performance tests meet latency requirements
7. ✅ Backwards compatibility verified

**Automated quality checks**:
- Schema linting for consistent formatting
- Example validation against schema
- Version bump validation (semver compliance)
- Breaking change detection
- Documentation updates required for new schemas

---

**For running tests locally, see the fixtures/ directory for sample data and scripts/ for validation utilities.**
# at-core Operational Runbook

## Service Overview

**Service Name**: at-core
**Type**: Shared Library
**Purpose**: Provides event schemas, validation, and utility functions for the trading system
**Dependencies**: None (library)
**Consumers**: at-gateway, at-agent-mcp, at-exec-sim, at-observability

## Quick Reference

| Action | Command/Location |
|--------|------------------|
| View schemas | `ls schemas/*.schema.json` |
| Test validation | `python -m at_core.validators` |
| Run tests | `pytest tests/` |
| Check version | `python -c "import at_core; print(at_core.__version__)"` |

## Common Operations

### Adding a New Schema

1. Create schema file:
```bash
cd repos/at-core/schemas
vim new_event_type.schema.json
```

2. Follow naming convention: `{subject}.{event}.schema.json`

3. Validate schema syntax:
```python
python -c "import json; json.load(open('schemas/new_event_type.schema.json'))"
```

4. Add event helper (optional):
```python
# Edit at_core/events.py
def create_new_event_type(...):
    ...
```

5. Update documentation:
- Update API_SPEC.md with new schema
- Add to SCHEMA_REGISTRY.md

### Updating an Existing Schema

1. Check current version:
```bash
grep '"version"' schemas/target.schema.json
```

2. Update schema following versioning rules:
- MAJOR: Breaking changes
- MINOR: New optional fields
- PATCH: Documentation only

3. Test backward compatibility:
```python
from at_core.validators import validate_event

# Test with old data structure
old_data = {...}
validate_event("event_type", old_data)  # Should still pass for minor/patch

# Test with new data structure
new_data = {...}
validate_event("event_type", new_data)
```

### Debugging Schema Validation

1. Get detailed validation errors:
```python
from at_core.validators import SchemaRegistry

registry = SchemaRegistry()
is_valid, errors = registry.validate_with_errors("event_type", data)
for error in errors:
    print(error)
```

2. View schema requirements:
```python
from at_core.validators import load_schema
import json

schema = load_schema("signals.raw")
print(json.dumps(schema, indent=2))
```

## Troubleshooting

### Issue: Schema Not Found

**Symptom**: `ValueError: Schema not found: {schema_name}`

**Check**:
```bash
ls schemas/*.schema.json | grep {schema_name}
```

**Resolution**:
1. Verify schema file exists
2. Check file naming convention
3. Ensure schema is valid JSON

### Issue: Validation Failing

**Symptom**: Events rejected with validation errors

**Debug**:
```python
from at_core.validators import SchemaRegistry

registry = SchemaRegistry()
data = {...}  # Your event data

# Get detailed errors
is_valid, errors = registry.validate_with_errors("event_type", data)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
```

**Common causes**:
- Missing required fields
- Incorrect data types
- Additional properties when `additionalProperties: false`
- Pattern mismatch for string fields

### Issue: Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'at_core'`

**Resolution**:
1. Install at-core in development:
```bash
cd repos/at-core
pip install -e .
```

2. Or add to PYTHONPATH:
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/repos/at-core"
```

### Issue: Schema Version Conflicts

**Symptom**: Services expecting different schema versions

**Check current versions**:
```bash
for f in schemas/*.schema.json; do
    echo "$f: $(grep '"version"' $f)"
done
```

**Resolution**:
1. Implement dual-write period for breaking changes
2. Update consumers gradually
3. Use schema version in validation calls

## Performance Monitoring

### Check Schema Load Time

```python
import time
from at_core.validators import SchemaRegistry

start = time.time()
registry = SchemaRegistry()
end = time.time()
print(f"Schema load time: {end - start:.3f}s")
print(f"Loaded schemas: {len(registry.list_schemas())}")
```

### Validation Performance

```python
import timeit
from at_core.validators import validate_event

data = {...}  # Your test data

time_taken = timeit.timeit(
    lambda: validate_event("signals.raw", data, raise_on_error=False),
    number=10000
)
print(f"Avg validation time: {time_taken/10000*1000:.3f}ms")
```

## Deployment Procedures

### Building Docker Image

```bash
cd repos/at-core
docker build -t at-core:latest .
```

### Publishing as Python Package

```bash
cd repos/at-core
python setup.py sdist bdist_wheel
# Upload to private PyPI or artifact repository
```

### Version Tagging

```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

## Emergency Procedures

### Rolling Back Schema Changes

1. Identify problematic schema:
```bash
git diff HEAD~1 schemas/
```

2. Revert specific schema:
```bash
git checkout HEAD~1 -- schemas/problematic.schema.json
```

3. Notify all consuming services:
- at-gateway
- at-agent-mcp
- at-exec-sim

### Schema Corruption Recovery

1. Validate all schemas:
```python
import json
import os

schema_dir = "schemas"
for filename in os.listdir(schema_dir):
    if filename.endswith(".schema.json"):
        try:
            with open(f"{schema_dir}/{filename}") as f:
                json.load(f)
            print(f"✓ {filename}")
        except:
            print(f"✗ {filename} - CORRUPTED")
```

2. Restore from backup:
```bash
cp /backup/schemas/*.schema.json schemas/
```

## Monitoring Integration

### Health Check Script

```python
#!/usr/bin/env python
# check_schemas.py

from at_core.validators import SchemaRegistry

try:
    registry = SchemaRegistry()
    schemas = registry.list_schemas()

    required = [
        "signals.raw",
        "signals.normalized",
        "decisions.order_intent",
        "executions.fill",
        "executions.reconcile"
    ]

    for schema in required:
        assert schema in schemas, f"Missing required schema: {schema}"

    print(f"OK: All {len(required)} required schemas present")
    exit(0)
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
```

### Integration Test

```python
# test_integration.py
from at_core import validate_event, create_signal_raw

def test_full_flow():
    # Create event
    event = create_signal_raw(
        payload={"test": "data"},
        source="test",
        corr_id="test_123"
    )

    # Validate event
    assert validate_event("signals.raw", event, raise_on_error=False)

    print("Integration test passed")

if __name__ == "__main__":
    test_full_flow()
```

## Service Dependencies

### Who Uses at-core

| Service | Usage | Critical Schemas |
|---------|-------|------------------|
| at-gateway | Event creation, validation | signals.raw, signals.normalized |
| at-agent-mcp | Signal consumption, decision creation | signals.normalized, decisions.order_intent |
| at-exec-sim | Order processing, fill creation | decisions.order_intent, executions.fill |
| at-observability | Event validation for metrics | All schemas |

### Update Coordination

When updating schemas:
1. Announce in team channel
2. Create migration guide
3. Implement dual-write if breaking
4. Coordinate deployment windows

## Contact and Escalation

| Level | Contact | When to Escalate |
|-------|---------|------------------|
| L1 | On-call Engineer | Schema validation errors |
| L2 | Platform Team | Schema corruption, version conflicts |
| L3 | Architecture Team | Breaking schema changes, design decisions |

## Related Documentation

- [SCHEMA_REGISTRY.md](SCHEMA_REGISTRY.md) - Complete schema documentation
- [API_SPEC.md](API_SPEC.md) - API reference
- [ERROR_CATALOG.md](ERROR_CATALOG.md) - Error codes (CORE-xxx)
- [TEST_STRATEGY.md](TEST_STRATEGY.md) - Testing approach
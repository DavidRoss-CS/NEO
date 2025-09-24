# at-core API Specification

## Overview

The at-core repository provides shared contracts, schemas, and utility functions for the agentic trading architecture. It acts as a library that other services import to ensure consistency across the system.

## Python API

### Schema Validation

```python
from at_core.validators import validate_event, load_schema, list_available_schemas

# Validate an event
is_valid = validate_event("signals.raw", event_data)

# Load a schema
schema = load_schema("decisions.order_intent")

# List available schemas
schemas = list_available_schemas()
# Returns: ['signals.raw', 'signals.normalized', 'decisions.order_intent', ...]
```

### Event Creation Helpers

```python
from at_core.events import (
    generate_correlation_id,
    create_event_header,
    create_signal_raw,
    create_signal_normalized,
    create_order_intent,
    create_execution_fill
)

# Generate correlation ID
corr_id = generate_correlation_id("req")  # Returns: "req_abc123def456"

# Create event headers for NATS
headers = create_event_header(
    corr_id="req_123",
    source="tradingview",
    instrument="EURUSD"
)

# Create a normalized signal
signal = create_signal_normalized(
    instrument="EURUSD",
    signal_type="bullish_momentum",
    strength=0.85,
    price=1.0895,
    source="tradingview",
    corr_id="req_123"
)

# Create an order intent
order = create_order_intent(
    strategy_id="momentum_v1",
    agent_id="agent_001",
    instrument="EURUSD",
    side="buy",
    order_type="market",
    quantity=10000,
    confidence=0.8,
    corr_id="req_123",
    reasoning="Strong momentum detected"
)
```

## Schema Definitions

### Available Schemas

| Schema | Version | Description | Location |
|--------|---------|-------------|----------|
| signals.raw | 1.0.0 | Raw webhook signals | schemas/signals.raw.schema.json |
| signals.normalized | 1.0.0 | Normalized trading signals | schemas/signals.normalized.schema.json |
| decisions.order_intent | 1.0.0 | Agent order decisions | schemas/decisions.order_intent.schema.json |
| executions.fill | 1.0.0 | Trade execution records | schemas/executions.fill.schema.json |
| executions.reconcile | 1.0.0 | Position reconciliation | schemas/executions.reconcile.schema.json |

## Usage Examples

### Service Integration

```python
# In at-gateway service
from at_core.validators import validate_event
from at_core.events import create_signal_raw, create_signal_normalized

async def process_webhook(payload: dict, source: str):
    # Create and validate raw signal
    raw_signal = create_signal_raw(payload, source)
    if not validate_event("signals.raw", raw_signal):
        raise ValueError("Invalid raw signal")

    # Publish to NATS
    await publish_to_nats("signals.raw", raw_signal)

    # Create normalized signal
    normalized = create_signal_normalized(
        instrument=payload["instrument"],
        signal_type=payload["signal"],
        strength=payload["strength"],
        price=payload["price"],
        source=source,
        corr_id=raw_signal["corr_id"]
    )

    # Validate and publish
    if validate_event("signals.normalized", normalized):
        await publish_to_nats("signals.normalized", normalized)
```

### Agent Integration

```python
# In at-agent-mcp service
from at_core.validators import validate_event
from at_core.events import create_order_intent

async def process_signal(signal: dict):
    # Validate incoming signal
    if not validate_event("signals.normalized", signal):
        logger.error(f"Invalid signal received: {signal}")
        return

    # Run strategy logic
    decision = run_strategy(signal)

    if decision:
        # Create order intent
        order = create_order_intent(
            strategy_id=self.strategy_id,
            agent_id=self.agent_id,
            instrument=signal["instrument"],
            side=decision["side"],
            order_type=decision["type"],
            quantity=decision["quantity"],
            confidence=decision["confidence"],
            corr_id=signal["corr_id"]
        )

        # Validate and publish
        if validate_event("decisions.order_intent", order):
            await publish_to_nats("decisions.order_intent", order)
```

## Error Handling

### Validation Errors

```python
from at_core.validators import validate_event

try:
    validate_event("signals.raw", data, raise_on_error=True)
except ValueError as e:
    # Handle validation error
    logger.error(f"Validation failed: {e}")

# Or check without raising
is_valid = validate_event("signals.raw", data, raise_on_error=False)
if not is_valid:
    # Handle invalid data
    pass
```

### Schema Not Found

```python
from at_core.validators import load_schema

try:
    schema = load_schema("invalid_schema")
except ValueError as e:
    # Schema not found
    logger.error(f"Schema error: {e}")
```

## Environment Variables

The at-core library doesn't require environment variables as it's a library package. Services using at-core should set their own environment variables.

## Development

### Running Tests

```bash
cd repos/at-core
python -m pytest tests/
```

### Adding New Schemas

1. Create schema file in `schemas/` directory following naming convention: `{subject}.{event}.schema.json`
2. Ensure schema follows JSON Schema Draft 2020-12 specification
3. Add corresponding event creation helper in `at_core/events.py`
4. Update this documentation

### Schema Versioning

Schemas use semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes (field removal, type changes)
- MINOR: Backward-compatible additions (new optional fields)
- PATCH: Documentation or validation clarifications

## Integration Points

### Services Using at-core

| Service | Usage |
|---------|-------|
| at-gateway | Schema validation, event creation |
| at-agent-mcp | Signal validation, order intent creation |
| at-exec-sim | Order validation, fill creation |
| at-observability | Schema validation for metrics |

### Import Examples

```python
# Full import
import at_core

# Specific imports
from at_core import validate_event, create_order_intent
from at_core.validators import SchemaRegistry
from at_core.events import generate_correlation_id
```

## Performance Considerations

- Schemas are loaded once at startup and cached
- Validation is performed using jsonschema's Draft202012Validator
- Event creation helpers are pure functions with minimal overhead

## Security Notes

- All events require correlation IDs for tracing
- Sensitive data should never be included in events
- Use environment-specific secrets for HMAC validation (handled by services, not at-core)
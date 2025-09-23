# ADR-0002: Event Contracts

## Status
Accepted

## Context

In an event-driven architecture with multiple repositories, we need a robust way to handle schema evolution while maintaining system stability. Trading systems require:
- Strict data validation to prevent costly errors
- Ability to evolve schemas as strategies change
- Compatibility across different service versions during deployments
- Clear versioning for audit and compliance purposes

Without proper contract management, schema changes can break the entire system or create subtle bugs that only surface during market conditions.

## Decision

We will implement versioned event contracts using JSON Schema with the following approach:

### Schema Definition
- All event schemas defined in at-core repository
- JSON Schema format with semantic versioning (MAJOR.MINOR.PATCH)
- Schema files organized by subject: `schemas/signals/v1.0.0.json`

### Versioning Policy
- **MAJOR**: Breaking changes (field removal, type changes)
- **MINOR**: Backward-compatible additions (new optional fields)
- **PATCH**: Documentation, validation rule clarifications

### Evolution Process
1. **Propose**: Submit schema change with migration plan
2. **Dual-write**: Producers emit both old and new versions
3. **Consumer migration**: Update consumers to handle new version
4. **Deprecation**: Mark old version deprecated after full migration
5. **Cleanup**: Remove old version after deprecation period

### Breaking Change Management
- Minimum 30-day dual-write period for breaking changes
- Contract tests in each repository verify compatibility
- Automated alerts when deprecated schemas are used

### Implementation
```python
# Schema validation in each service
from at_core.schemas import validate_event

@event_handler("signals.normalized")
def handle_signal(event_data):
    validated_data = validate_event("signals.normalized", "1.2.0", event_data)
    # Process validated data
```

## Consequences

### Positive
- **Safe evolution**: Changes can be made without breaking existing consumers
- **Clear compatibility**: Contract tests catch breaking changes early
- **Audit trail**: Schema versions provide clear history of changes
- **Faster deployments**: Services can be deployed independently during migrations

### Negative
- **Complexity**: Dual-write periods require coordination and monitoring
- **Storage overhead**: Multiple schema versions increase payload size temporarily
- **Migration discipline**: Teams must follow the process strictly to avoid issues

### Tooling Requirements
- Schema registry service for version management
- Contract testing framework
- Migration status dashboard
- Automated compatibility checking in CI/CD

### Monitoring
- Track schema version usage across services
- Alert on deprecated schema usage
- Monitor migration progress during dual-write periods
- Measure schema validation performance impact
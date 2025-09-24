# NEO-001: Schema Registry Implementation

**Phase**: 0 - Foundation Package
**Priority**: CRITICAL
**Status**: 🔄 IN_PROGRESS
**Assignee**: Claude
**Created**: 2025-09-24

## Scope

Implement complete JSONSchema v1 registry with validation utilities for all message contracts.

### Files to Create
- `at-core/schemas/SignalEventV1.json`
- `at-core/schemas/AgentOutputV1.json`
- `at-core/schemas/OrderIntentV1.json`
- `at-core/schemas/__init__.py`
- `at-core/validators.py`
- `at-core/CHANGELOG.md`
- `at-core/SCHEMA_EVOLUTION_POLICY.md`

### Technical Requirements
- All schemas use JSONSchema Draft 2020-12
- Semantic versioning with `schema_version` field
- Schema caching for performance
- Validation utilities with proper error handling
- Reference to evolution policy

## Definition of Done

### Functional Requirements
- [ ] All three schemas validate successfully with jsonschema library
- [ ] Schema loading utilities with caching implemented
- [ ] Validation functions work with sample payloads
- [ ] Schema evolution policy documented and referenced
- [ ] CHANGELOG.md tracks schema versions

### Technical Requirements
- [ ] Schemas follow naming conventions and include required fields
- [ ] Validation utilities handle edge cases and provide clear errors
- [ ] Schema IDs are globally unique and versioned
- [ ] Proper imports and module structure in place

### Testing Requirements
- [ ] Unit tests for schema loading and validation
- [ ] Sample payloads validate against schemas
- [ ] Error cases handled gracefully
- [ ] Performance acceptable for high-frequency validation

## Implementation Steps

1. Create directory structure: `at-core/schemas/`
2. Implement SignalEventV1.json with all required fields
3. Implement AgentOutputV1.json with embedded order intents
4. Implement OrderIntentV1.json for execution
5. Create schema loading utilities with caching
6. Implement validation functions and error handling
7. Add changelog and policy references
8. Create unit tests and validation checks

## Dependencies

- None (foundational component)

## Rollback Procedure

```bash
# Remove schema registry if issues found
rm -rf at-core/schemas/
rm at-core/validators.py
rm at-core/CHANGELOG.md
rm at-core/SCHEMA_EVOLUTION_POLICY.md
git checkout HEAD -- at-core/
```

## Testing Strategy

### Unit Tests
- Schema loading with valid/invalid files
- Validation with conforming/non-conforming payloads
- Caching performance and correctness
- Error message clarity and helpfulness

### Integration Tests
- Schema registry works with existing services
- Validation integrates with NATS message processing
- Performance under load (1000+ validations/second)

## Success Criteria

- All schemas load without errors
- Sample payloads from existing services validate successfully
- Validation is fast enough for real-time processing (<1ms per validation)
- Clear error messages help debug schema violations
- Foundation ready for contract testing in subsequent tickets

## Notes

- Use the complete schema definitions from the code drop
- Ensure compatibility with existing `at-core` module structure
- Schema evolution policy is reference-only (detailed policy in workspace)
- This is a foundational component - all subsequent phases depend on it

**Last Updated**: 2025-09-24
# Schema Registry

**Governance and versioning for event schemas in the agentic trading architecture.**

## Schema Organization

### Naming Convention
```
schemas/<domain>.<type>.schema.json
```

**Examples**:
- `signals.raw.schema.json` - Raw webhook signals from external sources
- `signals.normalized.schema.json` - Processed signals ready for agent consumption
- `decisions.entry.schema.json` - Trade entry decisions (future)
- `executions.filled.schema.json` - Execution confirmations (future)

### Schema Structure
All schemas must:
- Use **JSON Schema Draft 2020-12**
- Include `$schema`, `$id`, `title`, `description`
- Set `additionalProperties: false` for strict validation
- Embed valid examples in `examples` array
- Include `version` field in schema metadata

**Template**:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.trading.example.com/signals.raw.v1.json",
  "title": "Raw Trading Signal",
  "description": "Incoming webhook signal before normalization",
  "version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["corr_id", "source", "received_at", "payload"],
  "properties": {
    // ... field definitions
  },
  "examples": [
    // ... valid sample data
  ]
}
```

## Versioning Strategy

### Semantic Versioning
Schemas follow **semantic versioning (semver)**:

- **MAJOR.MINOR.PATCH** (e.g., `1.2.3`)
- **MAJOR**: Breaking changes (remove field, change type, add required field)
- **MINOR**: Backwards-compatible additions (add optional field, extend enum)
- **PATCH**: Documentation or example updates

### Version Examples

**✅ MINOR version bump (1.0.0 → 1.1.0)**:
```diff
// signals.raw.schema.json
{
  "properties": {
    "corr_id": {"type": "string"},
    "source": {"enum": ["tradingview", "custom"]},
+   "priority": {"type": "string", "enum": ["low", "high"]}
  }
}
```

**❌ MAJOR version bump required (1.1.0 → 2.0.0)**:
```diff
// signals.raw.schema.json
{
  "required": [
    "corr_id",
    "source",
-   "received_at",
+   "timestamp",  // Field renamed - breaking change
    "payload"
  ]
}
```

### Backwards Compatibility

**Support Policy**:
- **12 months** backwards compatibility for MAJOR versions
- **Immediate** compatibility for MINOR/PATCH versions
- **Dual schema support** during migration periods

**Migration Process**:
1. **Announce**: 90-day advance notice for breaking changes
2. **Dual support**: Publish new schema, maintain old schema
3. **Migration window**: Services update to new schema
4. **Deprecation**: Remove old schema after 12 months

### Versioning Examples

**Current state**: `signals.raw.schema.json` (v1.0.0)

**Step 1 - Add new schema**:
```bash
# Create new major version
cp signals.raw.schema.json signals.raw.v2.schema.json
# Edit signals.raw.v2.schema.json with breaking changes
```

**Step 2 - Update services**:
```python
# Services support both versions during migration
try:
    validate(data, schema_v2)
except ValidationError:
    validate(data, schema_v1)  # Fallback to old schema
```

**Step 3 - Deprecate old version**:
```json
// signals.raw.schema.json (v1.0.0)
{
  "deprecated": true,
  "deprecationDate": "2024-06-01",
  "replacedBy": "signals.raw.v2.schema.json",
  // ... rest of schema
}
```

## Schema Change Process

### 1. Request Schema Change
**Create ADR** in `DECISIONS/ADR-XXXX-schema-change-[domain].md`:

```markdown
# ADR-0010: Add Priority Field to Raw Signals

## Context
Trading strategies need to prioritize urgent signals during high-volatility periods.

## Decision
Add optional "priority" field to signals.raw schema v1.1.0.

## Schema Change
- **Type**: MINOR (backwards compatible)
- **Field**: priority (string, enum: ["low", "normal", "high"])
- **Default**: "normal" if not specified
```

### 2. Implement Schema
**Update schema file**:
```json
{
  "version": "1.1.0",
  "properties": {
    "priority": {
      "type": "string",
      "enum": ["low", "normal", "high"],
      "default": "normal",
      "description": "Signal processing priority"
    }
  }
}
```

### 3. Update Tests
**Add test cases**:
```python
# tests/test_signals_raw.py
def test_priority_field_optional():
    # Should validate without priority field
    signal = {"corr_id": "test", "source": "tradingview", ...}
    validate(signal, schema)

def test_priority_field_valid_values():
    for priority in ["low", "normal", "high"]:
        signal = {"priority": priority, ...}
        validate(signal, schema)
```

### 4. Communication
**Announce change**:
- Slack #trading-platform: "🔄 Schema Update: signals.raw v1.1.0 adds optional priority field"
- GitHub Discussion: Post migration timeline
- Update CHANGELOG.md with breaking change notice

## Deprecation Policy

### Deprecation Timeline
1. **T-90 days**: Announce deprecation, publish new schema
2. **T-60 days**: All new services must use new schema
3. **T-30 days**: Warning logs for old schema usage
4. **T-0 days**: Old schema removed, validation fails

### Deprecation Markers
```json
{
  "deprecated": true,
  "deprecationDate": "2024-12-01",
  "removalDate": "2025-03-01",
  "replacedBy": "signals.raw.v2.schema.json",
  "migrationGuide": "https://docs.trading.example.com/migrations/signals-v2"
}
```

### Migration Support
**Provide migration tooling**:
```python
# tools/migrate_signals_v1_to_v2.py
def migrate_signal_v1_to_v2(v1_signal):
    """Convert v1 signal format to v2."""
    return {
        "correlation_id": v1_signal["corr_id"],  # Field renamed
        "source_system": v1_signal["source"],   # Field renamed
        "received_timestamp": v1_signal["received_at"],
        "data": v1_signal["payload"]
    }
```

## Schema Validation

### Automated Checks
**CI/CD pipeline validates**:
- Schema syntax with `jsonschema` library
- All examples pass validation
- Backwards compatibility with `json-schema-diff`
- No breaking changes in MINOR/PATCH versions

### Manual Review
**Schema changes require**:
- Architecture team approval for MAJOR versions
- Product team approval for new domains
- Security review for sensitive data fields
- Performance impact assessment for large schemas

## Error Handling

### Validation Failures
**When schema validation fails**:
1. Log error with correlation ID and schema version
2. Return structured error response (see ERROR_CATALOG.md)
3. Increment `core_schema_validation_errors_total` metric
4. Alert if error rate > 5% over 5 minutes

### Version Mismatches
**When service uses unsupported schema version**:
1. Check if version is deprecated but still supported
2. Log warning with migration timeline
3. For unsupported versions, return CORE-002 error
4. Include supported version list in error response

## Governance

### Schema Ownership
- **Domain experts**: Propose functional changes
- **Architecture team**: Approve structural changes
- **Platform team**: Maintain registry infrastructure
- **Security team**: Review sensitive data handling

### Review Process
1. **Functional review**: Domain expert approves business logic
2. **Technical review**: Architecture team validates design
3. **Security review**: Security team checks for data exposure
4. **Impact assessment**: Platform team estimates migration effort

### Change Approval Matrix
| Change Type | Domain Expert | Architecture Team | Security Team | Platform Team |
|-------------|---------------|-------------------|---------------|--------------|
| PATCH | ✅ Required | 📝 Informed | 📝 Informed | 📝 Informed |
| MINOR | ✅ Required | ✅ Required | 📝 Informed | 📝 Informed |
| MAJOR | ✅ Required | ✅ Required | ✅ Required | ✅ Required |

---

**For questions about schema governance, contact the Architecture team via #architecture Slack channel.**
# Error Catalog - Core Contracts

**Standardized error codes for schema validation and contract enforcement.**

## Error Code Namespace

All core contract errors use the **CORE-XXX** namespace:
- **CORE-001** to **CORE-099**: Schema validation errors
- **CORE-100** to **CORE-199**: Versioning and compatibility errors
- **CORE-200** to **CORE-299**: Contract enforcement errors

## Error Response Format

All errors return a standardized JSON response:

```json
{
  "error": true,
  "code": "CORE-001",
  "message": "Schema validation failed",
  "corr_id": "req_abc123",
  "details": {
    "schema": "signals.raw.v1",
    "field": "payload.price",
    "reason": "Value must be a number"
  },
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

## Schema Validation Errors (CORE-001 to CORE-099)

### CORE-001: Schema Validation Failed

**When it happens**: Incoming data doesn't match the required schema structure.

**HTTP Status**: `400 Bad Request`

**Common causes**:
- Missing required fields
- Invalid data types
- Values outside allowed ranges
- Unknown fields when `additionalProperties: false`

**Example error**:
```json
{
  "error": true,
  "code": "CORE-001",
  "message": "Schema validation failed: missing required field 'corr_id'",
  "corr_id": "req_def456",
  "details": {
    "schema": "signals.raw.v1.0.0",
    "violations": [
      {
        "field": "corr_id",
        "error": "required field missing"
      }
    ]
  }
}
```

**Operator fix**:
1. Check recent schema changes for new required fields
2. Verify client is using correct schema version
3. Review gateway logs for payload patterns: `grep "CORE-001" /var/log/at-gateway.log`

**Client fix**:
1. Validate payload against current schema before sending
2. Ensure all required fields are present
3. Check data types match schema expectations

**Telemetry fields**:
```json
{
  "error_code": "CORE-001",
  "schema_name": "signals.raw",
  "schema_version": "1.0.0",
  "validation_field": "corr_id",
  "client_ip": "203.0.113.42"
}
```

### CORE-002: Schema Version Unsupported

**When it happens**: Client requests validation against a schema version that's no longer supported.

**HTTP Status**: `400 Bad Request`

**Common causes**:
- Using deprecated schema version beyond support window
- Requesting non-existent schema version
- Schema version format incorrect

**Example error**:
```json
{
  "error": true,
  "code": "CORE-002",
  "message": "Schema version 'signals.raw.v0.9.0' is no longer supported",
  "corr_id": "req_ghi789",
  "details": {
    "requested_version": "0.9.0",
    "supported_versions": ["1.0.0", "1.1.0"],
    "migration_guide": "https://docs.trading.example.com/migrations/signals-v1"
  }
}
```

**Operator fix**:
1. Check deprecation timeline: `grep "deprecated" schemas/signals.raw.schema.json`
2. Verify client migration status
3. Extend support window if business critical

**Client fix**:
1. Upgrade to supported schema version
2. Follow migration guide in error response
3. Update validation code to use new schema

**Telemetry fields**:
```json
{
  "error_code": "CORE-002",
  "requested_version": "0.9.0",
  "latest_version": "1.1.0",
  "client_user_agent": "TradingBot/1.2.3"
}
```

### CORE-003: Backwards Incompatibility Detected

**When it happens**: Schema change would break existing clients without proper versioning.

**HTTP Status**: `500 Internal Server Error` (this should not happen in production)

**Common causes**:
- Breaking change deployed without version bump
- Schema validation rules became stricter
- Required field added without migration period

**Example error**:
```json
{
  "error": true,
  "code": "CORE-003",
  "message": "Backwards incompatible change detected in schema",
  "corr_id": "req_jkl012",
  "details": {
    "schema": "signals.normalized.v1.0.0",
    "breaking_change": "field 'side' is now required",
    "impact": "Existing clients will fail validation"
  }
}
```

**Operator fix**:
1. **Immediate**: Rollback schema change
2. Create proper MAJOR version with migration plan
3. Communicate breaking change to all consumers
4. Review change approval process

**Client fix**:
- No client action required; this is a service-side error
- Wait for proper schema migration announcement

**Telemetry fields**:
```json
{
  "error_code": "CORE-003",
  "schema_name": "signals.normalized",
  "previous_version": "1.0.0",
  "current_version": "1.0.1",
  "breaking_change_type": "required_field_added"
}
```

## Versioning Errors (CORE-100 to CORE-199)

### CORE-101: Schema Not Found

**When it happens**: Requested schema file doesn't exist in the registry.

**HTTP Status**: `404 Not Found`

**Common causes**:
- Typo in schema name
- Schema was removed or relocated
- Client using outdated schema reference

**Example error**:
```json
{
  "error": true,
  "code": "CORE-101",
  "message": "Schema 'signals.premium.v1' not found",
  "corr_id": "req_mno345",
  "details": {
    "requested_schema": "signals.premium.v1",
    "available_schemas": [
      "signals.raw.v1",
      "signals.normalized.v1"
    ]
  }
}
```

**Operator fix**:
1. Check if schema was accidentally removed
2. Verify schema naming conventions
3. Update schema registry index

**Client fix**:
1. Verify schema name spelling
2. Check available schemas in error response
3. Update client configuration

**Telemetry fields**:
```json
{
  "error_code": "CORE-101",
  "requested_schema": "signals.premium.v1",
  "schema_lookup_path": "/schemas/signals.premium.schema.json"
}
```

### CORE-102: Version Format Invalid

**When it happens**: Schema version doesn't follow semantic versioning format.

**HTTP Status**: `400 Bad Request`

**Common causes**:
- Non-semver version string (e.g., "v1", "latest")
- Invalid version format (e.g., "1.0")
- Version contains invalid characters

**Example error**:
```json
{
  "error": true,
  "code": "CORE-102",
  "message": "Invalid version format 'latest'",
  "corr_id": "req_pqr678",
  "details": {
    "provided_version": "latest",
    "expected_format": "MAJOR.MINOR.PATCH (e.g., 1.0.0)",
    "valid_examples": ["1.0.0", "2.1.3"]
  }
}
```

**Operator fix**:
1. Review client integration documentation
2. Add version format validation to CI/CD
3. Provide clear examples in API documentation

**Client fix**:
1. Use semantic versioning format (x.y.z)
2. Replace "latest" with specific version number
3. Check schema registry for available versions

**Telemetry fields**:
```json
{
  "error_code": "CORE-102",
  "provided_version": "latest",
  "version_format_attempted": "string"
}
```

## Contract Enforcement Errors (CORE-200 to CORE-299)

### CORE-201: Contract Violation

**When it happens**: Data violates business rules defined in schema annotations.

**HTTP Status**: `422 Unprocessable Entity`

**Common causes**:
- Business logic constraints violated
- Cross-field validation failures
- Temporal constraints not met

**Example error**:
```json
{
  "error": true,
  "code": "CORE-201",
  "message": "Contract violation: signal timestamp is more than 5 minutes old",
  "corr_id": "req_stu901",
  "details": {
    "rule": "signal_freshness",
    "constraint": "timestamp must be within 5 minutes of received_at",
    "signal_timestamp": "2024-01-15T10:00:00Z",
    "received_at": "2024-01-15T10:06:30Z",
    "age_seconds": 390
  }
}
```

**Operator fix**:
1. Review contract rules for business validity
2. Check if client clocks are synchronized
3. Consider adjusting time window constraints

**Client fix**:
1. Ensure timestamps are current when sending signals
2. Synchronize system clocks with NTP
3. Send signals immediately after generation

**Telemetry fields**:
```json
{
  "error_code": "CORE-201",
  "contract_rule": "signal_freshness",
  "constraint_value": 300,
  "actual_value": 390
}
```

## Error Handling Best Practices

### For Service Developers

**Validation sequence**:
1. **Schema validation**: Check structure and types
2. **Business rules**: Validate contracts and constraints
3. **Processing**: Only process valid, compliant data

**Error response**:
```python
# Example error handling in FastAPI
from fastapi import HTTPException

try:
    validate(payload, schema)
except ValidationError as e:
    raise HTTPException(
        status_code=400,
        detail={
            "error": True,
            "code": "CORE-001",
            "message": f"Schema validation failed: {e.message}",
            "corr_id": correlation_id,
            "details": {
                "schema": schema_name,
                "violations": format_validation_errors(e)
            }
        }
    )
```

### For Client Developers

**Client-side validation**:
```python
import json
from jsonschema import validate, ValidationError

def validate_before_send(payload, schema_path):
    """Validate payload locally before sending to avoid server errors."""
    with open(schema_path) as f:
        schema = json.load(f)
    
    try:
        validate(instance=payload, schema=schema)
        return True
    except ValidationError as e:
        print(f"Validation failed: {e.message}")
        return False

# Use before sending webhook
if validate_before_send(signal_data, 'schemas/signals.raw.schema.json'):
    response = requests.post('/webhook/tradingview', json=signal_data)
else:
    print("Signal invalid, not sending")
```

### Monitoring and Alerting

**Key metrics**:
- `core_validation_errors_total{code, schema}` - Error rate by type
- `core_schema_version_usage{schema, version}` - Version adoption
- `core_backwards_compat_violations_total` - Breaking changes detected

**Alert thresholds**:
- **Critical**: > 10% validation error rate over 5 minutes
- **Warning**: > 5% errors for single schema over 10 minutes
- **Info**: New schema version usage detected

---

**For operational questions about error handling, see [RUNBOOK.md](RUNBOOK.md) or contact #trading-platform-alerts.**
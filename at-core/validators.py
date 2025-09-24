"""
Schema validation utilities for NEO message contracts.

Provides fast validation for SignalEventV1, AgentOutputV1, and OrderIntentV1
with caching and clear error handling.
"""

from jsonschema import Draft202012Validator, ValidationError
from typing import Dict, Any, Optional
import structlog

from .schemas import SIGNAL_EVENT_V1, AGENT_OUTPUT_V1, ORDER_INTENT_V1

logger = structlog.get_logger()

# Pre-compiled validators for performance
_validators = {
    "SignalEventV1": Draft202012Validator(SIGNAL_EVENT_V1),
    "AgentOutputV1": Draft202012Validator(AGENT_OUTPUT_V1),
    "OrderIntentV1": Draft202012Validator(ORDER_INTENT_V1),
}

class SchemaValidationError(Exception):
    """Raised when message payload doesn't conform to schema."""

    def __init__(self, schema_name: str, errors: list, payload_snippet: Optional[str] = None):
        self.schema_name = schema_name
        self.errors = errors
        self.payload_snippet = payload_snippet

        error_summary = "; ".join(str(err.message) for err in errors[:3])
        if len(errors) > 3:
            error_summary += f" (and {len(errors) - 3} more)"

        super().__init__(f"Schema validation failed for {schema_name}: {error_summary}")


def validate(schema_name: str, payload: Dict[str, Any], *, strict: bool = True) -> None:
    """
    Validate a message payload against the specified schema.

    Args:
        schema_name: Schema identifier ("SignalEventV1", "AgentOutputV1", "OrderIntentV1")
        payload: Message payload to validate
        strict: If True, raise on any validation error. If False, log warnings only.

    Raises:
        SchemaValidationError: If validation fails and strict=True
        ValueError: If schema_name is not recognized
    """
    if schema_name not in _validators:
        raise ValueError(f"Unknown schema: {schema_name}. Available: {list(_validators.keys())}")

    validator = _validators[schema_name]
    errors = list(validator.iter_errors(payload))

    if errors:
        # Create payload snippet for debugging (truncate if too long)
        payload_str = str(payload)
        snippet = payload_str[:200] + "..." if len(payload_str) > 200 else payload_str

        logger.error(
            "Schema validation failed",
            schema=schema_name,
            error_count=len(errors),
            errors=[str(err.message) for err in errors[:5]],  # Limit to 5 errors
            payload_snippet=snippet
        )

        if strict:
            raise SchemaValidationError(schema_name, errors, snippet)
        else:
            logger.warning("Schema validation failed but continuing (strict=False)")


def validate_signal_event(payload: Dict[str, Any], *, strict: bool = True) -> None:
    """Convenience function for validating SignalEventV1 payloads."""
    validate("SignalEventV1", payload, strict=strict)


def validate_agent_output(payload: Dict[str, Any], *, strict: bool = True) -> None:
    """Convenience function for validating AgentOutputV1 payloads."""
    validate("AgentOutputV1", payload, strict=strict)


def validate_order_intent(payload: Dict[str, Any], *, strict: bool = True) -> None:
    """Convenience function for validating OrderIntentV1 payloads."""
    validate("OrderIntentV1", payload, strict=strict)


def get_schema_version(payload: Dict[str, Any]) -> Optional[str]:
    """
    Extract schema version from payload if present.

    Returns:
        Schema version string or None if not found
    """
    return payload.get("schema_version")


def is_supported_version(schema_name: str, version: str) -> bool:
    """
    Check if a schema version is supported.

    Args:
        schema_name: Schema identifier
        version: Version string to check

    Returns:
        True if version is supported, False otherwise
    """
    # For v1, we only support exactly "1.0.0"
    # Future versions will need more sophisticated logic
    supported_versions = {
        "SignalEventV1": ["1.0.0"],
        "AgentOutputV1": ["1.0.0"],
        "OrderIntentV1": ["1.0.0"],
    }

    return version in supported_versions.get(schema_name, [])


def validate_with_version_check(payload: Dict[str, Any]) -> str:
    """
    Auto-detect schema version and validate accordingly.

    Args:
        payload: Message payload with schema_version field

    Returns:
        Schema name that was used for validation

    Raises:
        SchemaValidationError: If validation fails
        ValueError: If schema version is not supported or missing
    """
    version = get_schema_version(payload)
    if not version:
        raise ValueError("Message payload missing required 'schema_version' field")

    # Map version to schema name (simple for v1)
    if version == "1.0.0":
        # Try each schema until one validates successfully
        for schema_name in ["SignalEventV1", "AgentOutputV1", "OrderIntentV1"]:
            try:
                validate(schema_name, payload, strict=True)
                return schema_name
            except SchemaValidationError:
                continue

        # If none validate, raise error with details
        raise SchemaValidationError("auto-detect", [], f"No schema matches version {version}")
    else:
        raise ValueError(f"Unsupported schema version: {version}")
"""
Contract testing helpers for NEO message validation.

Provides utilities for validating message contracts across service boundaries
and ensuring schema compliance in integration tests.
"""

from typing import Dict, Any, List, Optional, Tuple
import json
from jsonschema import validate, ValidationError, Draft202012Validator
import sys
import os

# Add at-core to path for schema access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'at-core'))

try:
    from schemas import SIGNAL_EVENT_V1, AGENT_OUTPUT_V1, ORDER_INTENT_V1
except ImportError:
    # Fallback to direct JSON loading if module import fails
    schema_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'at-core', 'schemas')

    with open(os.path.join(schema_dir, 'SignalEventV1.json')) as f:
        SIGNAL_EVENT_V1 = json.load(f)

    with open(os.path.join(schema_dir, 'AgentOutputV1.json')) as f:
        AGENT_OUTPUT_V1 = json.load(f)

    with open(os.path.join(schema_dir, 'OrderIntentV1.json')) as f:
        ORDER_INTENT_V1 = json.load(f)


# Schema registry
SCHEMAS = {
    "SignalEventV1": SIGNAL_EVENT_V1,
    "AgentOutputV1": AGENT_OUTPUT_V1,
    "OrderIntentV1": ORDER_INTENT_V1,
}

# Pre-compiled validators for performance
VALIDATORS = {
    name: Draft202012Validator(schema)
    for name, schema in SCHEMAS.items()
}


class ContractViolation(Exception):
    """Raised when a message violates its schema contract."""

    def __init__(self, schema_name: str, payload: Dict[str, Any], errors: List[ValidationError]):
        self.schema_name = schema_name
        self.payload = payload
        self.errors = errors

        error_summary = "; ".join(err.message for err in errors[:3])
        if len(errors) > 3:
            error_summary += f" (and {len(errors) - 3} more)"

        super().__init__(f"Contract violation in {schema_name}: {error_summary}")


def assert_conforms(schema_name: str, payload: Dict[str, Any]) -> None:
    """
    Assert that a payload conforms to the specified schema.

    Args:
        schema_name: Schema to validate against ("SignalEventV1", etc.)
        payload: Message payload to validate

    Raises:
        ContractViolation: If payload doesn't conform to schema
        ValueError: If schema_name is not recognized
    """
    if schema_name not in VALIDATORS:
        available = list(VALIDATORS.keys())
        raise ValueError(f"Unknown schema: {schema_name}. Available: {available}")

    validator = VALIDATORS[schema_name]
    errors = list(validator.iter_errors(payload))

    if errors:
        raise ContractViolation(schema_name, payload, errors)


def validate_signal_event(payload: Dict[str, Any]) -> bool:
    """
    Validate a SignalEventV1 payload.

    Returns:
        True if valid, False otherwise
    """
    try:
        assert_conforms("SignalEventV1", payload)
        return True
    except ContractViolation:
        return False


def validate_agent_output(payload: Dict[str, Any]) -> bool:
    """
    Validate an AgentOutputV1 payload.

    Returns:
        True if valid, False otherwise
    """
    try:
        assert_conforms("AgentOutputV1", payload)
        return True
    except ContractViolation:
        return False


def validate_order_intent(payload: Dict[str, Any]) -> bool:
    """
    Validate an OrderIntentV1 payload.

    Returns:
        True if valid, False otherwise
    """
    try:
        assert_conforms("OrderIntentV1", payload)
        return True
    except ContractViolation:
        return False


def get_schema_errors(schema_name: str, payload: Dict[str, Any]) -> List[str]:
    """
    Get detailed validation errors for a payload.

    Args:
        schema_name: Schema to validate against
        payload: Message payload to validate

    Returns:
        List of error messages (empty if valid)
    """
    if schema_name not in VALIDATORS:
        return [f"Unknown schema: {schema_name}"]

    validator = VALIDATORS[schema_name]
    errors = list(validator.iter_errors(payload))
    return [err.message for err in errors]


def contract_test_suite(payloads: List[Tuple[str, Dict[str, Any]]],
                       should_pass: bool = True) -> Dict[str, Any]:
    """
    Run contract validation on multiple payloads.

    Args:
        payloads: List of (schema_name, payload) tuples
        should_pass: Whether payloads are expected to pass validation

    Returns:
        Test results with pass/fail counts and error details
    """
    results = {
        "total": len(payloads),
        "passed": 0,
        "failed": 0,
        "errors": []
    }

    for schema_name, payload in payloads:
        try:
            assert_conforms(schema_name, payload)
            if should_pass:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "schema": schema_name,
                    "expected": "failure",
                    "actual": "success",
                    "payload": payload
                })
        except ContractViolation as e:
            if not should_pass:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "schema": schema_name,
                    "expected": "success",
                    "actual": "failure",
                    "errors": [err.message for err in e.errors],
                    "payload": payload
                })

    return results


def create_contract_test_payloads() -> Dict[str, List[Tuple[str, Dict[str, Any]]]]:
    """
    Create standard test payloads for contract validation.

    Returns:
        Dictionary with 'valid' and 'invalid' payload lists
    """
    import datetime as dt

    # Valid payloads
    valid_signal = {
        "schema_version": "1.0.0",
        "intent_id": "intent-123456",
        "correlation_id": "corr-123456",
        "source": "tradingview",
        "instrument": "BTCUSD",
        "type": "momentum",
        "strength": 0.82,
        "priority": "standard",
        "payload": {"price": 120000.25},
        "ts_iso": dt.datetime.now(dt.timezone.utc).isoformat()
    }

    valid_agent_output = {
        "schema_version": "1.0.0",
        "intent_id": "intent-123456",
        "agent": "test-agent",
        "confidence": 0.75,
        "summary": "BTC momentum signal confirmed",
        "recommendation": {
            "action": "alert",
            "orders": [{
                "instrument": "BTCUSD",
                "side": "buy",
                "qty": 0.1,
                "type": "limit",
                "limit_price": 119900.0
            }]
        },
        "rationale": "Strong upward momentum with volume confirmation",
        "risk": {
            "max_drawdown_pct": 2.5,
            "stop_loss": 118500.0,
            "take_profit": 121800.0
        },
        "metadata": {"confidence_factors": ["volume", "momentum"]},
        "ts_iso": dt.datetime.now(dt.timezone.utc).isoformat()
    }

    valid_order_intent = {
        "schema_version": "1.0.0",
        "order_id": "ord-123456",
        "intent_id": "intent-123456",
        "account": "paper-default",
        "instrument": "BTCUSD",
        "side": "buy",
        "qty": 0.1,
        "type": "limit",
        "limit_price": 119900.0,
        "time_in_force": "day",
        "ts_iso": dt.datetime.now(dt.timezone.utc).isoformat()
    }

    # Invalid payloads (missing required fields)
    invalid_signal = valid_signal.copy()
    del invalid_signal["instrument"]

    invalid_agent_output = valid_agent_output.copy()
    del invalid_agent_output["recommendation"]

    invalid_order_intent = valid_order_intent.copy()
    del invalid_order_intent["side"]

    return {
        "valid": [
            ("SignalEventV1", valid_signal),
            ("AgentOutputV1", valid_agent_output),
            ("OrderIntentV1", valid_order_intent),
        ],
        "invalid": [
            ("SignalEventV1", invalid_signal),
            ("AgentOutputV1", invalid_agent_output),
            ("OrderIntentV1", invalid_order_intent),
        ]
    }


# Test utilities for pytest integration

def pytest_contract_validator(schema_name: str):
    """
    Create a pytest fixture for contract validation.

    Usage:
        signal_validator = pytest_contract_validator("SignalEventV1")

        def test_my_signal(signal_validator):
            payload = {...}
            signal_validator(payload)  # Asserts compliance
    """
    def validator_fixture(payload: Dict[str, Any]):
        assert_conforms(schema_name, payload)

    validator_fixture.__name__ = f"{schema_name.lower()}_validator"
    return validator_fixture


if __name__ == "__main__":
    # Run basic contract test when called directly
    print("🧪 Running contract validation tests...")

    test_payloads = create_contract_test_payloads()

    valid_results = contract_test_suite(test_payloads["valid"], should_pass=True)
    invalid_results = contract_test_suite(test_payloads["invalid"], should_pass=False)

    print(f"✅ Valid payloads: {valid_results['passed']}/{valid_results['total']} passed")
    print(f"✅ Invalid payloads: {invalid_results['passed']}/{invalid_results['total']} correctly rejected")

    if valid_results["failed"] > 0 or invalid_results["failed"] > 0:
        print("❌ Some contract tests failed!")
        for error in valid_results["errors"] + invalid_results["errors"]:
            print(f"   {error['schema']}: {error}")
    else:
        print("🎉 All contract tests passed!")
"""
Contract tests for AgentOutputV1 schema.

These tests ensure that the AgentOutputV1 schema correctly validates
AI agent outputs and rejects invalid payloads.
"""

import pytest
from tests.utils.contract_helpers import assert_conforms, get_schema_errors


class TestAgentOutputV1Contract:
    """Test suite for AgentOutputV1 contract validation."""

    def test_valid_agent_output_conforms(self, sample_agent_output):
        """Test that a valid agent output passes contract validation."""
        assert_conforms("AgentOutputV1", sample_agent_output)

    def test_missing_required_field_rejected(self, invalid_agent_output_bad_confidence):
        """Test that agent outputs with invalid confidence are rejected."""
        # This fixture has confidence > 1.0 which violates schema
        with pytest.raises(Exception):  # ContractViolation
            assert_conforms("AgentOutputV1", invalid_agent_output_bad_confidence)

    @pytest.mark.parametrize("missing_field", [
        "schema_version",
        "intent_id",
        "agent",
        "confidence",
        "summary",
        "recommendation",
        "rationale",
        "risk",
        "metadata",
        "ts_iso"
    ])
    def test_missing_required_fields(self, sample_agent_output, missing_field):
        """Test that each required field is actually required."""
        invalid_output = sample_agent_output.copy()
        del invalid_output[missing_field]

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0
        assert any(missing_field in error for error in errors)

    @pytest.mark.parametrize("invalid_confidence", [
        -0.1,  # Below minimum
        1.1,   # Above maximum
        "0.5", # String instead of number
        None
    ])
    def test_invalid_confidence_rejected(self, sample_agent_output, invalid_confidence):
        """Test that confidence values outside 0-1 range are rejected."""
        invalid_output = sample_agent_output.copy()
        invalid_output["confidence"] = invalid_confidence

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_confidence", [
        0.0,   # Minimum
        0.5,   # Middle
        1.0,   # Maximum
        0.001, # Very small
        0.999  # Very close to maximum
    ])
    def test_valid_confidence_accepted(self, sample_agent_output, valid_confidence):
        """Test that confidence values in 0-1 range are accepted."""
        output = sample_agent_output.copy()
        output["confidence"] = valid_confidence

        assert_conforms("AgentOutputV1", output)

    def test_empty_summary_rejected(self, sample_agent_output):
        """Test that empty summary is rejected."""
        invalid_output = sample_agent_output.copy()
        invalid_output["summary"] = ""

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    def test_summary_must_be_string(self, sample_agent_output):
        """Test that summary must be a string."""
        invalid_output = sample_agent_output.copy()
        invalid_output["summary"] = 123

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    @pytest.mark.parametrize("invalid_action", [
        "invalid_action",
        123,
        None,
        ""
    ])
    def test_invalid_recommendation_action_rejected(self, sample_agent_output, invalid_action):
        """Test that invalid recommendation actions are rejected."""
        invalid_output = sample_agent_output.copy()
        invalid_output["recommendation"]["action"] = invalid_action

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_action", [
        "none",
        "analyze",
        "alert",
        "paper_order",
        "live_order"
    ])
    def test_valid_recommendation_actions_accepted(self, sample_agent_output, valid_action):
        """Test that all valid recommendation actions are accepted."""
        output = sample_agent_output.copy()
        output["recommendation"]["action"] = valid_action

        assert_conforms("AgentOutputV1", output)

    def test_recommendation_without_action_rejected(self, sample_agent_output):
        """Test that recommendation must have action field."""
        invalid_output = sample_agent_output.copy()
        del invalid_output["recommendation"]["action"]

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    def test_recommendation_orders_optional(self, sample_agent_output):
        """Test that recommendation orders are optional."""
        output = sample_agent_output.copy()
        del output["recommendation"]["orders"]

        # Should still be valid
        assert_conforms("AgentOutputV1", output)

    def test_embedded_order_intent_validation(self, sample_agent_output):
        """Test that embedded OrderIntentEmbed follows schema."""
        # Valid order should pass
        assert_conforms("AgentOutputV1", sample_agent_output)

        # Invalid order should fail
        invalid_output = sample_agent_output.copy()
        invalid_order = invalid_output["recommendation"]["orders"][0]
        del invalid_order["instrument"]  # Remove required field

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    @pytest.mark.parametrize("invalid_side", [
        "long",
        "short",
        "hold",
        123,
        None
    ])
    def test_embedded_order_invalid_side_rejected(self, sample_agent_output, invalid_side):
        """Test that embedded orders with invalid sides are rejected."""
        invalid_output = sample_agent_output.copy()
        invalid_output["recommendation"]["orders"][0]["side"] = invalid_side

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_side", ["buy", "sell"])
    def test_embedded_order_valid_sides_accepted(self, sample_agent_output, valid_side):
        """Test that embedded orders with valid sides are accepted."""
        output = sample_agent_output.copy()
        output["recommendation"]["orders"][0]["side"] = valid_side

        assert_conforms("AgentOutputV1", output)

    @pytest.mark.parametrize("invalid_qty", [
        0,     # Zero quantity
        -1,    # Negative quantity
        "1.0", # String instead of number
        None
    ])
    def test_embedded_order_invalid_quantity_rejected(self, sample_agent_output, invalid_qty):
        """Test that embedded orders with invalid quantities are rejected."""
        invalid_output = sample_agent_output.copy()
        invalid_output["recommendation"]["orders"][0]["qty"] = invalid_qty

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_qty", [
        0.001,  # Very small positive
        1.0,    # Standard
        1000.0  # Large
    ])
    def test_embedded_order_valid_quantities_accepted(self, sample_agent_output, valid_qty):
        """Test that embedded orders with valid quantities are accepted."""
        output = sample_agent_output.copy()
        output["recommendation"]["orders"][0]["qty"] = valid_qty

        assert_conforms("AgentOutputV1", output)

    @pytest.mark.parametrize("invalid_order_type", [
        "stop",
        "stop_limit",
        "trailing",
        123,
        None
    ])
    def test_embedded_order_invalid_type_rejected(self, sample_agent_output, invalid_order_type):
        """Test that embedded orders with invalid types are rejected."""
        invalid_output = sample_agent_output.copy()
        invalid_output["recommendation"]["orders"][0]["type"] = invalid_order_type

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_order_type", ["market", "limit"])
    def test_embedded_order_valid_types_accepted(self, sample_agent_output, valid_order_type):
        """Test that embedded orders with valid types are accepted."""
        output = sample_agent_output.copy()
        output["recommendation"]["orders"][0]["type"] = valid_order_type

        assert_conforms("AgentOutputV1", output)

    def test_limit_price_optional_for_market_orders(self, sample_agent_output):
        """Test that limit_price is optional for market orders."""
        output = sample_agent_output.copy()
        output["recommendation"]["orders"][0]["type"] = "market"

        # Remove limit_price
        if "limit_price" in output["recommendation"]["orders"][0]:
            del output["recommendation"]["orders"][0]["limit_price"]

        assert_conforms("AgentOutputV1", output)

    def test_time_in_force_optional(self, sample_agent_output):
        """Test that time_in_force is optional in embedded orders."""
        output = sample_agent_output.copy()

        # Remove time_in_force if present
        if "time_in_force" in output["recommendation"]["orders"][0]:
            del output["recommendation"]["orders"][0]["time_in_force"]

        assert_conforms("AgentOutputV1", output)

    @pytest.mark.parametrize("valid_tif", ["day", "gtc", "ioc", "fok"])
    def test_valid_time_in_force_accepted(self, sample_agent_output, valid_tif):
        """Test that valid time_in_force values are accepted."""
        output = sample_agent_output.copy()
        output["recommendation"]["orders"][0]["time_in_force"] = valid_tif

        assert_conforms("AgentOutputV1", output)

    def test_risk_fields_optional(self, sample_agent_output):
        """Test that individual risk fields are optional."""
        output = sample_agent_output.copy()

        # Remove individual risk fields
        risk_fields = ["max_drawdown_pct", "stop_loss", "take_profit"]
        for field in risk_fields:
            if field in output["risk"]:
                del output["risk"][field]

        # Risk object is required but individual fields are optional
        assert_conforms("AgentOutputV1", output)

    def test_risk_allows_additional_properties(self, sample_agent_output):
        """Test that risk object allows additional properties."""
        output = sample_agent_output.copy()
        output["risk"]["custom_risk_metric"] = 5.5
        output["risk"]["volatility"] = 0.25

        # Should accept additional risk properties
        assert_conforms("AgentOutputV1", output)

    def test_metadata_allows_arbitrary_properties(self, sample_agent_output):
        """Test that metadata accepts arbitrary JSON objects."""
        output = sample_agent_output.copy()

        test_metadata = [
            {},
            {"simple": "value"},
            {"complex": {"nested": {"data": [1, 2, 3]}}},
            {"array": [{"item": 1}, {"item": 2}]},
            {"numbers": 123, "booleans": True, "nulls": None}
        ]

        for metadata in test_metadata:
            output["metadata"] = metadata
            assert_conforms("AgentOutputV1", output)

    def test_rationale_must_be_string(self, sample_agent_output):
        """Test that rationale must be a string."""
        invalid_output = sample_agent_output.copy()
        invalid_output["rationale"] = {"structured": "rationale"}

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    def test_additional_properties_rejected(self, sample_agent_output):
        """Test that additional properties beyond schema are rejected."""
        invalid_output = sample_agent_output.copy()
        invalid_output["extra_field"] = "not_allowed"

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0
        assert any("additional" in error.lower() for error in errors)

    def test_wrong_schema_version_rejected(self, sample_agent_output):
        """Test that wrong schema versions are rejected."""
        invalid_output = sample_agent_output.copy()
        invalid_output["schema_version"] = "2.0.0"

        errors = get_schema_errors("AgentOutputV1", invalid_output)
        assert len(errors) > 0

    def test_multiple_orders_in_recommendation(self, sample_agent_output):
        """Test that recommendation can contain multiple orders."""
        output = sample_agent_output.copy()

        # Add second order
        second_order = {
            "instrument": "ETHUSD",
            "side": "sell",
            "qty": 5.0,
            "type": "limit",
            "limit_price": 4200.0
        }

        output["recommendation"]["orders"].append(second_order)

        assert_conforms("AgentOutputV1", output)

    def test_empty_orders_array_allowed(self, sample_agent_output):
        """Test that recommendation can have empty orders array."""
        output = sample_agent_output.copy()
        output["recommendation"]["orders"] = []

        assert_conforms("AgentOutputV1", output)
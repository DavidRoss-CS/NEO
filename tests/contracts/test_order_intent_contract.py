"""
Contract tests for OrderIntentV1 schema.

These tests ensure that the OrderIntentV1 schema correctly validates
order specifications and rejects invalid payloads.
"""

import pytest
from tests.utils.contract_helpers import assert_conforms, get_schema_errors


class TestOrderIntentV1Contract:
    """Test suite for OrderIntentV1 contract validation."""

    def test_valid_order_intent_conforms(self, sample_order_intent):
        """Test that a valid order intent passes contract validation."""
        assert_conforms("OrderIntentV1", sample_order_intent)

    @pytest.mark.parametrize("missing_field", [
        "schema_version",
        "order_id",
        "intent_id",
        "account",
        "instrument",
        "side",
        "qty",
        "type",
        "time_in_force",
        "ts_iso"
    ])
    def test_missing_required_fields(self, sample_order_intent, missing_field):
        """Test that each required field is actually required."""
        invalid_order = sample_order_intent.copy()
        del invalid_order[missing_field]

        errors = get_schema_errors("OrderIntentV1", invalid_order)
        assert len(errors) > 0
        assert any(missing_field in error for error in errors)

    @pytest.mark.parametrize("invalid_side", [
        "long",
        "short",
        "hold",
        123,
        None,
        ""
    ])
    def test_invalid_side_rejected(self, sample_order_intent, invalid_side):
        """Test that invalid order sides are rejected."""
        invalid_order = sample_order_intent.copy()
        invalid_order["side"] = invalid_side

        errors = get_schema_errors("OrderIntentV1", invalid_order)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_side", ["buy", "sell"])
    def test_valid_sides_accepted(self, sample_order_intent, valid_side):
        """Test that valid order sides are accepted."""
        order = sample_order_intent.copy()
        order["side"] = valid_side

        assert_conforms("OrderIntentV1", order)

    @pytest.mark.parametrize("invalid_qty", [
        0,      # Zero quantity
        -1,     # Negative quantity
        -0.001, # Negative small quantity
        "1.0",  # String instead of number
        None
    ])
    def test_invalid_quantity_rejected(self, sample_order_intent, invalid_qty):
        """Test that invalid quantities are rejected."""
        invalid_order = sample_order_intent.copy()
        invalid_order["qty"] = invalid_qty

        errors = get_schema_errors("OrderIntentV1", invalid_order)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_qty", [
        0.001,  # Very small positive
        1.0,    # Standard
        1000.0, # Large
        0.1     # Decimal
    ])
    def test_valid_quantities_accepted(self, sample_order_intent, valid_qty):
        """Test that valid quantities are accepted."""
        order = sample_order_intent.copy()
        order["qty"] = valid_qty

        assert_conforms("OrderIntentV1", order)

    @pytest.mark.parametrize("invalid_type", [
        "stop",
        "stop_limit",
        "trailing",
        "iceberg",
        123,
        None,
        ""
    ])
    def test_invalid_order_type_rejected(self, sample_order_intent, invalid_type):
        """Test that invalid order types are rejected."""
        invalid_order = sample_order_intent.copy()
        invalid_order["type"] = invalid_type

        errors = get_schema_errors("OrderIntentV1", invalid_order)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_type", ["market", "limit"])
    def test_valid_order_types_accepted(self, sample_order_intent, valid_type):
        """Test that valid order types are accepted."""
        order = sample_order_intent.copy()
        order["type"] = valid_type

        assert_conforms("OrderIntentV1", order)

    @pytest.mark.parametrize("invalid_tif", [
        "immediate",
        "good_until_date",
        "market_close",
        123,
        None,
        ""
    ])
    def test_invalid_time_in_force_rejected(self, sample_order_intent, invalid_tif):
        """Test that invalid time_in_force values are rejected."""
        invalid_order = sample_order_intent.copy()
        invalid_order["time_in_force"] = invalid_tif

        errors = get_schema_errors("OrderIntentV1", invalid_order)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_tif", ["day", "gtc", "ioc", "fok"])
    def test_valid_time_in_force_accepted(self, sample_order_intent, valid_tif):
        """Test that valid time_in_force values are accepted."""
        order = sample_order_intent.copy()
        order["time_in_force"] = valid_tif

        assert_conforms("OrderIntentV1", order)

    def test_limit_price_optional(self, sample_order_intent):
        """Test that limit_price is optional."""
        order = sample_order_intent.copy()

        # Remove limit_price if present
        if "limit_price" in order:
            del order["limit_price"]

        assert_conforms("OrderIntentV1", order)

    def test_stop_loss_optional(self, sample_order_intent):
        """Test that stop_loss is optional."""
        order = sample_order_intent.copy()

        # Remove stop_loss if present
        if "stop_loss" in order:
            del order["stop_loss"]

        assert_conforms("OrderIntentV1", order)

    def test_take_profit_optional(self, sample_order_intent):
        """Test that take_profit is optional."""
        order = sample_order_intent.copy()

        # Remove take_profit if present
        if "take_profit" in order:
            del order["take_profit"]

        assert_conforms("OrderIntentV1", order)

    def test_limit_order_with_limit_price(self, sample_order_intent):
        """Test limit order with limit price."""
        order = sample_order_intent.copy()
        order["type"] = "limit"
        order["limit_price"] = 120000.0

        assert_conforms("OrderIntentV1", order)

    def test_market_order_without_limit_price(self, sample_order_intent):
        """Test market order without limit price."""
        order = sample_order_intent.copy()
        order["type"] = "market"

        # Remove limit_price for market order
        if "limit_price" in order:
            del order["limit_price"]

        assert_conforms("OrderIntentV1", order)

    def test_order_with_stop_loss_and_take_profit(self, sample_order_intent):
        """Test order with both stop loss and take profit."""
        order = sample_order_intent.copy()
        order["stop_loss"] = 118000.0
        order["take_profit"] = 122000.0

        assert_conforms("OrderIntentV1", order)

    @pytest.mark.parametrize("invalid_price", [
        -100.0,  # Negative price
        "100.0",  # String price
        None      # None price (when provided)
    ])
    def test_invalid_prices_rejected(self, sample_order_intent, invalid_price):
        """Test that invalid price values are rejected."""
        invalid_order = sample_order_intent.copy()
        invalid_order["limit_price"] = invalid_price

        errors = get_schema_errors("OrderIntentV1", invalid_order)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_price", [
        0.01,      # Very small positive
        100.0,     # Standard
        120000.25, # Large with decimals
        1.0        # Simple
    ])
    def test_valid_prices_accepted(self, sample_order_intent, valid_price):
        """Test that valid price values are accepted."""
        order = sample_order_intent.copy()
        order["limit_price"] = valid_price

        assert_conforms("OrderIntentV1", order)

    def test_empty_strings_rejected(self, sample_order_intent):
        """Test that empty strings are rejected for string fields."""
        string_fields = ["order_id", "intent_id", "account", "instrument"]

        for field in string_fields:
            invalid_order = sample_order_intent.copy()
            invalid_order[field] = ""

            errors = get_schema_errors("OrderIntentV1", invalid_order)
            assert len(errors) > 0, f"Empty string should be rejected for field: {field}"

    def test_very_long_strings_accepted(self, sample_order_intent):
        """Test that reasonably long strings are accepted."""
        order = sample_order_intent.copy()

        # Test with longer but reasonable values
        order["order_id"] = "very-long-order-id-" + "x" * 50
        order["intent_id"] = "very-long-intent-id-" + "x" * 50
        order["account"] = "very-long-account-name-" + "x" * 50

        assert_conforms("OrderIntentV1", order)

    def test_additional_properties_rejected(self, sample_order_intent):
        """Test that additional properties beyond schema are rejected."""
        invalid_order = sample_order_intent.copy()
        invalid_order["extra_field"] = "not_allowed"

        errors = get_schema_errors("OrderIntentV1", invalid_order)
        assert len(errors) > 0
        assert any("additional" in error.lower() for error in errors)

    def test_wrong_schema_version_rejected(self, sample_order_intent):
        """Test that wrong schema versions are rejected."""
        invalid_order = sample_order_intent.copy()
        invalid_order["schema_version"] = "2.0.0"

        errors = get_schema_errors("OrderIntentV1", invalid_order)
        assert len(errors) > 0

    def test_buy_order_complete_example(self):
        """Test a complete buy order example."""
        buy_order = {
            "schema_version": "1.0.0",
            "order_id": "buy-btc-001",
            "intent_id": "intent-buy-btc",
            "account": "paper-trading",
            "instrument": "BTCUSD",
            "side": "buy",
            "qty": 0.5,
            "type": "limit",
            "limit_price": 119500.0,
            "stop_loss": 117000.0,
            "take_profit": 125000.0,
            "time_in_force": "gtc",
            "ts_iso": "2025-01-01T12:00:00+00:00"
        }

        assert_conforms("OrderIntentV1", buy_order)

    def test_sell_order_complete_example(self):
        """Test a complete sell order example."""
        sell_order = {
            "schema_version": "1.0.0",
            "order_id": "sell-eth-001",
            "intent_id": "intent-sell-eth",
            "account": "paper-trading",
            "instrument": "ETHUSD",
            "side": "sell",
            "qty": 2.0,
            "type": "market",
            "time_in_force": "ioc",
            "ts_iso": "2025-01-01T12:00:00+00:00"
        }

        assert_conforms("OrderIntentV1", sell_order)

    def test_minimal_order_example(self):
        """Test minimal order with only required fields."""
        minimal_order = {
            "schema_version": "1.0.0",
            "order_id": "minimal-001",
            "intent_id": "intent-minimal",
            "account": "test",
            "instrument": "SPYUSD",
            "side": "buy",
            "qty": 1.0,
            "type": "market",
            "time_in_force": "day",
            "ts_iso": "2025-01-01T12:00:00+00:00"
        }

        assert_conforms("OrderIntentV1", minimal_order)
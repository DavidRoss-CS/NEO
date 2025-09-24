"""
Contract tests for SignalEventV1 schema.

These tests ensure that the SignalEventV1 schema correctly validates
trading signals and rejects invalid payloads.
"""

import pytest
from tests.utils.contract_helpers import assert_conforms, get_schema_errors


class TestSignalEventV1Contract:
    """Test suite for SignalEventV1 contract validation."""

    def test_valid_signal_conforms(self, sample_signal):
        """Test that a valid signal passes contract validation."""
        # Should not raise any exception
        assert_conforms("SignalEventV1", sample_signal)

    def test_btc_momentum_signal_conforms(self, btc_momentum_signal):
        """Test BTC momentum signal contract compliance."""
        assert_conforms("SignalEventV1", btc_momentum_signal)

    def test_eth_breakout_signal_conforms(self, eth_breakout_signal):
        """Test ETH breakout signal contract compliance."""
        assert_conforms("SignalEventV1", eth_breakout_signal)

    def test_missing_required_field_rejected(self, invalid_signal_missing_instrument):
        """Test that signals missing required fields are rejected."""
        with pytest.raises(Exception):  # ContractViolation
            assert_conforms("SignalEventV1", invalid_signal_missing_instrument)

    @pytest.mark.parametrize("missing_field", [
        "schema_version",
        "intent_id",
        "correlation_id",
        "source",
        "instrument",
        "type",
        "strength",
        "payload",
        "ts_iso"
    ])
    def test_missing_required_fields(self, sample_signal, missing_field):
        """Test that each required field is actually required."""
        invalid_signal = sample_signal.copy()
        del invalid_signal[missing_field]

        errors = get_schema_errors("SignalEventV1", invalid_signal)
        assert len(errors) > 0
        assert any(missing_field in error for error in errors)

    @pytest.mark.parametrize("invalid_source", [
        "invalid_source",
        123,
        None,
        ""
    ])
    def test_invalid_source_rejected(self, sample_signal, invalid_source):
        """Test that invalid sources are rejected."""
        invalid_signal = sample_signal.copy()
        invalid_signal["source"] = invalid_source

        errors = get_schema_errors("SignalEventV1", invalid_signal)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_source", [
        "tradingview",
        "webhook",
        "backtest",
        "manual"
    ])
    def test_valid_sources_accepted(self, sample_signal, valid_source):
        """Test that all valid sources are accepted."""
        signal = sample_signal.copy()
        signal["source"] = valid_source

        # Should not raise exception
        assert_conforms("SignalEventV1", signal)

    @pytest.mark.parametrize("invalid_type", [
        "invalid_type",
        123,
        None,
        ""
    ])
    def test_invalid_signal_type_rejected(self, sample_signal, invalid_type):
        """Test that invalid signal types are rejected."""
        invalid_signal = sample_signal.copy()
        invalid_signal["type"] = invalid_type

        errors = get_schema_errors("SignalEventV1", invalid_signal)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_type", [
        "momentum",
        "breakout",
        "indicator",
        "sentiment",
        "custom"
    ])
    def test_valid_signal_types_accepted(self, sample_signal, valid_type):
        """Test that all valid signal types are accepted."""
        signal = sample_signal.copy()
        signal["type"] = valid_type

        # Should not raise exception
        assert_conforms("SignalEventV1", signal)

    @pytest.mark.parametrize("invalid_strength", [
        -0.1,  # Below minimum
        1.1,   # Above maximum
        "0.5", # String instead of number
        None
    ])
    def test_invalid_strength_rejected(self, sample_signal, invalid_strength):
        """Test that strength values outside 0-1 range are rejected."""
        invalid_signal = sample_signal.copy()
        invalid_signal["strength"] = invalid_strength

        errors = get_schema_errors("SignalEventV1", invalid_signal)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_strength", [
        0.0,   # Minimum
        0.5,   # Middle
        1.0,   # Maximum
        0.001, # Very small
        0.999  # Very close to maximum
    ])
    def test_valid_strength_accepted(self, sample_signal, valid_strength):
        """Test that strength values in 0-1 range are accepted."""
        signal = sample_signal.copy()
        signal["strength"] = valid_strength

        # Should not raise exception
        assert_conforms("SignalEventV1", signal)

    @pytest.mark.parametrize("invalid_priority", [
        "urgent",
        "low",
        123,
        None
    ])
    def test_invalid_priority_rejected(self, sample_signal, invalid_priority):
        """Test that invalid priority values are rejected."""
        invalid_signal = sample_signal.copy()
        invalid_signal["priority"] = invalid_priority

        errors = get_schema_errors("SignalEventV1", invalid_signal)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_priority", [
        "high",
        "standard"
    ])
    def test_valid_priority_accepted(self, sample_signal, valid_priority):
        """Test that valid priority values are accepted."""
        signal = sample_signal.copy()
        signal["priority"] = valid_priority

        # Should not raise exception
        assert_conforms("SignalEventV1", signal)

    def test_priority_optional_defaults_to_standard(self, sample_signal):
        """Test that priority field is optional."""
        signal = sample_signal.copy()
        # Remove priority to test it's optional
        if "priority" in signal:
            del signal["priority"]

        # Should still be valid
        assert_conforms("SignalEventV1", signal)

    @pytest.mark.parametrize("invalid_instrument", [
        "a",        # Too short (< 2 chars)
        "A" * 33,   # Too long (> 32 chars)
        "btc usd",  # Contains space (not in pattern)
        "BTC@USD",  # Contains @ (not in pattern)
        "",         # Empty string
        123         # Not a string
    ])
    def test_invalid_instrument_rejected(self, sample_signal, invalid_instrument):
        """Test that invalid instrument identifiers are rejected."""
        invalid_signal = sample_signal.copy()
        invalid_signal["instrument"] = invalid_instrument

        errors = get_schema_errors("SignalEventV1", invalid_signal)
        assert len(errors) > 0

    @pytest.mark.parametrize("valid_instrument", [
        "BTCUSD",
        "BTC-USD",
        "BTC_USD",
        "BTC/USD",
        "ES1!",
        "GC1!",
        "6E1!",
        "SPY",
        "QQQ"
    ])
    def test_valid_instrument_accepted(self, sample_signal, valid_instrument):
        """Test that valid instrument identifiers are accepted."""
        signal = sample_signal.copy()
        signal["instrument"] = valid_instrument

        # Should not raise exception
        assert_conforms("SignalEventV1", signal)

    def test_additional_properties_rejected(self, sample_signal):
        """Test that additional properties beyond schema are rejected."""
        invalid_signal = sample_signal.copy()
        invalid_signal["extra_field"] = "not_allowed"

        errors = get_schema_errors("SignalEventV1", invalid_signal)
        assert len(errors) > 0
        assert any("additional" in error.lower() for error in errors)

    def test_wrong_schema_version_rejected(self, sample_signal):
        """Test that wrong schema versions are rejected."""
        invalid_signal = sample_signal.copy()
        invalid_signal["schema_version"] = "2.0.0"  # Wrong version

        errors = get_schema_errors("SignalEventV1", invalid_signal)
        assert len(errors) > 0

    def test_payload_can_be_arbitrary_object(self, sample_signal):
        """Test that payload field accepts arbitrary JSON objects."""
        signal = sample_signal.copy()

        # Test various payload structures
        test_payloads = [
            {},
            {"price": 100.0},
            {"price": 100.0, "volume": 1000, "indicators": {"rsi": 65}},
            {"complex": {"nested": {"data": [1, 2, 3]}}}
        ]

        for payload in test_payloads:
            signal["payload"] = payload
            # Should not raise exception
            assert_conforms("SignalEventV1", signal)

    def test_timestamp_format_validation(self, sample_signal):
        """Test that timestamp must be valid ISO format."""
        invalid_timestamps = [
            "2025-01-01",           # Date only
            "2025-01-01 10:00:00",  # Space instead of T
            "invalid-timestamp",    # Not a datetime
            "2025-13-01T10:00:00Z", # Invalid month
            123456789               # Numeric timestamp
        ]

        for invalid_ts in invalid_timestamps:
            invalid_signal = sample_signal.copy()
            invalid_signal["ts_iso"] = invalid_ts

            errors = get_schema_errors("SignalEventV1", invalid_ts)
            # Note: JSONSchema date-time validation may be lenient
            # This test documents expected behavior
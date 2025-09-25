#!/usr/bin/env python3
"""
Test suite for enhanced gateway processing with v1.0 schema validation.
"""

import json
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
import sys
import os

# Add the at_gateway module to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../at-core'))

from at_gateway.app import app, process_webhook_enhanced, create_signal_event_v1, categorize_signal_type, determine_signal_priority
from at_core.validators import validate_signal_event
from tests.fixtures.fake_nats import FakeNats


class TestEnhancedProcessing:
    """Test enhanced webhook processing with v1.0 features"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def sample_signal(self):
        """Sample market signal for testing"""
        return {
            "instrument": "BTCUSD",
            "price": 45000.0,
            "signal": "RSI_oversold",
            "strength": 0.85,
            "timestamp": "2025-09-24T10:30:00Z",
            "metadata": {
                "indicator": "RSI",
                "value": 25.3
            }
        }

    @pytest.fixture
    def mock_nats(self):
        """Mock NATS client for testing"""
        fake_nats = FakeNats()
        return fake_nats

    def test_signal_categorization(self):
        """Test signal type categorization logic"""
        # Test momentum signals
        assert categorize_signal_type("RSI_oversold") == "momentum"
        assert categorize_signal_type("MACD_bullish") == "momentum"
        assert categorize_signal_type("stochastic_signal") == "momentum"

        # Test breakout signals
        assert categorize_signal_type("resistance_break") == "breakout"
        assert categorize_signal_type("support_bounce") == "breakout"
        assert categorize_signal_type("breakout_long") == "breakout"

        # Test indicator signals
        assert categorize_signal_type("EMA_cross") == "indicator"
        assert categorize_signal_type("SMA_golden_cross") == "indicator"
        assert categorize_signal_type("bollinger_squeeze") == "indicator"

        # Test sentiment signals
        assert categorize_signal_type("sentiment_bullish") == "sentiment"
        assert categorize_signal_type("fear_greed_index") == "sentiment"

        # Test custom/unknown signals
        assert categorize_signal_type("custom_strategy") == "custom"
        assert categorize_signal_type("unknown_signal") == "custom"

    def test_priority_determination(self):
        """Test signal priority determination"""
        # High strength signals
        assert determine_signal_priority(0.9, "momentum") == "high"
        assert determine_signal_priority(0.8, "breakout") == "high"

        # Context-based priority
        assert determine_signal_priority(0.7, "breakout") == "high"
        assert determine_signal_priority(0.6, "momentum") == "high"

        # Standard priority
        assert determine_signal_priority(0.5, "indicator") == "std"
        assert determine_signal_priority(0.3, "sentiment") == "std"

    def test_signal_event_v1_creation(self, sample_signal):
        """Test SignalEventV1 creation from legacy signal"""
        corr_id = "test-corr-123"
        source = "tradingview"

        signal_event = create_signal_event_v1(
            type('MockSignal', (), sample_signal)(),
            source,
            corr_id
        )

        # Verify schema compliance
        assert signal_event["schema_version"] == "1.0.0"
        assert signal_event["correlation_id"] == corr_id
        assert signal_event["source"] == source
        assert signal_event["instrument"] == "BTCUSD"
        assert signal_event["type"] == "momentum"  # RSI signal
        assert signal_event["strength"] == 0.85

        # Validate against schema
        validate_signal_event(signal_event)  # Should not raise

    @pytest.mark.asyncio
    async def test_enhanced_processing_flow(self, sample_signal, mock_nats):
        """Test complete enhanced processing flow"""
        with patch('at_gateway.app.js_client', mock_nats), \
             patch('at_gateway.app.FF_TV_SLICE', True):

            # Mock request and signal objects
            request = Mock()
            request.state.corr_id = "test-corr-456"

            signal_obj = type('MockSignal', (), sample_signal)()

            # Process webhook
            response = await process_webhook_enhanced(
                request, signal_obj, "tradingview", "test-corr-456", None
            )

            # Verify response structure
            assert response["status"] == "accepted"
            assert response["processing_mode"] == "enhanced"
            assert response["schema_version"] == "1.0.0"
            assert "signal_classification" in response

            classification = response["signal_classification"]
            assert classification["type"] == "momentum"
            assert classification["priority"] == "high"  # 0.85 strength
            assert "signals.normalized.high.BTCUSD.momentum" in classification["subject"]

            # Verify NATS messages were published
            assert len(mock_nats.published_messages) == 2

            # Check raw signal
            raw_msg = mock_nats.published_messages[0]
            assert raw_msg["subject"] == "signals.raw"
            raw_payload = json.loads(raw_msg["data"])
            assert raw_payload["schema_version"] == "1.0.0"

            # Check enhanced normalized signal
            norm_msg = mock_nats.published_messages[1]
            assert norm_msg["subject"] == "signals.normalized.high.BTCUSD.momentum"
            norm_payload = json.loads(norm_msg["data"])
            assert norm_payload["schema_version"] == "1.0.0"
            validate_signal_event(norm_payload)  # Schema validation

    @pytest.mark.asyncio
    async def test_schema_validation_failure(self, mock_nats):
        """Test handling of schema validation failures"""
        with patch('at_gateway.app.js_client', mock_nats), \
             patch('at_gateway.app.FF_TV_SLICE', True):

            # Create invalid signal (missing required fields)
            invalid_signal = type('MockSignal', (), {
                "price": 45000.0,
                "signal": "test_signal",
                "strength": 0.5
                # Missing instrument
            })()

            request = Mock()
            request.state.corr_id = "test-corr-invalid"

            # Should raise HTTPException for schema validation
            with pytest.raises(Exception):  # HTTPException
                await process_webhook_enhanced(
                    request, invalid_signal, "test", "test-corr-invalid", None
                )

    def test_feature_flag_integration(self, client, sample_signal):
        """Test feature flag integration in webhook processing"""
        with patch('at_gateway.app.FF_TV_SLICE', True), \
             patch('at_gateway.app.js_client') as mock_js, \
             patch('at_gateway.app.nats_client') as mock_nats:

            mock_nats.is_connected = True
            mock_js.publish = AsyncMock()

            response = client.post("/webhook/test", json=sample_signal, headers={
                "X-Correlation-ID": "test-feature-flag"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["processing_mode"] == "enhanced"

    def test_legacy_fallback(self, client, sample_signal):
        """Test fallback to legacy processing when feature flag disabled"""
        with patch('at_gateway.app.FF_TV_SLICE', False), \
             patch('at_gateway.app.js_client') as mock_js, \
             patch('at_gateway.app.nats_client') as mock_nats:

            mock_nats.is_connected = True
            mock_js.publish = AsyncMock()

            response = client.post("/webhook/test", json=sample_signal, headers={
                "X-Correlation-ID": "test-legacy"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["processing_mode"] == "legacy"

    def test_dlq_on_processing_failure(self, mock_nats):
        """Test DLQ message creation on processing failures"""
        with patch('at_gateway.app.js_client', mock_nats), \
             patch('at_gateway.app.FF_TV_SLICE', True), \
             patch('at_gateway.app.validate_signal_event', side_effect=Exception("Processing error")):

            signal = type('MockSignal', (), {
                "instrument": "ETHUSD",
                "price": 3000.0,
                "signal": "test_signal",
                "strength": 0.6
            })()

            request = Mock()
            request.state.corr_id = "test-dlq"

            # Processing should fail and send to DLQ
            with pytest.raises(Exception):
                asyncio.run(process_webhook_enhanced(
                    request, signal, "test", "test-dlq", None
                ))

            # Verify DLQ message was published
            dlq_messages = [msg for msg in mock_nats.published_messages if msg["subject"].startswith("dlq.")]
            assert len(dlq_messages) == 1
            assert dlq_messages[0]["subject"] == "dlq.signals.normalized.test"

    def test_detailed_health_check(self, client):
        """Test enhanced health check endpoint"""
        with patch('at_gateway.app.nats_client') as mock_nats:
            mock_nats.is_connected = True

            response = client.get("/healthz/detailed")
            assert response.status_code == 200

            data = response.json()
            assert data["version"] == "1.0.0"
            assert "feature_flags" in data
            assert "schema_registry" in data

            # Verify feature flags are reported
            flags = data["feature_flags"]
            assert "FF_TV_SLICE" in flags
            assert "FF_ENHANCED_LOGGING" in flags
            assert "FF_CIRCUIT_BREAKER" in flags

    def test_enhanced_metrics_collection(self):
        """Test that enhanced metrics are properly defined"""
        from at_gateway.app import schema_validation_errors, signal_categorization_total, feature_flag_evaluations, enhanced_processing_duration

        # Verify metrics are Counter/Histogram objects
        assert hasattr(schema_validation_errors, 'labels')
        assert hasattr(signal_categorization_total, 'labels')
        assert hasattr(feature_flag_evaluations, 'labels')
        assert hasattr(enhanced_processing_duration, 'observe')

    @pytest.mark.parametrize("signal_type,expected_type", [
        ("RSI_overbought", "momentum"),
        ("MACD_bearish", "momentum"),
        ("support_break", "breakout"),
        ("resistance_hold", "breakout"),
        ("EMA_20_cross", "indicator"),
        ("sentiment_neutral", "sentiment"),
        ("custom_algo", "custom"),
    ])
    def test_signal_categorization_comprehensive(self, signal_type, expected_type):
        """Test comprehensive signal categorization scenarios"""
        assert categorize_signal_type(signal_type) == expected_type

    @pytest.mark.parametrize("strength,signal_type,expected_priority", [
        (0.9, "momentum", "high"),
        (0.8, "breakout", "high"),
        (0.7, "breakout", "high"),
        (0.6, "momentum", "high"),
        (0.5, "indicator", "std"),
        (0.4, "sentiment", "std"),
        (0.3, "custom", "std"),
    ])
    def test_priority_determination_comprehensive(self, strength, signal_type, expected_priority):
        """Test comprehensive priority determination scenarios"""
        assert determine_signal_priority(strength, signal_type) == expected_priority


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
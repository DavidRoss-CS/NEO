"""
pytest configuration and shared fixtures for NEO tests.

Provides common test fixtures and configuration that can be used
across all test modules.
"""

import pytest
import datetime as dt
from typing import Dict, Any

# Import our test fixtures
from tests.fixtures import (
    FakeNats, FakeClock, ConfigFactory,
    create_test_nats, create_test_clock,
    quick_test_config, integration_test_config
)


# Schema test fixtures - sample payloads for contract testing

@pytest.fixture
def sample_signal() -> Dict[str, Any]:
    """Sample SignalEventV1 payload for testing."""
    return {
        "schema_version": "1.0.0",
        "intent_id": "intent-123456",
        "correlation_id": "corr-123456",
        "source": "tradingview",
        "instrument": "BTCUSD",
        "type": "momentum",
        "strength": 0.82,
        "priority": "standard",
        "payload": {"price": 120000.25, "note": "BTC momentum long"},
        "ts_iso": dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).isoformat()
    }


@pytest.fixture
def sample_agent_output() -> Dict[str, Any]:
    """Sample AgentOutputV1 payload for testing."""
    return {
        "schema_version": "1.0.0",
        "intent_id": "intent-123456",
        "agent": "mcp_gpt_trend",
        "confidence": 0.71,
        "summary": "Momentum long with tight risk management",
        "recommendation": {
            "action": "alert",
            "orders": [
                {
                    "instrument": "BTCUSD",
                    "side": "buy",
                    "qty": 0.1,
                    "type": "limit",
                    "limit_price": 119900.0,
                    "time_in_force": "day"
                }
            ]
        },
        "rationale": "Higher timeframe uptrend with breakout confirmation",
        "risk": {
            "max_drawdown_pct": 2.5,
            "stop_loss": 118500.0,
            "take_profit": 121800.0
        },
        "metadata": {"htf": "4H", "confidence_factors": ["momentum", "volume"]},
        "ts_iso": dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).isoformat()
    }


@pytest.fixture
def sample_order_intent() -> Dict[str, Any]:
    """Sample OrderIntentV1 payload for testing."""
    return {
        "schema_version": "1.0.0",
        "order_id": "ord-abc123",
        "intent_id": "intent-123456",
        "account": "paper-default",
        "instrument": "BTCUSD",
        "side": "buy",
        "qty": 0.1,
        "type": "limit",
        "limit_price": 119900.0,
        "stop_loss": 118500.0,
        "take_profit": 121800.0,
        "time_in_force": "day",
        "ts_iso": dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).isoformat()
    }


# Test infrastructure fixtures

@pytest.fixture
def fake_nats() -> FakeNats:
    """Provide a fake NATS client for isolated testing."""
    return FakeNats(persist_messages=True)


@pytest.fixture
def fake_nats_with_jetstream():
    """Provide fake NATS with JetStream for testing."""
    return create_test_nats(persist=True)


@pytest.fixture
def fake_clock() -> FakeClock:
    """Provide a controllable clock for testing."""
    return create_test_clock()


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return quick_test_config()


@pytest.fixture
def integration_config():
    """Provide integration test configuration."""
    return integration_test_config()


# Configuration fixtures for specific services

@pytest.fixture
def gateway_config():
    """Gateway service test configuration."""
    return ConfigFactory.minimal_gateway()


@pytest.fixture
def agent_config():
    """Agent service test configuration."""
    return ConfigFactory.test_agent()


@pytest.fixture
def orchestrator_config():
    """Orchestrator service test configuration."""
    return ConfigFactory.test_orchestrator()


# Sample data fixtures for different test scenarios

@pytest.fixture
def btc_momentum_signal(sample_signal) -> Dict[str, Any]:
    """BTC momentum signal for testing."""
    signal = sample_signal.copy()
    signal.update({
        "instrument": "BTCUSD",
        "type": "momentum",
        "strength": 0.85,
        "payload": {
            "price": 120000.25,
            "volume": 1250000,
            "rsi": 65.2,
            "ma_cross": "bullish"
        }
    })
    return signal


@pytest.fixture
def eth_breakout_signal(sample_signal) -> Dict[str, Any]:
    """ETH breakout signal for testing."""
    signal = sample_signal.copy()
    signal.update({
        "intent_id": "intent-eth-001",
        "correlation_id": "corr-eth-001",
        "instrument": "ETHUSD",
        "type": "breakout",
        "strength": 0.75,
        "priority": "high",
        "payload": {
            "price": 4250.50,
            "resistance_level": 4200.0,
            "volume_surge": True
        }
    })
    return signal


@pytest.fixture
def invalid_signal_missing_instrument(sample_signal) -> Dict[str, Any]:
    """Invalid signal missing required field for error testing."""
    signal = sample_signal.copy()
    del signal["instrument"]
    return signal


@pytest.fixture
def invalid_agent_output_bad_confidence(sample_agent_output) -> Dict[str, Any]:
    """Invalid agent output with confidence > 1.0 for error testing."""
    output = sample_agent_output.copy()
    output["confidence"] = 1.5  # Invalid: > 1.0
    return output


# Time-based fixtures

@pytest.fixture
def market_hours_clock() -> FakeClock:
    """Clock set to market hours for trading tests."""
    # January 3, 2025 is a Friday, 10:30 AM EST = 15:30 UTC
    market_time = dt.datetime(2025, 1, 3, 15, 30, tzinfo=dt.timezone.utc)
    return FakeClock(market_time)


@pytest.fixture
def weekend_clock() -> FakeClock:
    """Clock set to weekend for market-closed tests."""
    # January 4, 2025 is a Saturday
    weekend_time = dt.datetime(2025, 1, 4, 12, 0, tzinfo=dt.timezone.utc)
    return FakeClock(weekend_time)


# Test case categories for parametrized testing

@pytest.fixture(params=["momentum", "breakout", "indicator", "sentiment"])
def signal_type(request):
    """Parametrized fixture for testing different signal types."""
    return request.param


@pytest.fixture(params=["buy", "sell"])
def order_side(request):
    """Parametrized fixture for testing different order sides."""
    return request.param


@pytest.fixture(params=["market", "limit"])
def order_type(request):
    """Parametrized fixture for testing different order types."""
    return request.param


# Feature flag fixtures

@pytest.fixture
def feature_flags_all_enabled():
    """Feature flags with all features enabled."""
    return ConfigFactory.feature_flags(
        FF_TV_SLICE=True,
        FF_AGENT_GPT=True,
        FF_OUTPUT_SLACK=True,
        FF_EXEC_PAPER=True
    )


@pytest.fixture
def feature_flags_minimal():
    """Feature flags with only essential features enabled."""
    return ConfigFactory.feature_flags(
        FF_TV_SLICE=True,
        FF_AGENT_GPT=False,
        FF_OUTPUT_SLACK=False,
        FF_EXEC_PAPER=True
    )


# Cleanup fixtures

@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Automatically cleanup temporary files after each test."""
    import tempfile
    import shutil
    import os

    temp_dirs = []

    yield  # Run the test

    # Cleanup any temp directories created during the test
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


# pytest configuration

def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers",
        "contract: mark test as a contract validation test"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test requiring external services"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test paths."""
    for item in items:
        # Add contract marker to contract tests
        if "contracts" in str(item.fspath):
            item.add_marker(pytest.mark.contract)

        # Add integration marker to integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
"""
Test fixtures for NEO trading system.

Provides fake implementations of external dependencies for isolated testing:
- FakeNats: In-memory NATS client with pattern matching
- FakeClock: Controllable time for deterministic tests
- ConfigFactory: Pre-configured test settings for all services
"""

from .fake_nats import FakeNats, FakeJetStream, create_test_nats, publish_test_signal
from .fake_clock import FakeClock, create_test_clock, market_open_clock, weekend_clock, ClockContext
from .config_factory import (
    ConfigFactory,
    GatewayConfig,
    AgentConfig,
    OrchestratorConfig,
    OutputManagerConfig,
    ExecConfig,
    TestEnvironmentConfig,
    quick_test_config,
    integration_test_config,
    docker_compose_config
)

__all__ = [
    # NATS fixtures
    "FakeNats",
    "FakeJetStream",
    "create_test_nats",
    "publish_test_signal",

    # Clock fixtures
    "FakeClock",
    "create_test_clock",
    "market_open_clock",
    "weekend_clock",
    "ClockContext",

    # Configuration
    "ConfigFactory",
    "GatewayConfig",
    "AgentConfig",
    "OrchestratorConfig",
    "OutputManagerConfig",
    "ExecConfig",
    "TestEnvironmentConfig",
    "quick_test_config",
    "integration_test_config",
    "docker_compose_config",
]
"""
Configuration factory for testing NEO services.

Provides pre-configured test configurations for all NEO services
with sensible defaults and easy customization.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import os
import tempfile


@dataclass
class GatewayConfig:
    """Configuration for at-gateway service."""
    nats_url: str = "nats://localhost:4222"
    hmac_secret: str = "testsecret"
    port: int = 8001
    log_level: str = "INFO"
    dedupe_ttl_s: int = 60
    rate_limit_rps: int = 100
    replay_window_sec: int = 300
    allowed_sources: List[str] = field(default_factory=lambda: ["tradingview", "webhook", "test", "manual"])
    max_payload_size: int = 1024 * 1024  # 1MB
    maintenance_mode: bool = False

    # Subject configuration
    raw_signal_subject: str = "signals.raw"
    normalized_subject_template: str = "signals.normalized.{priority}.{instrument}.{type}"


@dataclass
class AgentConfig:
    """Configuration for agent services."""
    nats_url: str = "nats://localhost:4222"
    port: int = 8002
    log_level: str = "INFO"
    agent_id: str = "test-agent"
    strategy_type: str = "momentum"
    risk_limit: float = 0.02
    confidence_threshold: float = 0.7
    max_positions: int = 5

    # Subject configuration
    signal_subject_pattern: str = "signals.normalized.*"
    decision_subject: str = "decisions.order_intent"


@dataclass
class OrchestratorConfig:
    """Configuration for agent orchestrator service."""
    nats_url: str = "nats://localhost:4222"
    port: int = 8010
    log_level: str = "INFO"

    # Database
    db_url: str = "postgresql://test:test@localhost:5432/neo_test"

    # MCP Integration
    mcp_timeout_s: int = 30
    max_agent_tokens: int = 4000
    agent_rate_limit_per_min: int = 10

    # Trigger evaluation
    trigger_config_file: str = "triggers.yaml"
    debounce_window_s: int = 5


@dataclass
class OutputManagerConfig:
    """Configuration for output manager service."""
    nats_url: str = "nats://localhost:4222"
    port: int = 8008
    log_level: str = "INFO"

    # Database
    db_url: str = "postgresql://test:test@localhost:5432/neo_test"

    # Notification channels
    slack_webhook_url: str = "https://hooks.slack.com/test"
    telegram_bot_token: str = "test-token"
    telegram_chat_id: str = "test-chat"

    # Subject patterns
    agent_output_pattern: str = "decisions.agent_output.*"
    notification_subject: str = "outputs.notification.{channel}"
    execution_subject: str = "outputs.execution.{venue}"


@dataclass
class ExecConfig:
    """Configuration for execution services."""
    nats_url: str = "nats://localhost:4222"
    port: int = 8004
    log_level: str = "INFO"

    # Paper trading
    initial_balance: float = 100000.0
    commission_per_trade: float = 1.0
    slippage_bps: int = 2  # basis points

    # Risk limits
    max_position_size: float = 10000.0
    max_daily_loss: float = 1000.0

    # Subject patterns
    order_intent_pattern: str = "outputs.execution.*"
    fill_subject: str = "executions.fill"


@dataclass
class NatsConfig:
    """Configuration for NATS server and streams."""
    url: str = "nats://localhost:4222"
    stream_name: str = "trading-events"
    subjects: List[str] = field(default_factory=lambda: ["signals.*", "decisions.*", "outputs.*", "executions.*"])
    retention_policy: str = "limits"
    max_msgs: int = 1000000
    max_age_days: int = 7
    storage_type: str = "file"
    replicas: int = 1


@dataclass
class TestEnvironmentConfig:
    """Complete test environment configuration."""
    # Service configs
    gateway: GatewayConfig = field(default_factory=GatewayConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    output_manager: OutputManagerConfig = field(default_factory=OutputManagerConfig)
    exec_sim: ExecConfig = field(default_factory=ExecConfig)
    nats: NatsConfig = field(default_factory=NatsConfig)

    # Test-specific settings
    temp_dir: Optional[str] = None
    cleanup_on_exit: bool = True
    fast_mode: bool = True  # Reduced timeouts for faster tests


class ConfigFactory:
    """Factory for creating test configurations."""

    @staticmethod
    def minimal_gateway(**overrides) -> GatewayConfig:
        """Create minimal gateway config for unit tests."""
        config = GatewayConfig(
            nats_url="memory://test",
            port=0,  # Random available port
            log_level="ERROR",  # Quiet for tests
            rate_limit_rps=1000,  # Higher for tests
            **overrides
        )
        return config

    @staticmethod
    def integration_gateway(**overrides) -> GatewayConfig:
        """Create gateway config for integration tests."""
        config = GatewayConfig(**overrides)
        return config

    @staticmethod
    def test_agent(strategy: str = "momentum", **overrides) -> AgentConfig:
        """Create agent config for tests."""
        config = AgentConfig(
            nats_url="memory://test",
            port=0,
            log_level="ERROR",
            strategy_type=strategy,
            agent_id=f"test-{strategy}-agent",
            **overrides
        )
        return config

    @staticmethod
    def test_orchestrator(**overrides) -> OrchestratorConfig:
        """Create orchestrator config for tests."""
        # Use in-memory SQLite for tests
        temp_db = tempfile.mktemp(suffix=".db")
        config = OrchestratorConfig(
            nats_url="memory://test",
            port=0,
            log_level="ERROR",
            db_url=f"sqlite:///{temp_db}",
            mcp_timeout_s=5,  # Faster for tests
            **overrides
        )
        return config

    @staticmethod
    def test_output_manager(**overrides) -> OutputManagerConfig:
        """Create output manager config for tests."""
        temp_db = tempfile.mktemp(suffix=".db")
        config = OutputManagerConfig(
            nats_url="memory://test",
            port=0,
            log_level="ERROR",
            db_url=f"sqlite:///{temp_db}",
            slack_webhook_url="https://httpbin.org/post",  # Test endpoint
            **overrides
        )
        return config

    @staticmethod
    def test_environment(**overrides) -> TestEnvironmentConfig:
        """Create complete test environment config."""
        temp_dir = tempfile.mkdtemp(prefix="neo_test_")

        config = TestEnvironmentConfig(
            temp_dir=temp_dir,
            **overrides
        )

        # Use memory NATS for all services in test environment
        config.gateway.nats_url = "memory://test"
        config.agent.nats_url = "memory://test"
        config.orchestrator.nats_url = "memory://test"
        config.output_manager.nats_url = "memory://test"
        config.exec_sim.nats_url = "memory://test"
        config.nats.url = "memory://test"

        return config

    @staticmethod
    def feature_flags(**overrides) -> Dict[str, bool]:
        """Create feature flag configuration."""
        flags = {
            "FF_TV_SLICE": True,
            "FF_AGENT_GPT": False,  # Disabled by default for tests
            "FF_OUTPUT_SLACK": False,
            "FF_EXEC_PAPER": True,
            "FF_ENHANCED_LOGGING": True,
            **overrides
        }
        return flags

    @staticmethod
    def from_env(config_class=GatewayConfig, prefix: str = "NEO_") -> Any:
        """Load configuration from environment variables."""
        # This would read from environment and create config
        # For now, return default config
        return config_class()


# Convenience functions for common test scenarios

def quick_test_config() -> TestEnvironmentConfig:
    """Create a fast test configuration for unit tests."""
    return ConfigFactory.test_environment(
        fast_mode=True,
        cleanup_on_exit=True
    )


def integration_test_config() -> TestEnvironmentConfig:
    """Create configuration for integration tests with real services."""
    config = ConfigFactory.test_environment()
    # Use real NATS for integration tests
    config.nats.url = "nats://localhost:4222"
    for service_config in [config.gateway, config.agent, config.orchestrator,
                          config.output_manager, config.exec_sim]:
        service_config.nats_url = "nats://localhost:4222"

    return config


def docker_compose_config() -> TestEnvironmentConfig:
    """Create configuration matching docker-compose setup."""
    config = integration_test_config()
    # Use docker-compose service names
    config.nats.url = "nats://nats:4222"
    for service_config in [config.gateway, config.agent, config.orchestrator,
                          config.output_manager, config.exec_sim]:
        service_config.nats_url = "nats://nats:4222"

    return config
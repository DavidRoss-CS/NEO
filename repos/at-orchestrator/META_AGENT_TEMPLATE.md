# Meta-Agent Template

**Reference template for building meta-agents that coordinate specialized agents and manage workflow state.**

## Template Overview

This template provides a structured approach for implementing meta-agents within the orchestrator layer. Meta-agents coordinate multiple specialized agents, manage shared state, and implement complex decision workflows that span multiple agent capabilities.

## Meta-Agent Architecture

### Core Components

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
import json
import time
from datetime import datetime

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_AGENTS = "waiting_for_agents"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

@dataclass
class AgentSignal:
    """Standardized agent signal format."""
    corr_id: str
    agent_name: str
    signal_type: str
    data: Dict[str, Any]
    confidence: float
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class WorkflowContext:
    """Workflow execution context."""
    corr_id: str
    workflow_id: str
    status: WorkflowStatus
    required_agents: List[str]
    received_signals: Dict[str, AgentSignal]
    started_at: str
    timeout_seconds: int
    metadata: Dict[str, Any]

class MetaAgent(ABC):
    """Abstract base class for meta-agents."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", self.__class__.__name__)
        self.nats = None
        self.redis = None
        self.active_workflows: Dict[str, WorkflowContext] = {}

    @abstractmethod
    async def define_workflow(self, trigger_signal: AgentSignal) -> WorkflowContext:
        """Define workflow requirements and agents needed."""
        pass

    @abstractmethod
    async def evaluate_signals(self, context: WorkflowContext) -> Dict[str, Any]:
        """Evaluate collected agent signals and make decision."""
        pass

    @abstractmethod
    async def can_make_decision(self, context: WorkflowContext) -> bool:
        """Check if sufficient signals are available for decision."""
        pass

    async def start(self):
        """Initialize and start the meta-agent."""
        await self.init_connections()
        await self.setup_subscriptions()
        await self.start_workflow_monitor()

    async def init_connections(self):
        """Initialize NATS and Redis connections."""
        from nats.aio.client import Client as NATS
        import aioredis

        # NATS connection
        self.nats = NATS()
        await self.nats.connect(self.config.get("nats_url", "nats://localhost:4222"))
        self.jetstream = self.nats.jetstream()

        # Redis connection for state management
        self.redis = aioredis.from_url(self.config.get("redis_url", "redis://localhost:6379"))

    async def setup_subscriptions(self):
        """Setup NATS subscriptions for agent signals."""
        await self.jetstream.subscribe(
            subject="signals.enriched.*",
            cb=self.handle_agent_signal,
            durable=f"{self.name}-enriched-consumer"
        )

        await self.jetstream.subscribe(
            subject="signals.normalized",
            cb=self.handle_trigger_signal,
            durable=f"{self.name}-trigger-consumer"
        )

    async def handle_trigger_signal(self, msg):
        """Handle new trigger signals that may start workflows."""
        try:
            signal_data = json.loads(msg.data.decode())
            trigger_signal = AgentSignal(
                corr_id=signal_data["corr_id"],
                agent_name="normalizer",
                signal_type="normalized",
                data=signal_data,
                confidence=1.0,
                timestamp=signal_data.get("normalized_at"),
                metadata={}
            )

            # Check if we should start a new workflow
            if await self.should_start_workflow(trigger_signal):
                workflow = await self.define_workflow(trigger_signal)
                await self.start_workflow(workflow)

            await msg.ack()

        except Exception as e:
            self.logger.error(f"Error handling trigger signal: {e}")
            await msg.nak()

    async def handle_agent_signal(self, msg):
        """Handle enriched signals from specialized agents."""
        try:
            signal_data = json.loads(msg.data.decode())
            agent_signal = AgentSignal(
                corr_id=signal_data["corr_id"],
                agent_name=signal_data["agent_name"],
                signal_type=signal_data.get("signal_type", "analysis"),
                data=signal_data,
                confidence=signal_data.get("confidence", 0.0),
                timestamp=signal_data.get("timestamp"),
                metadata=signal_data.get("metadata", {})
            )

            # Route to appropriate workflow
            await self.route_signal_to_workflow(agent_signal)

            await msg.ack()

        except Exception as e:
            self.logger.error(f"Error handling agent signal: {e}")
            await msg.nak()

    async def should_start_workflow(self, signal: AgentSignal) -> bool:
        """Determine if trigger signal should start new workflow."""
        # Override in subclasses with specific logic
        return True

    async def start_workflow(self, context: WorkflowContext):
        """Start a new workflow."""
        self.active_workflows[context.corr_id] = context
        context.status = WorkflowStatus.IN_PROGRESS

        # Store workflow state in Redis
        await self.store_workflow_state(context)

        self.logger.info(
            f"Started workflow {context.workflow_id} for {context.corr_id}, "
            f"waiting for agents: {context.required_agents}"
        )

    async def route_signal_to_workflow(self, signal: AgentSignal):
        """Route agent signal to appropriate workflow."""
        context = self.active_workflows.get(signal.corr_id)

        if not context:
            self.logger.debug(f"No active workflow for {signal.corr_id}")
            return

        # Add signal to workflow context
        context.received_signals[signal.agent_name] = signal
        context.status = WorkflowStatus.WAITING_FOR_AGENTS

        # Check if we can make a decision
        if await self.can_make_decision(context):
            await self.execute_decision_workflow(context)

    async def execute_decision_workflow(self, context: WorkflowContext):
        """Execute decision workflow with collected signals."""
        try:
            context.status = WorkflowStatus.EVALUATING
            await self.store_workflow_state(context)

            # Evaluate signals and make decision
            decision = await self.evaluate_signals(context)

            # Publish orchestrated decision
            await self.publish_decision(context, decision)

            # Mark workflow as completed
            context.status = WorkflowStatus.COMPLETED
            await self.store_workflow_state(context)

            # Cleanup
            del self.active_workflows[context.corr_id]

            self.logger.info(f"Completed workflow {context.workflow_id} for {context.corr_id}")

        except Exception as e:
            context.status = WorkflowStatus.FAILED
            await self.store_workflow_state(context)
            self.logger.error(f"Workflow {context.workflow_id} failed: {e}")

    async def publish_decision(self, context: WorkflowContext, decision: Dict[str, Any]):
        """Publish orchestrated decision."""
        orchestrated_signal = {
            "corr_id": context.corr_id,
            "workflow_id": context.workflow_id,
            "orchestrator": self.name,
            "decision": decision,
            "source_signals": [
                {
                    "agent": signal.agent_name,
                    "confidence": signal.confidence,
                    "timestamp": signal.timestamp
                }
                for signal in context.received_signals.values()
            ],
            "orchestrated_at": datetime.utcnow().isoformat(),
            "metadata": context.metadata
        }

        await self.nats.publish(
            "orchestrated.decision",
            json.dumps(orchestrated_signal).encode()
        )

    async def store_workflow_state(self, context: WorkflowContext):
        """Store workflow state in Redis."""
        state_key = f"workflow:{context.corr_id}:{context.workflow_id}"
        state_data = {
            "corr_id": context.corr_id,
            "workflow_id": context.workflow_id,
            "status": context.status,
            "required_agents": context.required_agents,
            "received_agents": list(context.received_signals.keys()),
            "started_at": context.started_at,
            "timeout_seconds": context.timeout_seconds,
            "metadata": context.metadata
        }

        await self.redis.setex(
            state_key,
            context.timeout_seconds,
            json.dumps(state_data)
        )

    async def start_workflow_monitor(self):
        """Start background task to monitor workflow timeouts."""
        asyncio.create_task(self._workflow_timeout_monitor())

    async def _workflow_timeout_monitor(self):
        """Monitor and handle workflow timeouts."""
        while True:
            try:
                current_time = time.time()

                for corr_id, context in list(self.active_workflows.items()):
                    started_time = datetime.fromisoformat(context.started_at).timestamp()

                    if current_time - started_time > context.timeout_seconds:
                        context.status = WorkflowStatus.TIMEOUT
                        await self.handle_workflow_timeout(context)
                        del self.active_workflows[corr_id]

                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                self.logger.error(f"Error in workflow timeout monitor: {e}")
                await asyncio.sleep(10)

    async def handle_workflow_timeout(self, context: WorkflowContext):
        """Handle workflow timeout."""
        await self.store_workflow_state(context)

        self.logger.warning(
            f"Workflow {context.workflow_id} for {context.corr_id} timed out. "
            f"Received signals from: {list(context.received_signals.keys())}, "
            f"Missing: {set(context.required_agents) - set(context.received_signals.keys())}"
        )

        # Optionally publish partial decision or timeout notification
        timeout_decision = {
            "action": "timeout",
            "reason": "workflow_timeout",
            "partial_signals": list(context.received_signals.keys()),
            "missing_signals": list(set(context.required_agents) - set(context.received_signals.keys()))
        }

        await self.publish_decision(context, timeout_decision)
```

## Example Implementation: Trading Decision Meta-Agent

```python
class TradingDecisionMetaAgent(MetaAgent):
    """Meta-agent for coordinating trading decisions across multiple agents."""

    async def define_workflow(self, trigger_signal: AgentSignal) -> WorkflowContext:
        """Define workflow for trading decision coordination."""
        instrument = trigger_signal.data.get("instrument", "UNKNOWN")

        # Different workflows based on instrument type
        if instrument.startswith("CRYPTO"):
            required_agents = ["momentum", "risk", "sentiment", "correlation"]
            timeout_seconds = 300  # 5 minutes for crypto
        elif instrument in ["SPY", "QQQ", "IWM"]:
            required_agents = ["momentum", "risk", "correlation", "macro"]
            timeout_seconds = 180  # 3 minutes for ETFs
        else:
            required_agents = ["momentum", "risk"]
            timeout_seconds = 120  # 2 minutes for FX

        return WorkflowContext(
            corr_id=trigger_signal.corr_id,
            workflow_id=f"trading_decision_{int(time.time())}",
            status=WorkflowStatus.PENDING,
            required_agents=required_agents,
            received_signals={},
            started_at=datetime.utcnow().isoformat(),
            timeout_seconds=timeout_seconds,
            metadata={
                "instrument": instrument,
                "trigger_price": trigger_signal.data.get("price"),
                "trigger_side": trigger_signal.data.get("side")
            }
        )

    async def can_make_decision(self, context: WorkflowContext) -> bool:
        """Check if we have sufficient signals for trading decision."""
        received_agents = set(context.received_signals.keys())\n        required_agents = set(context.required_agents)\n        \n        # Must have momentum and risk at minimum\n        if not ({"momentum", "risk"} <= received_agents):\n            return False\n        \n        # For crypto, also need sentiment\n        instrument = context.metadata.get("instrument", "")\n        if instrument.startswith("CRYPTO") and "sentiment" not in received_agents:\n            return False\n        \n        # Have enough core signals\n        return len(received_agents) >= 2\n    \n    async def evaluate_signals(self, context: WorkflowContext) -> Dict[str, Any]:\n        \"\"\"Evaluate collected signals and make trading decision.\"\"\"\n        signals = context.received_signals\n        instrument = context.metadata.get("instrument")\n        \n        # Extract key metrics from each agent\n        momentum_signal = signals.get("momentum")\n        risk_signal = signals.get("risk")\n        sentiment_signal = signals.get("sentiment")\n        correlation_signal = signals.get("correlation")\n        \n        # Initialize decision structure\n        decision = {\n            "action": "no_trade",\n            "reason": "insufficient_confidence",\n            "confidence": 0.0,\n            "metadata": {\n                "instrument": instrument,\n                "analysis_timestamp": datetime.utcnow().isoformat(),\n                "agents_consulted": list(signals.keys())\n            }\n        }\n        \n        # Risk check first - blocking\n        if risk_signal and risk_signal.data.get("risk_level") == "blocked":\n            decision.update({\n                "action": "no_trade",\n                "reason": "risk_blocked",\n                "confidence": 1.0\n            })\n            return decision\n        \n        # Momentum analysis\n        if momentum_signal:\n            momentum_data = momentum_signal.data.get("analysis", {})\n            momentum_confidence = momentum_signal.confidence\n            trend_direction = momentum_data.get("trend_direction")\n            momentum_strength = momentum_data.get("momentum_strength", 0)\n            \n            # High conviction momentum signal\n            if momentum_confidence > 0.8 and momentum_strength > 0.7:\n                # Risk-adjusted position sizing\n                position_size = self.calculate_position_size(\n                    risk_signal, momentum_strength, momentum_confidence\n                )\n                \n                if position_size > 0:\n                    decision.update({\n                        "action": "trade",\n                        "direction": trend_direction,\n                        "position_size": position_size,\n                        "confidence": min(momentum_confidence, risk_signal.confidence if risk_signal else 1.0),\n                        "reason": "high_conviction_momentum"\n                    })\n        \n        # Sentiment boost for crypto\n        if sentiment_signal and instrument.startswith("CRYPTO"):\n            sentiment_score = sentiment_signal.data.get("sentiment_score", 0)\n            if abs(sentiment_score) > 0.6:  # Strong sentiment\n                if decision["action"] == "trade":\n                    # Boost confidence for aligned sentiment\n                    if (sentiment_score > 0 and decision["direction"] == "bullish") or \\\n                       (sentiment_score < 0 and decision["direction"] == "bearish"):\n                        decision["confidence"] = min(decision["confidence"] * 1.2, 1.0)\n                        decision["metadata"]["sentiment_boost"] = True\n        \n        # Correlation risk adjustment\n        if correlation_signal:\n            correlation_risk = correlation_signal.data.get("correlation_risk", 0)\n            if correlation_risk > 0.8:  # High correlation risk\n                if decision["action"] == "trade":\n                    decision["position_size"] *= 0.5  # Reduce size\n                    decision["metadata"]["correlation_adjustment"] = True\n        \n        return decision\n    \n    def calculate_position_size(self, risk_signal: Optional[AgentSignal], \n                              momentum_strength: float, confidence: float) -> float:\n        \"\"\"Calculate risk-adjusted position size.\"\"\"\n        if not risk_signal:\n            return 0.0\n        \n        risk_data = risk_signal.data.get("analysis", {})\n        max_position = risk_data.get("max_position_size", 0)\n        risk_level = risk_data.get("risk_level")\n        \n        # Base size from risk limits\n        base_size = max_position * 0.5  # Conservative base\n        \n        # Risk level adjustments\n        risk_multipliers = {\n            "low": 1.0,\n            "medium": 0.7,\n            "high": 0.3,\n            "blocked": 0.0\n        }\n        \n        risk_multiplier = risk_multipliers.get(risk_level, 0.5)\n        \n        # Confidence and momentum adjustments\n        signal_multiplier = (confidence * momentum_strength)\n        \n        return base_size * risk_multiplier * signal_multiplier\n    \n    async def should_start_workflow(self, signal: AgentSignal) -> bool:\n        \"\"\"Determine if normalized signal should trigger trading workflow.\"\"\"\n        data = signal.data\n        \n        # Only start workflows for actionable signals\n        if data.get("side") is None:\n            return False  # No trade intent\n        \n        # Strength threshold\n        strength = data.get("strength", 0)\n        if strength < 0.3:\n            return False  # Too weak\n        \n        # Don't start duplicate workflows\n        if signal.corr_id in self.active_workflows:\n            return False\n        \n        return True\n```\n\n## Configuration Management\n\n```python\nfrom pydantic import BaseSettings\nfrom typing import Dict, List, Optional\n\nclass MetaAgentConfig(BaseSettings):\n    \"\"\"Configuration for meta-agents.\"\"\"\n    \n    # Basic settings\n    name: str\n    nats_url: str = \"nats://localhost:4222\"\n    redis_url: str = \"redis://localhost:6379\"\n    log_level: str = \"INFO\"\n    \n    # Workflow settings\n    default_timeout_seconds: int = 300\n    max_concurrent_workflows: int = 100\n    workflow_cleanup_interval: int = 60\n    \n    # Agent coordination\n    required_agents: List[str] = []\n    optional_agents: List[str] = []\n    agent_timeout_seconds: int = 60\n    \n    # Decision thresholds\n    min_confidence_threshold: float = 0.5\n    min_agents_required: int = 2\n    \n    # Monitoring\n    health_check_interval: int = 30\n    metrics_port: int = 9090\n    \n    class Config:\n        env_prefix = \"META_AGENT_\"\n        env_file = \".env\"\n\n# Load configuration\nconfig = MetaAgentConfig(\n    name=\"trading_decision_meta_agent\",\n    required_agents=[\"momentum\", \"risk\"],\n    optional_agents=[\"sentiment\", \"correlation\", \"macro\"],\n    min_confidence_threshold=0.6\n)\n```\n\n## Deployment Example\n\n```python\n# main.py\nimport asyncio\nimport logging\nfrom trading_decision_meta_agent import TradingDecisionMetaAgent\nfrom config import MetaAgentConfig\n\nasync def main():\n    # Setup logging\n    logging.basicConfig(\n        level=logging.INFO,\n        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'\n    )\n    \n    # Load configuration\n    config = MetaAgentConfig()\n    \n    # Create and start meta-agent\n    meta_agent = TradingDecisionMetaAgent(config.dict())\n    \n    try:\n        await meta_agent.start()\n        \n        # Keep running\n        while True:\n            await asyncio.sleep(1)\n            \n    except KeyboardInterrupt:\n        logging.info(\"Shutting down meta-agent...\")\n    except Exception as e:\n        logging.error(f\"Meta-agent error: {e}\")\n\nif __name__ == \"__main__\":\n    asyncio.run(main())\n```\n\n## Docker Deployment\n\n```dockerfile\n# Dockerfile\nFROM python:3.11-slim\n\nWORKDIR /app\n\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\n\nCOPY . .\n\nEXPOSE 9090\n\nCMD [\"python\", \"main.py\"]\n```\n\n```yaml\n# docker-compose.yml\nversion: '3.8'\nservices:\n  trading-meta-agent:\n    build: .\n    environment:\n      - META_AGENT_NATS_URL=nats://nats:4222\n      - META_AGENT_REDIS_URL=redis://redis:6379\n      - META_AGENT_LOG_LEVEL=INFO\n      - META_AGENT_MIN_CONFIDENCE_THRESHOLD=0.7\n    depends_on:\n      - nats\n      - redis\n    restart: unless-stopped\n    ports:\n      - \"9090:9090\"\n```\n\n## Testing Strategy\n\n```python\nimport pytest\nimport asyncio\nfrom unittest.mock import Mock, AsyncMock\n\nclass TestTradingDecisionMetaAgent:\n    @pytest.fixture\n    async def meta_agent(self):\n        config = {\n            \"name\": \"test_meta_agent\",\n            \"nats_url\": \"nats://localhost:4222\",\n            \"redis_url\": \"redis://localhost:6379\"\n        }\n        agent = TradingDecisionMetaAgent(config)\n        agent.nats = AsyncMock()\n        agent.redis = AsyncMock()\n        return agent\n    \n    @pytest.mark.asyncio\n    async def test_workflow_creation(self, meta_agent):\n        \"\"\"Test workflow creation for different instruments.\"\"\"\n        # FX signal\n        fx_signal = AgentSignal(\n            corr_id=\"test_001\",\n            agent_name=\"normalizer\",\n            signal_type=\"normalized\",\n            data={\"instrument\": \"EURUSD\", \"side\": \"buy\"},\n            confidence=1.0,\n            timestamp=\"2024-01-15T10:00:00Z\"\n        )\n        \n        workflow = await meta_agent.define_workflow(fx_signal)\n        \n        assert workflow.corr_id == \"test_001\"\n        assert \"momentum\" in workflow.required_agents\n        assert \"risk\" in workflow.required_agents\n        assert workflow.timeout_seconds == 120  # FX timeout\n    \n    @pytest.mark.asyncio\n    async def test_decision_evaluation(self, meta_agent):\n        \"\"\"Test decision evaluation with multiple signals.\"\"\"\n        context = WorkflowContext(\n            corr_id=\"test_002\",\n            workflow_id=\"test_workflow\",\n            status=WorkflowStatus.EVALUATING,\n            required_agents=[\"momentum\", \"risk\"],\n            received_signals={\n                \"momentum\": AgentSignal(\n                    corr_id=\"test_002\",\n                    agent_name=\"momentum\",\n                    signal_type=\"analysis\",\n                    data={\n                        \"analysis\": {\n                            \"trend_direction\": \"bullish\",\n                            \"momentum_strength\": 0.8\n                        }\n                    },\n                    confidence=0.9,\n                    timestamp=\"2024-01-15T10:00:00Z\"\n                ),\n                \"risk\": AgentSignal(\n                    corr_id=\"test_002\",\n                    agent_name=\"risk\",\n                    signal_type=\"analysis\",\n                    data={\n                        \"analysis\": {\n                            \"risk_level\": \"low\",\n                            \"max_position_size\": 100000\n                        }\n                    },\n                    confidence=0.8,\n                    timestamp=\"2024-01-15T10:00:00Z\"\n                )\n            },\n            started_at=\"2024-01-15T10:00:00Z\",\n            timeout_seconds=120,\n            metadata={\"instrument\": \"EURUSD\"}\n        )\n        \n        decision = await meta_agent.evaluate_signals(context)\n        \n        assert decision[\"action\"] == \"trade\"\n        assert decision[\"direction\"] == \"bullish\"\n        assert decision[\"confidence\"] > 0.7\n        assert decision[\"position_size\"] > 0\n    \n    @pytest.mark.asyncio\n    async def test_risk_blocking(self, meta_agent):\n        \"\"\"Test that risk blocking prevents trades.\"\"\"\n        context = WorkflowContext(\n            corr_id=\"test_003\",\n            workflow_id=\"test_workflow\",\n            status=WorkflowStatus.EVALUATING,\n            required_agents=[\"momentum\", \"risk\"],\n            received_signals={\n                \"risk\": AgentSignal(\n                    corr_id=\"test_003\",\n                    agent_name=\"risk\",\n                    signal_type=\"analysis\",\n                    data={\"analysis\": {\"risk_level\": \"blocked\"}},\n                    confidence=1.0,\n                    timestamp=\"2024-01-15T10:00:00Z\"\n                )\n            },\n            started_at=\"2024-01-15T10:00:00Z\",\n            timeout_seconds=120,\n            metadata={\"instrument\": \"EURUSD\"}\n        )\n        \n        decision = await meta_agent.evaluate_signals(context)\n        \n        assert decision[\"action\"] == \"no_trade\"\n        assert decision[\"reason\"] == \"risk_blocked\"\n        assert decision[\"confidence\"] == 1.0\n```\n\n## Monitoring and Observability\n\n```python\nfrom prometheus_client import Counter, Histogram, Gauge, start_http_server\n\nclass MetaAgentMetrics:\n    \"\"\"Prometheus metrics for meta-agents.\"\"\"\n    \n    def __init__(self):\n        self.workflows_started = Counter(\n            'meta_agent_workflows_started_total',\n            'Total workflows started',\n            ['agent_name', 'workflow_type']\n        )\n        \n        self.workflows_completed = Counter(\n            'meta_agent_workflows_completed_total',\n            'Total workflows completed',\n            ['agent_name', 'workflow_type', 'status']\n        )\n        \n        self.workflow_duration = Histogram(\n            'meta_agent_workflow_duration_seconds',\n            'Workflow execution time',\n            ['agent_name', 'workflow_type']\n        )\n        \n        self.active_workflows = Gauge(\n            'meta_agent_active_workflows',\n            'Currently active workflows',\n            ['agent_name']\n        )\n        \n        self.agent_signals_received = Counter(\n            'meta_agent_signals_received_total',\n            'Signals received from agents',\n            ['meta_agent', 'source_agent']\n        )\n        \n        self.decisions_published = Counter(\n            'meta_agent_decisions_published_total',\n            'Decisions published',\n            ['meta_agent', 'decision_type']\n        )\n\n# Health check endpoint\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get(\"/health\")\nasync def health_check():\n    return {\n        \"status\": \"healthy\",\n        \"agent_name\": meta_agent.name,\n        \"active_workflows\": len(meta_agent.active_workflows),\n        \"nats_connected\": meta_agent.nats.is_connected if meta_agent.nats else False,\n        \"redis_connected\": await meta_agent.redis.ping() if meta_agent.redis else False\n    }\n\n@app.get(\"/metrics\")\nasync def metrics():\n    \"\"\"Prometheus metrics endpoint.\"\"\"\n    from prometheus_client import generate_latest\n    return generate_latest()\n```\n\n---\n\n**Next Steps**: Use this template to implement specific meta-agents for your orchestration requirements. Adapt the workflow logic and agent coordination patterns to your use case.
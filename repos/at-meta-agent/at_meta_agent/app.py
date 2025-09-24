"""
Meta-agent service for coordinating multiple trading agents.

Responsibilities:
- Consume signals.normalized from NATS
- Subscribe to decisions.order_intent from all agents
- Implement consensus/voting logic for conflicting decisions
- Emit decisions.meta with coordinated actions
- Provide gRPC/HTTP control plane for strategy management
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi.responses import Response

# Import risk engine
from .risk_engine import PortfolioRiskEngine, RiskLimits, RiskViolation

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Prometheus metrics
coordinations_total = Counter('meta_coordinations_total', 'Total coordination decisions made')
coordination_latency = Histogram('meta_latency_seconds', 'Coordination decision latency')
overrides_total = Counter('meta_overrides_total', 'Total risk/manual overrides applied')
active_agents = Gauge('meta_active_agents', 'Number of active agents')
conflicting_decisions = Counter('meta_conflicting_decisions_total', 'Conflicting decisions resolved')
consensus_confidence = Gauge('meta_consensus_confidence', 'Confidence level of consensus decision')

class VotingStrategy(Enum):
    MAJORITY = "majority"
    WEIGHTED = "weighted"
    UNANIMOUS = "unanimous"
    CONFIDENCE_WEIGHTED = "confidence_weighted"

class RiskOverride(Enum):
    PAUSE_ALL = "pause_all"
    PAUSE_SYMBOL = "pause_symbol"
    REDUCE_POSITION = "reduce_position"
    EMERGENCY_STOP = "emergency_stop"

@dataclass
class AgentDecision:
    agent_id: str
    symbol: str
    action: str  # BUY, SELL, HOLD
    quantity: float
    confidence: float
    timestamp: datetime
    correlation_id: str
    reasoning: str

@dataclass
class MetaDecision:
    symbol: str
    action: str
    quantity: float
    confidence: float
    participating_agents: List[str]
    consensus_method: str
    timestamp: datetime
    correlation_id: str
    override_applied: Optional[str] = None

class MetaAgentService:
    def __init__(self):
        self.nats_client: Optional[NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.agent_decisions: Dict[str, List[AgentDecision]] = {}
        self.voting_strategy = VotingStrategy.CONFIDENCE_WEIGHTED
        self.risk_overrides: Dict[str, RiskOverride] = {}
        self.paused_strategies: set = set()
        self.symbol_limits: Dict[str, float] = {}
        self.risk_engine = PortfolioRiskEngine()

    async def connect_nats(self):
        """Connect to NATS JetStream."""
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        try:
            self.nats_client = await nats.connect(nats_url)
            self.js = self.nats_client.jetstream()
            logger.info("Connected to NATS", url=nats_url)
        except Exception as e:
            logger.error("Failed to connect to NATS", error=str(e))
            raise

    async def subscribe_to_signals(self):
        """Subscribe to normalized signals from gateway."""
        try:
            await self.js.subscribe(
                "signals.normalized",
                cb=self._handle_signal,
                durable="meta-agent-signals",
                queue="meta-agent"
            )
            logger.info("Subscribed to signals.normalized")
        except Exception as e:
            logger.error("Failed to subscribe to signals", error=str(e))
            raise

    async def subscribe_to_decisions(self):
        """Subscribe to order intents from all agents."""
        try:
            await self.js.subscribe(
                "decisions.order_intent",
                cb=self._handle_agent_decision,
                durable="meta-agent-decisions",
                queue="meta-agent"
            )
            logger.info("Subscribed to decisions.order_intent")
        except Exception as e:
            logger.error("Failed to subscribe to decisions", error=str(e))
            raise

    async def _handle_signal(self, msg):
        """Process incoming normalized signals."""
        try:
            data = json.loads(msg.data.decode())
            correlation_id = data.get("correlation_id", "unknown")

            logger.info("Received normalized signal",
                       symbol=data.get("symbol"),
                       correlation_id=correlation_id)

            # Meta-agent doesn't make direct trading decisions on signals
            # It waits for agent decisions and coordinates them
            await msg.ack()

        except Exception as e:
            logger.error("Error processing signal", error=str(e))
            await msg.nak()

    async def _handle_agent_decision(self, msg):
        """Process order intent decisions from agents."""
        try:
            data = json.loads(msg.data.decode())

            decision = AgentDecision(
                agent_id=data["agent_id"],
                symbol=data["symbol"],
                action=data["action"],
                quantity=data["quantity"],
                confidence=data.get("confidence", 0.5),
                timestamp=datetime.fromisoformat(data["timestamp"]),
                correlation_id=data["correlation_id"],
                reasoning=data.get("reasoning", "")
            )

            logger.info("Received agent decision",
                       agent_id=decision.agent_id,
                       symbol=decision.symbol,
                       action=decision.action,
                       confidence=decision.confidence,
                       correlation_id=decision.correlation_id)

            # Store decision for coordination
            symbol = decision.symbol
            if symbol not in self.agent_decisions:
                self.agent_decisions[symbol] = []

            self.agent_decisions[symbol].append(decision)

            # Check if we have enough decisions to make a meta-decision
            await self._coordinate_decisions(symbol, decision.correlation_id)

            await msg.ack()
            active_agents.set(len(set(d.agent_id for decisions in self.agent_decisions.values() for d in decisions)))

        except Exception as e:
            logger.error("Error processing agent decision", error=str(e))
            await msg.nak()

    async def _coordinate_decisions(self, symbol: str, correlation_id: str):
        """Coordinate decisions for a symbol using voting strategy."""
        decisions = self.agent_decisions.get(symbol, [])

        # Only coordinate if we have multiple decisions for the same correlation
        relevant_decisions = [d for d in decisions if d.correlation_id == correlation_id]

        if len(relevant_decisions) < 2:
            return  # Wait for more decisions

        with coordination_latency.time():
            meta_decision = await self._apply_voting_strategy(relevant_decisions)

            if meta_decision:
                # Apply risk overrides
                meta_decision = await self._apply_risk_overrides(meta_decision)

                # Publish meta decision
                await self._publish_meta_decision(meta_decision)

                # Clean up processed decisions
                self.agent_decisions[symbol] = [
                    d for d in self.agent_decisions[symbol]
                    if d.correlation_id != correlation_id
                ]

                coordinations_total.inc()

    async def _apply_voting_strategy(self, decisions: List[AgentDecision]) -> Optional[MetaDecision]:
        """Apply voting strategy to reach consensus."""
        if len(decisions) < 2:
            return None

        symbol = decisions[0].symbol
        correlation_id = decisions[0].correlation_id

        if self.voting_strategy == VotingStrategy.CONFIDENCE_WEIGHTED:
            return await self._confidence_weighted_vote(decisions)
        elif self.voting_strategy == VotingStrategy.MAJORITY:
            return await self._majority_vote(decisions)
        elif self.voting_strategy == VotingStrategy.WEIGHTED:
            return await self._weighted_vote(decisions)
        elif self.voting_strategy == VotingStrategy.UNANIMOUS:
            return await self._unanimous_vote(decisions)

        return None

    async def _confidence_weighted_vote(self, decisions: List[AgentDecision]) -> Optional[MetaDecision]:
        """Weight decisions by agent confidence levels."""
        action_weights = {}
        total_weight = 0

        for decision in decisions:
            action = decision.action
            weight = decision.confidence

            if action not in action_weights:
                action_weights[action] = {"weight": 0, "quantity": 0, "agents": []}

            action_weights[action]["weight"] += weight
            action_weights[action]["quantity"] += decision.quantity * weight
            action_weights[action]["agents"].append(decision.agent_id)
            total_weight += weight

        if not action_weights:
            return None

        # Find action with highest weighted confidence
        winning_action = max(action_weights.keys(), key=lambda x: action_weights[x]["weight"])
        winning_data = action_weights[winning_action]

        # Check for conflicts
        if len(action_weights) > 1:
            conflicting_decisions.inc()

        confidence = winning_data["weight"] / total_weight if total_weight > 0 else 0
        avg_quantity = winning_data["quantity"] / winning_data["weight"] if winning_data["weight"] > 0 else 0

        consensus_confidence.set(confidence)

        return MetaDecision(
            symbol=decisions[0].symbol,
            action=winning_action,
            quantity=avg_quantity,
            confidence=confidence,
            participating_agents=winning_data["agents"],
            consensus_method="confidence_weighted",
            timestamp=datetime.utcnow(),
            correlation_id=decisions[0].correlation_id
        )

    async def _majority_vote(self, decisions: List[AgentDecision]) -> Optional[MetaDecision]:
        """Simple majority voting."""
        action_counts = {}

        for decision in decisions:
            action = decision.action
            if action not in action_counts:
                action_counts[action] = {"count": 0, "agents": [], "total_quantity": 0}
            action_counts[action]["count"] += 1
            action_counts[action]["agents"].append(decision.agent_id)
            action_counts[action]["total_quantity"] += decision.quantity

        winning_action = max(action_counts.keys(), key=lambda x: action_counts[x]["count"])
        winning_data = action_counts[winning_action]

        confidence = winning_data["count"] / len(decisions)
        avg_quantity = winning_data["total_quantity"] / winning_data["count"]

        return MetaDecision(
            symbol=decisions[0].symbol,
            action=winning_action,
            quantity=avg_quantity,
            confidence=confidence,
            participating_agents=winning_data["agents"],
            consensus_method="majority",
            timestamp=datetime.utcnow(),
            correlation_id=decisions[0].correlation_id
        )

    async def _weighted_vote(self, decisions: List[AgentDecision]) -> Optional[MetaDecision]:
        """Weighted voting (placeholder for future agent performance weighting)."""
        # For now, treat as equal weight majority
        return await self._majority_vote(decisions)

    async def _unanimous_vote(self, decisions: List[AgentDecision]) -> Optional[MetaDecision]:
        """Require unanimous agreement."""
        if len(set(d.action for d in decisions)) > 1:
            logger.info("No unanimous agreement", symbol=decisions[0].symbol)
            return None

        return await self._majority_vote(decisions)

    async def _apply_risk_overrides(self, decision: MetaDecision) -> Optional[MetaDecision]:
        """Apply risk management overrides."""
        symbol = decision.symbol

        # Check portfolio risk engine first
        # Estimate a price for risk checking (in production, would get from market data)
        estimated_price = 100.0  # Placeholder

        allowed, violation = await self.risk_engine.check_order_risk(
            symbol=symbol,
            action=decision.action,
            quantity=decision.quantity,
            price=estimated_price
        )

        if not allowed:
            logger.warning("Risk engine blocked decision",
                         symbol=symbol,
                         action=decision.action,
                         violation=violation.message if violation else "Unknown")

            # Emit risk violation if NATS is connected
            if violation and self.js:
                await self.risk_engine.emit_risk_violation(violation, self.nats_client, self.js)

            # Convert to HOLD action
            decision.action = "HOLD"
            decision.quantity = 0
            decision.override_applied = f"risk_blocked: {violation.violation_type.value if violation else 'unknown'}"
            overrides_total.inc()
            return decision

        # Check for emergency stop
        if "emergency_stop" in self.risk_overrides or self.risk_engine.kill_switch_active:
            decision.action = "HOLD"
            decision.quantity = 0
            decision.override_applied = "emergency_stop"
            overrides_total.inc()
            return decision

        # Check for paused strategies
        if symbol in self.paused_strategies or symbol in self.risk_engine.blocked_symbols:
            decision.action = "HOLD"
            decision.quantity = 0
            decision.override_applied = "symbol_paused"
            overrides_total.inc()
            return decision

        # Check position limits
        if symbol in self.symbol_limits:
            max_quantity = self.symbol_limits[symbol]
            if decision.quantity > max_quantity:
                decision.quantity = max_quantity
                decision.override_applied = "position_limit"
                overrides_total.inc()

        return decision

    async def _publish_meta_decision(self, decision: MetaDecision):
        """Publish coordinated meta decision."""
        try:
            decision_data = {
                "symbol": decision.symbol,
                "action": decision.action,
                "quantity": decision.quantity,
                "confidence": decision.confidence,
                "participating_agents": decision.participating_agents,
                "consensus_method": decision.consensus_method,
                "timestamp": decision.timestamp.isoformat(),
                "correlation_id": decision.correlation_id,
                "override_applied": decision.override_applied,
                "source": "meta-agent"
            }

            await self.js.publish(
                "decisions.meta",
                json.dumps(decision_data).encode()
            )

            logger.info("Published meta decision",
                       symbol=decision.symbol,
                       action=decision.action,
                       quantity=decision.quantity,
                       confidence=decision.confidence,
                       agents=decision.participating_agents,
                       correlation_id=decision.correlation_id)

        except Exception as e:
            logger.error("Failed to publish meta decision", error=str(e))

# FastAPI app for control plane
app = FastAPI(title="Meta-Agent Service", version="0.1.0")
meta_service = MetaAgentService()

@app.on_event("startup")
async def startup():
    """Initialize NATS connections on startup."""
    await meta_service.connect_nats()
    await meta_service.subscribe_to_signals()
    await meta_service.subscribe_to_decisions()

@app.on_event("shutdown")
async def shutdown():
    """Clean shutdown."""
    if meta_service.nats_client:
        await meta_service.nats_client.close()

@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "meta-agent",
        "timestamp": datetime.utcnow().isoformat(),
        "nats_connected": meta_service.nats_client is not None,
        "active_agents": len(set(d.agent_id for decisions in meta_service.agent_decisions.values() for d in decisions))
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type="text/plain")

@app.post("/control/pause_strategy")
async def pause_strategy(strategy_id: str):
    """Pause a specific strategy."""
    meta_service.paused_strategies.add(strategy_id)
    logger.info("Strategy paused", strategy_id=strategy_id)
    return {"status": "paused", "strategy_id": strategy_id}

@app.post("/control/resume_strategy")
async def resume_strategy(strategy_id: str):
    """Resume a paused strategy."""
    meta_service.paused_strategies.discard(strategy_id)
    logger.info("Strategy resumed", strategy_id=strategy_id)
    return {"status": "resumed", "strategy_id": strategy_id}

@app.post("/control/emergency_stop")
async def emergency_stop():
    """Emergency stop all trading."""
    meta_service.risk_overrides["emergency_stop"] = RiskOverride.EMERGENCY_STOP
    overrides_total.inc()
    logger.warning("Emergency stop activated")
    return {"status": "emergency_stop_activated"}

@app.post("/control/set_voting_strategy")
async def set_voting_strategy(strategy: VotingStrategy):
    """Change voting strategy."""
    meta_service.voting_strategy = strategy
    logger.info("Voting strategy changed", strategy=strategy.value)
    return {"status": "updated", "voting_strategy": strategy.value}

@app.get("/status")
async def get_status():
    """Get current meta-agent status."""
    return {
        "voting_strategy": meta_service.voting_strategy.value,
        "paused_strategies": list(meta_service.paused_strategies),
        "active_decisions": {symbol: len(decisions) for symbol, decisions in meta_service.agent_decisions.items()},
        "risk_overrides": list(meta_service.risk_overrides.keys()),
        "symbol_limits": meta_service.symbol_limits,
        "risk_summary": meta_service.risk_engine.get_risk_summary()
    }

# Risk management endpoints
@app.get("/risk/summary")
async def get_risk_summary():
    """Get current risk summary."""
    return meta_service.risk_engine.get_risk_summary()

@app.post("/risk/limits")
async def update_risk_limits(
    max_daily_loss: Optional[float] = None,
    max_position_value: Optional[float] = None,
    max_total_exposure: Optional[float] = None,
    max_concentration: Optional[float] = None
):
    """Update risk limits."""
    limits = meta_service.risk_engine.risk_limits

    if max_daily_loss is not None:
        limits.max_daily_loss = max_daily_loss
    if max_position_value is not None:
        limits.max_position_value = max_position_value
    if max_total_exposure is not None:
        limits.max_total_exposure = max_total_exposure
    if max_concentration is not None:
        limits.max_concentration = max_concentration

    logger.info("Risk limits updated", limits=asdict(limits))
    return {"status": "updated", "limits": asdict(limits)}

@app.post("/risk/block_symbol")
async def block_symbol(symbol: str):
    """Block trading for a specific symbol."""
    meta_service.risk_engine.blocked_symbols.add(symbol)
    logger.warning("Symbol blocked", symbol=symbol)
    return {"status": "blocked", "symbol": symbol}

@app.post("/risk/unblock_symbol")
async def unblock_symbol(symbol: str):
    """Unblock trading for a specific symbol."""
    meta_service.risk_engine.blocked_symbols.discard(symbol)
    logger.info("Symbol unblocked", symbol=symbol)
    return {"status": "unblocked", "symbol": symbol}

@app.post("/risk/reset_daily")
async def reset_daily_risk():
    """Reset daily risk counters."""
    await meta_service.risk_engine.reset_daily_counters()
    return {"status": "daily_counters_reset"}

@app.get("/risk/violations")
async def get_risk_violations(limit: int = 20):
    """Get recent risk violations."""
    violations = meta_service.risk_engine.violations[-limit:]
    return {
        "violations": [
            {
                "type": v.violation_type.value,
                "symbol": v.symbol,
                "message": v.message,
                "severity": v.severity,
                "timestamp": v.timestamp.isoformat(),
                "metadata": v.metadata
            }
            for v in violations
        ],
        "total_count": len(meta_service.risk_engine.violations)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
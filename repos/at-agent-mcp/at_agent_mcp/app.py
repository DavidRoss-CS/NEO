import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum

import numpy as np
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import nats
from nats.errors import ConnectionClosedError, TimeoutError as NatsTimeoutError
from pydantic import BaseModel, Field

# Environment variables
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
NATS_STREAM = os.getenv("NATS_STREAM", "trading-events")
SERVICE_NAME = os.getenv("SERVICE_NAME", "at-agent-mcp")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
AGENT_ID = os.getenv("AGENT_ID", f"agent_{uuid.uuid4().hex[:8]}")
STRATEGY_TYPE = os.getenv("STRATEGY_TYPE", "momentum")  # momentum, mean_reversion, hybrid
RISK_LIMIT = float(os.getenv("RISK_LIMIT", "0.02"))  # 2% max risk per trade
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))

# Configure structured logging
logger = structlog.get_logger()

# Prometheus metrics
signals_received = Counter('mcp_signals_received_total', 'Total signals received', ['instrument', 'signal_type'])
decisions_generated = Counter('mcp_decisions_generated_total', 'Total decisions generated', ['strategy', 'side'])
strategy_confidence = Histogram('mcp_strategy_confidence', 'Strategy confidence distribution', ['strategy'])
processing_duration = Histogram('mcp_processing_duration_seconds', 'Signal processing duration', ['strategy'])
active_positions = Gauge('mcp_active_positions', 'Number of active positions')
error_count = Counter('mcp_errors_total', 'Total errors', ['error_type'])
nats_connection_status = Gauge('mcp_nats_connected', 'NATS connection status')

app = FastAPI(
    title="at-agent-mcp",
    description="MCP Trading Agent Server",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=3600,
)

# Global state
nats_client: Optional[nats.NATS] = None
js_client = None
start_time = time.time()
position_tracker: Dict[str, Dict] = {}  # Track positions by instrument
signal_buffer: List[Dict] = []  # Recent signals for analysis

class TradingSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"

class StrategyEngine:
    """Trading strategy engine"""

    def __init__(self, strategy_type: str, risk_limit: float):
        self.strategy_type = strategy_type
        self.risk_limit = risk_limit
        self.momentum_window = 20
        self.mean_reversion_threshold = 2.0  # Standard deviations

    async def analyze_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze signal and generate trading decision"""

        instrument = signal.get("instrument")
        signal_type = signal.get("signal_type")
        strength = signal.get("strength", 0)
        price = signal.get("price", 0)

        # Skip if signal strength below threshold
        if strength < CONFIDENCE_THRESHOLD:
            logger.debug(
                "Signal below confidence threshold",
                instrument=instrument,
                strength=strength,
                threshold=CONFIDENCE_THRESHOLD
            )
            return None

        # Check position limits
        if len(position_tracker) >= MAX_POSITIONS:
            logger.warning(
                "Max positions reached",
                current_positions=len(position_tracker),
                max_positions=MAX_POSITIONS
            )
            return None

        # Apply strategy logic
        if self.strategy_type == "momentum":
            decision = await self._momentum_strategy(signal)
        elif self.strategy_type == "mean_reversion":
            decision = await self._mean_reversion_strategy(signal)
        elif self.strategy_type == "hybrid":
            decision = await self._hybrid_strategy(signal)
        else:
            decision = None

        if decision:
            # Add metadata
            decision["strategy_id"] = f"{self.strategy_type}_v1"
            decision["agent_id"] = AGENT_ID
            decision["risk_score"] = self._calculate_risk_score(decision)
            decision["signal_refs"] = [signal.get("corr_id")]

            # Record confidence
            strategy_confidence.labels(strategy=self.strategy_type).observe(decision["confidence"])

        return decision

    async def _momentum_strategy(self, signal: Dict) -> Optional[Dict]:
        """Momentum-based strategy"""

        signal_type = signal.get("signal_type", "")
        strength = signal.get("strength", 0)

        # Look for strong directional signals
        if "bullish" in signal_type.lower() or "buy" in signal_type.lower():
            return {
                "instrument": signal["instrument"],
                "side": TradingSide.BUY,
                "order_type": OrderType.MARKET,
                "quantity": self._calculate_position_size(signal),
                "confidence": min(strength * 1.1, 1.0),  # Boost confidence for momentum
                "reasoning": f"Momentum strategy: {signal_type} with strength {strength:.2f}"
            }
        elif "bearish" in signal_type.lower() or "sell" in signal_type.lower():
            return {
                "instrument": signal["instrument"],
                "side": TradingSide.SELL,
                "order_type": OrderType.MARKET,
                "quantity": self._calculate_position_size(signal),
                "confidence": min(strength * 1.1, 1.0),
                "reasoning": f"Momentum strategy: {signal_type} with strength {strength:.2f}"
            }

        return None

    async def _mean_reversion_strategy(self, signal: Dict) -> Optional[Dict]:
        """Mean reversion strategy"""

        # Add to signal buffer for analysis
        signal_buffer.append(signal)
        if len(signal_buffer) > 100:
            signal_buffer.pop(0)

        # Need sufficient data
        if len(signal_buffer) < 20:
            return None

        # Calculate statistics
        instrument = signal["instrument"]
        recent_prices = [s["price"] for s in signal_buffer if s.get("instrument") == instrument]

        if len(recent_prices) < 10:
            return None

        mean_price = np.mean(recent_prices)
        std_price = np.std(recent_prices)
        current_price = signal["price"]
        z_score = (current_price - mean_price) / std_price if std_price > 0 else 0

        # Trade on extremes
        if z_score > self.mean_reversion_threshold:
            # Price too high, sell
            return {
                "instrument": instrument,
                "side": TradingSide.SELL,
                "order_type": OrderType.LIMIT,
                "price": current_price * 0.999,  # Slightly below current
                "quantity": self._calculate_position_size(signal),
                "confidence": min(abs(z_score) / 3, 0.95),
                "reasoning": f"Mean reversion: Z-score {z_score:.2f} (overbought)"
            }
        elif z_score < -self.mean_reversion_threshold:
            # Price too low, buy
            return {
                "instrument": instrument,
                "side": TradingSide.BUY,
                "order_type": OrderType.LIMIT,
                "price": current_price * 1.001,  # Slightly above current
                "quantity": self._calculate_position_size(signal),
                "confidence": min(abs(z_score) / 3, 0.95),
                "reasoning": f"Mean reversion: Z-score {z_score:.2f} (oversold)"
            }

        return None

    async def _hybrid_strategy(self, signal: Dict) -> Optional[Dict]:
        """Combine momentum and mean reversion"""

        # Try momentum first
        momentum_decision = await self._momentum_strategy(signal)
        mean_rev_decision = await self._mean_reversion_strategy(signal)

        if momentum_decision and mean_rev_decision:
            # Both strategies agree
            if momentum_decision["side"] == mean_rev_decision["side"]:
                momentum_decision["confidence"] = min(
                    (momentum_decision["confidence"] + mean_rev_decision["confidence"]) / 1.5,
                    0.99
                )
                momentum_decision["reasoning"] = "Hybrid: Momentum and mean reversion agree"
                return momentum_decision
            else:
                # Strategies disagree, skip
                return None

        # Return whichever has higher confidence
        if momentum_decision and not mean_rev_decision:
            return momentum_decision
        elif mean_rev_decision and not momentum_decision:
            return mean_rev_decision

        return None

    def _calculate_position_size(self, signal: Dict) -> float:
        """Calculate position size based on risk management"""
        # Simple fixed size for now
        base_size = 10000  # Base unit size
        strength = signal.get("strength", 0.5)

        # Scale by signal strength and risk limit
        position_size = base_size * strength * self.risk_limit * 10

        return round(position_size, 2)

    def _calculate_risk_score(self, decision: Dict) -> float:
        """Calculate risk score for decision"""
        # Simple risk scoring
        base_risk = 5.0  # Medium risk baseline

        # Adjust for order type
        if decision["order_type"] == OrderType.MARKET:
            base_risk += 1.0  # Higher risk for market orders

        # Adjust for confidence
        confidence_adjustment = (1 - decision["confidence"]) * 3

        return min(base_risk + confidence_adjustment, 10.0)

# Initialize strategy engine
strategy_engine = StrategyEngine(STRATEGY_TYPE, RISK_LIMIT)

@app.on_event("startup")
async def startup_event():
    """Initialize NATS connection and start consuming signals"""
    global nats_client, js_client

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    try:
        # Connect to NATS
        nats_client = await nats.connect(NATS_URL)
        js_client = nats_client.jetstream()
        nats_connection_status.set(1)

        # Subscribe to normalized signals
        await js_client.subscribe(
            "signals.normalized",
            cb=handle_signal,
            durable="mcp-signals",
            manual_ack=True
        )

        logger.info(
            "MCP Agent started",
            agent_id=AGENT_ID,
            strategy=STRATEGY_TYPE,
            port=8002,
            service_name=SERVICE_NAME,
            nats_url=NATS_URL
        )

    except Exception as e:
        logger.error(f"Failed to start MCP agent: {e}")
        nats_connection_status.set(0)
        error_count.labels(error_type="startup").inc()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    global nats_client
    if nats_client:
        await nats_client.close()
    logger.info("MCP Agent stopped")

async def handle_signal(msg):
    """Process incoming signals"""
    start = time.time()

    try:
        # Parse signal
        signal_data = json.loads(msg.data.decode())
        corr_id = signal_data.get("corr_id", "unknown")
        instrument = signal_data.get("instrument", "unknown")
        signal_type = signal_data.get("signal_type", "unknown")

        # Record metrics
        signals_received.labels(
            instrument=instrument,
            signal_type=signal_type
        ).inc()

        logger.info(
            "Signal received",
            corr_id=corr_id,
            instrument=instrument,
            signal_type=signal_type,
            strength=signal_data.get("strength")
        )

        # Analyze with strategy engine
        decision = await strategy_engine.analyze_signal(signal_data)

        if decision:
            # Create order intent event
            order_intent = {
                "corr_id": corr_id,
                "strategy_id": decision["strategy_id"],
                "agent_id": decision["agent_id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "instrument": decision["instrument"],
                "side": decision["side"],
                "order_type": decision["order_type"],
                "quantity": decision["quantity"],
                "confidence": decision["confidence"],
                "reasoning": decision.get("reasoning"),
                "risk_score": decision.get("risk_score"),
                "signal_refs": decision.get("signal_refs", [])
            }

            # Add price for limit orders
            if "price" in decision:
                order_intent["price"] = decision["price"]

            # Publish decision
            await js_client.publish(
                "decisions.order_intent",
                json.dumps(order_intent).encode(),
                headers={
                    "Corr-ID": corr_id,
                    "Agent-ID": AGENT_ID,
                    "Strategy": decision["strategy_id"]
                }
            )

            # Update position tracker
            position_tracker[decision["instrument"]] = {
                "side": decision["side"],
                "quantity": decision["quantity"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            active_positions.set(len(position_tracker))

            # Record metrics
            decisions_generated.labels(
                strategy=decision["strategy_id"],
                side=decision["side"]
            ).inc()

            logger.info(
                "Decision generated",
                corr_id=corr_id,
                instrument=decision["instrument"],
                side=decision["side"],
                confidence=decision["confidence"]
            )

        # Acknowledge message
        await msg.ack()

    except Exception as e:
        logger.error(
            "Error processing signal",
            error=str(e),
            corr_id=signal_data.get("corr_id") if 'signal_data' in locals() else "unknown"
        )
        error_count.labels(error_type="signal_processing").inc()
        # Don't ack on error - let it retry

    finally:
        # Record processing time
        duration = time.time() - start
        processing_duration.labels(strategy=STRATEGY_TYPE).observe(duration)

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "ok": True,
        "service": SERVICE_NAME,
        "agent_id": AGENT_ID,
        "strategy": STRATEGY_TYPE,
        "uptime_seconds": int(time.time() - start_time),
        "nats_connected": nats_client is not None and nats_client.is_connected,
        "active_positions": len(position_tracker),
        "signals_buffered": len(signal_buffer)
    }

    if not health_status["nats_connected"]:
        health_status["ok"] = False
        health_status["error"] = "NATS disconnected"
        return JSONResponse(status_code=503, content=health_status)

    return health_status

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.get("/status")
async def status():
    """Detailed agent status"""
    return {
        "agent_id": AGENT_ID,
        "strategy": {
            "type": STRATEGY_TYPE,
            "risk_limit": RISK_LIMIT,
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "max_positions": MAX_POSITIONS
        },
        "positions": position_tracker,
        "metrics": {
            "signals_received": len(signal_buffer),
            "active_positions": len(position_tracker)
        },
        "health": {
            "nats_connected": nats_client is not None and nats_client.is_connected,
            "uptime_seconds": int(time.time() - start_time)
        }
    }

@app.post("/positions/clear")
async def clear_positions():
    """Clear all tracked positions (admin endpoint)"""
    global position_tracker
    count = len(position_tracker)
    position_tracker = {}
    active_positions.set(0)

    logger.info("Positions cleared", count=count)

    return {
        "status": "cleared",
        "positions_cleared": count
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)
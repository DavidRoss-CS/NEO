import asyncio
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import jsonschema
import structlog

logger = structlog.get_logger(__name__)

class ExecutionSimulator:
    def __init__(self, orders_received=None, fills_generated=None):
        # Prometheus metrics (passed from app)
        self.orders_received = orders_received
        self.fills_generated = fills_generated

        # Simulation parameters from environment
        self.min_delay_ms = int(os.getenv("SIMULATION_MIN_DELAY_MS", "100"))
        self.max_delay_ms = int(os.getenv("SIMULATION_MAX_DELAY_MS", "2000"))
        self.partial_fill_chance = float(os.getenv("SIMULATION_PARTIAL_FILL_CHANCE", "0.1"))
        self.max_slippage_bps = float(os.getenv("SIMULATION_SLIPPAGE_BPS", "2"))

        # Load schema for validation (placeholder - would load from at-core)
        self.order_intent_schema = self._get_order_intent_schema()

        # Idempotency tracking
        self.processed_orders = {}
        self.idempotency_ttl = int(os.getenv("IDEMPOTENCY_TTL_SEC", "3600"))

    def _get_order_intent_schema(self) -> Dict[str, Any]:
        """Get order intent schema (placeholder - should load from at-core)"""
        return {
            "type": "object",
            "required": ["corr_id", "agent_id", "instrument", "side", "quantity", "order_type", "timestamp"],
            "properties": {
                "corr_id": {"type": "string", "minLength": 1},
                "agent_id": {"type": "string", "minLength": 1},
                "instrument": {"type": "string", "pattern": "^[A-Z]{3,6}(/[A-Z]{3,6})?$"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "quantity": {"type": "number", "minimum": 0.001},
                "order_type": {"type": "string", "enum": ["market", "limit", "stop"]},
                "price_limit": {"type": ["number", "null"]},
                "timestamp": {"type": "string", "format": "date-time"},
                "strategy": {"type": "string"},
                "risk_params": {"type": "object"}
            },
            "additionalProperties": True
        }

    async def process_order_intent(self, order_data: Dict[str, Any], corr_id: str, nats_client):
        """Process an order intent event and simulate execution"""
        start_time = time.time()

        try:
            # Check for duplicate processing (idempotency)
            if self._is_duplicate_order(corr_id):
                logger.warning("Duplicate order intent detected",
                              corr_id=corr_id,
                              instrument=order_data.get("instrument"))
                return

            # Validate schema
            validation_result = self._validate_order_schema(order_data, corr_id)
            if not validation_result["valid"]:
                if self.orders_received:
                    self.orders_received.labels(status="invalid").inc()
                return

            # Count valid order received
            if self.orders_received:
                self.orders_received.labels(status="valid").inc()

            # Extract order details
            instrument = order_data["instrument"]
            side = order_data["side"]
            quantity = order_data["quantity"]
            order_type = order_data["order_type"]
            agent_id = order_data["agent_id"]

            logger.info("Starting execution simulation",
                       corr_id=corr_id,
                       instrument=instrument,
                       side=side,
                       quantity=quantity,
                       order_type=order_type)

            # Simulate execution delay
            delay_ms = random.randint(self.min_delay_ms, self.max_delay_ms)
            await asyncio.sleep(delay_ms / 1000.0)

            # Simulate execution
            fill_result = self._simulate_execution(order_data)

            # Generate fill event
            fill_event = self._create_fill_event(order_data, fill_result, corr_id)

            # Generate reconcile event
            reconcile_event = self._create_reconcile_event(order_data, fill_result, corr_id)

            # Publish events
            await nats_client.publish_fill(fill_event, corr_id)
            await nats_client.publish_reconcile(reconcile_event, corr_id)

            # Record fill generated
            if self.fills_generated:
                self.fills_generated.labels(fill_type=fill_result["fill_status"], instrument=instrument).inc()

            # Record processing for idempotency
            self._record_processed_order(corr_id, fill_event["fill_id"])

            # Record metrics
            duration = time.time() - start_time
            logger.info("Execution simulation completed",
                       corr_id=corr_id,
                       fill_id=fill_event["fill_id"],
                       quantity_filled=fill_result["quantity_filled"],
                       fill_status=fill_result["fill_status"],
                       simulation_delay_ms=delay_ms,
                       total_duration_ms=int(duration * 1000))

        except Exception as e:
            logger.error("Error in execution simulation",
                        corr_id=corr_id,
                        error=str(e),
                        duration_ms=int((time.time() - start_time) * 1000))
            raise

    def _validate_order_schema(self, order_data: Dict[str, Any], corr_id: str) -> Dict[str, Any]:
        """Validate order intent against schema"""
        try:
            # Check for unknown fields first (log but don't fail)
            schema_properties = set(self.order_intent_schema.get("properties", {}).keys())
            order_fields = set(order_data.keys())
            unknown_fields = order_fields - schema_properties

            if unknown_fields:
                logger.info("Unknown fields detected in order data",
                           corr_id=corr_id,
                           unknown_fields=list(unknown_fields),
                           unknown_count=len(unknown_fields))

                # Track metrics for unknown fields
                if hasattr(self, 'unknown_fields'):
                    for field in unknown_fields:
                        self.unknown_fields.labels(field_name=field).inc()

            # Validate with schema (allowing additional properties)
            jsonschema.validate(order_data, self.order_intent_schema)

            logger.debug("Order schema validation passed",
                        corr_id=corr_id,
                        required_fields_present=len(schema_properties & order_fields),
                        unknown_fields_count=len(unknown_fields))
            return {"valid": True, "unknown_fields": list(unknown_fields)}

        except jsonschema.ValidationError as e:
            logger.error("Order schema validation failed",
                        corr_id=corr_id,
                        error_code="EXEC-001",
                        validation_errors=[str(e)],
                        schema_version="1.0.0")
            return {"valid": False, "error": "EXEC-001", "details": str(e)}

        except Exception as e:
            logger.error("Schema validation error",
                        corr_id=corr_id,
                        error=str(e))
            return {"valid": False, "error": "EXEC-001", "details": str(e)}

    def _simulate_execution(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate the actual execution with realistic behavior"""
        quantity_requested = order_data["quantity"]
        order_type = order_data["order_type"]
        side = order_data["side"]

        # Determine if this will be a partial fill
        is_partial = random.random() < self.partial_fill_chance

        if is_partial:
            # Partial fill: 30-95% of requested quantity
            fill_ratio = random.uniform(0.3, 0.95)
            quantity_filled = quantity_requested * fill_ratio
            fill_status = "partial"
            partial_fill_reason = random.choice([
                "liquidity_constraint",
                "market_impact",
                "position_limit"
            ])
        else:
            quantity_filled = quantity_requested
            fill_status = "full"
            partial_fill_reason = None

        # Simulate market price (placeholder - would use real market data)
        base_price = self._get_simulated_market_price(order_data["instrument"])

        # Calculate slippage for market orders
        if order_type == "market":
            slippage_bps = random.uniform(0, self.max_slippage_bps)
            if side == "buy":
                fill_price = base_price * (1 + slippage_bps / 10000)
            else:
                fill_price = base_price * (1 - slippage_bps / 10000)
        else:
            # Limit/stop orders execute at specified price
            fill_price = order_data.get("price_limit", base_price)
            slippage_bps = 0

        return {
            "quantity_filled": round(quantity_filled, 6),
            "fill_price": round(fill_price, 6),
            "fill_status": fill_status,
            "slippage_bps": round(slippage_bps, 2),
            "partial_fill_reason": partial_fill_reason
        }

    def _get_simulated_market_price(self, instrument: str) -> float:
        """Get simulated market price for instrument"""
        # Placeholder prices for common instruments
        prices = {
            "EURUSD": 1.0945,
            "GBPUSD": 1.2634,
            "USDJPY": 149.75,
            "BTC/USD": 42500.00,
            "ETH/USD": 2650.00,
            "SPY": 485.50,
            "QQQ": 389.25
        }

        base_price = prices.get(instrument, 100.0)

        # Add some random variation (±0.1%)
        variation = random.uniform(-0.001, 0.001)
        return base_price * (1 + variation)

    def _create_fill_event(self, order_data: Dict[str, Any], fill_result: Dict[str, Any], corr_id: str) -> Dict[str, Any]:
        """Create execution fill event"""
        fill_id = f"fill_{uuid.uuid4().hex[:8]}"
        fill_timestamp = datetime.now(timezone.utc).isoformat()

        return {
            "corr_id": corr_id,
            "fill_id": fill_id,
            "instrument": order_data["instrument"],
            "side": order_data["side"],
            "quantity_requested": order_data["quantity"],
            "quantity_filled": fill_result["quantity_filled"],
            "avg_fill_price": fill_result["fill_price"],
            "fill_status": fill_result["fill_status"],
            "execution_venue": "simulator",
            "fill_timestamp": fill_timestamp,
            "simulation_metadata": {
                "delay_ms": random.randint(self.min_delay_ms, self.max_delay_ms),
                "slippage_bps": fill_result["slippage_bps"],
                "partial_fill_reason": fill_result.get("partial_fill_reason")
            }
        }

    def _create_reconcile_event(self, order_data: Dict[str, Any], fill_result: Dict[str, Any], corr_id: str) -> Dict[str, Any]:
        """Create reconciliation event for position tracking"""
        reconcile_id = f"rec_{uuid.uuid4().hex[:8]}"
        reconcile_timestamp = datetime.now(timezone.utc).isoformat()

        # Calculate position delta (positive for buy, negative for sell)
        position_delta = fill_result["quantity_filled"]
        if order_data["side"] == "sell":
            position_delta = -position_delta

        return {
            "corr_id": corr_id,
            "reconcile_id": reconcile_id,
            "agent_id": order_data["agent_id"],
            "instrument": order_data["instrument"],
            "position_delta": position_delta,
            "realized_pnl": 0.0,  # No P&L calculation in simulation
            "unrealized_pnl": 0.0,
            "reconcile_timestamp": reconcile_timestamp,
            "reconcile_type": "execution"
        }

    def _is_duplicate_order(self, corr_id: str) -> bool:
        """Check if order has already been processed (idempotency)"""
        current_time = time.time()

        # Clean up expired entries
        expired_keys = [
            key for key, data in self.processed_orders.items()
            if current_time - data["timestamp"] > self.idempotency_ttl
        ]
        for key in expired_keys:
            del self.processed_orders[key]

        return corr_id in self.processed_orders

    def _record_processed_order(self, corr_id: str, fill_id: str):
        """Record that an order has been processed"""
        self.processed_orders[corr_id] = {
            "fill_id": fill_id,
            "timestamp": time.time()
        }

    def get_pending_count(self) -> int:
        """Get number of orders being processed"""
        # For now, return 0 as we process synchronously
        # Could be enhanced to track async processing
        return 0
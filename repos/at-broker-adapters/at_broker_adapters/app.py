"""
Broker adapter service for managing multiple broker connections.

Responsibilities:
- Manage multiple broker adapter instances
- Route orders to appropriate brokers
- Provide unified API for order management
- Handle order state machine and reconciliation
- Monitor broker connection health
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi.responses import Response

from .base_adapter import BrokerAdapter, BrokerError
from .models import Order, Fill, Position, Account, OrderStatus, OrderSide, OrderType, TimeInForce
from .adapters.paper_adapter import PaperTradingAdapter
from .adapters.ib_adapter import InteractiveBrokersAdapter
from .adapters.alpaca_adapter import AlpacaAdapter

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
orders_submitted = Counter('broker_orders_submitted_total', 'Orders submitted to brokers', ['broker', 'symbol'])
orders_filled = Counter('broker_orders_filled_total', 'Orders filled by brokers', ['broker', 'symbol'])
orders_rejected = Counter('broker_orders_rejected_total', 'Orders rejected by brokers', ['broker', 'reason'])
order_latency = Histogram('broker_order_latency_seconds', 'Order submission latency', ['broker'])
active_connections = Gauge('broker_active_connections', 'Active broker connections', ['broker'])
reconciliation_errors = Counter('broker_reconciliation_errors_total', 'Order reconciliation errors', ['broker'])

class BrokerType(Enum):
    PAPER = "paper"
    INTERACTIVE_BROKERS = "ib"
    ALPACA = "alpaca"

@dataclass
class BrokerConfig:
    broker_type: BrokerType
    name: str
    config: Dict[str, Any]
    enabled: bool = True
    primary: bool = False

class BrokerAdapterService:
    def __init__(self):
        self.nats_client: Optional[NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.adapters: Dict[str, BrokerAdapter] = {}
        self.orders: Dict[str, Order] = {}
        self.order_broker_mapping: Dict[str, str] = {}  # order_id -> broker_name
        self.reconciliation_running = False

    async def connect_nats(self):
        """Connect to NATS JetStream."""
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        try:
            self.nats_client = await nats.connect(nats_url)
            self.js = self.nats_client.jetstream()
            logger.info("Connected to NATS", url=nats_url)

            # Subscribe to meta decisions
            await self.js.subscribe(
                "decisions.meta",
                cb=self._handle_meta_decision,
                durable="broker-adapter-decisions",
                queue="broker-adapter"
            )

        except Exception as e:
            logger.error("Failed to connect to NATS", error=str(e))
            raise

    async def add_broker(self, config: BrokerConfig):
        """Add a broker adapter."""
        try:
            if config.broker_type == BrokerType.PAPER:
                adapter = PaperTradingAdapter(config.config)
            elif config.broker_type == BrokerType.INTERACTIVE_BROKERS:
                adapter = InteractiveBrokersAdapter(config.config)
            elif config.broker_type == BrokerType.ALPACA:
                adapter = AlpacaAdapter(config.config)
            else:
                raise ValueError(f"Unknown broker type: {config.broker_type}")

            # Connect to broker
            connected = await adapter.connect()
            if not connected:
                raise BrokerError(f"Failed to connect to {config.name}")

            self.adapters[config.name] = adapter
            active_connections.labels(broker=config.name).set(1)

            logger.info("Broker adapter added", name=config.name, type=config.broker_type.value)

        except Exception as e:
            logger.error("Failed to add broker adapter", name=config.name, error=str(e))
            raise

    async def remove_broker(self, name: str):
        """Remove a broker adapter."""
        if name in self.adapters:
            await self.adapters[name].disconnect()
            del self.adapters[name]
            active_connections.labels(broker=name).set(0)
            logger.info("Broker adapter removed", name=name)

    async def _handle_meta_decision(self, msg):
        """Handle meta decisions from meta-agent."""
        try:
            data = json.loads(msg.data.decode())

            # Skip HOLD decisions
            if data.get("action") == "HOLD":
                await msg.ack()
                return

            # Create order from meta decision
            order = Order(
                id=str(uuid.uuid4()),
                symbol=data["symbol"],
                side=OrderSide.BUY if data["action"] == "BUY" else OrderSide.SELL,
                order_type=OrderType.MARKET,  # Default to market orders
                quantity=data["quantity"],
                client_order_id=data["correlation_id"]
            )

            # Submit order to primary broker
            await self.submit_order(order)

            await msg.ack()

        except Exception as e:
            logger.error("Error handling meta decision", error=str(e))
            await msg.nak()

    async def submit_order(self, order: Order, broker_name: Optional[str] = None) -> Order:
        """Submit order to specified broker or primary broker."""
        if not self.adapters:
            raise BrokerError("No broker adapters available")

        # Choose broker
        if broker_name:
            if broker_name not in self.adapters:
                raise BrokerError(f"Broker {broker_name} not found")
            adapter = self.adapters[broker_name]
        else:
            # Use first available broker (in production, would have better logic)
            broker_name = list(self.adapters.keys())[0]
            adapter = self.adapters[broker_name]

        try:
            with order_latency.labels(broker=broker_name).time():
                # Submit to broker
                updated_order = await adapter.submit_order(order)

                # Store order and mapping
                self.orders[order.id] = updated_order
                self.order_broker_mapping[order.id] = broker_name

                orders_submitted.labels(broker=broker_name, symbol=order.symbol).inc()

                # Publish order event
                await self._publish_order_event(updated_order, "submitted")

                logger.info("Order submitted",
                           order_id=order.id,
                           broker=broker_name,
                           symbol=order.symbol,
                           action=order.side.value,
                           quantity=order.quantity)

                return updated_order

        except Exception as e:
            orders_rejected.labels(broker=broker_name, reason=str(e)[:50]).inc()
            logger.error("Order submission failed",
                        order_id=order.id,
                        broker=broker_name,
                        error=str(e))
            raise

    async def cancel_order(self, order_id: str) -> Order:
        """Cancel an order."""
        if order_id not in self.order_broker_mapping:
            raise BrokerError(f"Order {order_id} not found")

        broker_name = self.order_broker_mapping[order_id]
        adapter = self.adapters[broker_name]

        try:
            updated_order = await adapter.cancel_order(order_id)
            self.orders[order_id] = updated_order

            await self._publish_order_event(updated_order, "cancelled")

            logger.info("Order cancelled", order_id=order_id, broker=broker_name)
            return updated_order

        except Exception as e:
            logger.error("Order cancellation failed", order_id=order_id, error=str(e))
            raise

    async def get_order(self, order_id: str) -> Order:
        """Get order status."""
        if order_id not in self.order_broker_mapping:
            raise BrokerError(f"Order {order_id} not found")

        broker_name = self.order_broker_mapping[order_id]
        adapter = self.adapters[broker_name]

        try:
            order = await adapter.get_order(order_id)
            self.orders[order_id] = order
            return order

        except Exception as e:
            logger.error("Failed to get order", order_id=order_id, error=str(e))
            raise

    async def get_orders(self, broker_name: Optional[str] = None, symbol: Optional[str] = None) -> List[Order]:
        """Get orders from specified broker or all brokers."""
        orders = []

        if broker_name:
            if broker_name not in self.adapters:
                raise BrokerError(f"Broker {broker_name} not found")
            adapter = self.adapters[broker_name]
            broker_orders = await adapter.get_orders(symbol)
            orders.extend(broker_orders)
        else:
            # Get from all brokers
            for name, adapter in self.adapters.items():
                try:
                    broker_orders = await adapter.get_orders(symbol)
                    orders.extend(broker_orders)
                except Exception as e:
                    logger.warning("Failed to get orders from broker", broker=name, error=str(e))

        return orders

    async def get_positions(self, broker_name: Optional[str] = None) -> List[Position]:
        """Get positions from specified broker or all brokers."""
        positions = []

        if broker_name:
            if broker_name not in self.adapters:
                raise BrokerError(f"Broker {broker_name} not found")
            adapter = self.adapters[broker_name]
            broker_positions = await adapter.get_positions()
            positions.extend(broker_positions)
        else:
            # Get from all brokers
            for name, adapter in self.adapters.items():
                try:
                    broker_positions = await adapter.get_positions()
                    positions.extend(broker_positions)
                except Exception as e:
                    logger.warning("Failed to get positions from broker", broker=name, error=str(e))

        return positions

    async def get_account(self, broker_name: str) -> Account:
        """Get account information from specified broker."""
        if broker_name not in self.adapters:
            raise BrokerError(f"Broker {broker_name} not found")

        adapter = self.adapters[broker_name]
        return await adapter.get_account()

    async def _publish_order_event(self, order: Order, event_type: str):
        """Publish order event to NATS."""
        try:
            if not self.js:
                return

            event_data = {
                "event_type": event_type,
                "order_id": order.id,
                "symbol": order.symbol,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "quantity": order.quantity,
                "price": order.price,
                "status": order.status.value,
                "broker_order_id": order.broker_order_id,
                "timestamp": datetime.utcnow().isoformat(),
                "broker": self.order_broker_mapping.get(order.id)
            }

            await self.js.publish(
                "executions.order_update",
                json.dumps(event_data).encode()
            )

        except Exception as e:
            logger.error("Failed to publish order event", error=str(e))

    async def start_reconciliation(self):
        """Start order reconciliation process."""
        if self.reconciliation_running:
            return

        self.reconciliation_running = True
        asyncio.create_task(self._reconciliation_loop())

    async def _reconciliation_loop(self):
        """Periodic order reconciliation with brokers."""
        while self.reconciliation_running:
            try:
                await self._reconcile_orders()
                await asyncio.sleep(30)  # Reconcile every 30 seconds
            except Exception as e:
                logger.error("Reconciliation error", error=str(e))
                reconciliation_errors.labels(broker="all").inc()

    async def _reconcile_orders(self):
        """Reconcile order states with brokers."""
        for order_id, broker_name in self.order_broker_mapping.items():
            try:
                if broker_name not in self.adapters:
                    continue

                adapter = self.adapters[broker_name]
                broker_order = await adapter.get_order(order_id)

                # Check for status changes
                local_order = self.orders.get(order_id)
                if local_order and local_order.status != broker_order.status:
                    logger.info("Order status reconciled",
                               order_id=order_id,
                               old_status=local_order.status.value,
                               new_status=broker_order.status.value)

                    self.orders[order_id] = broker_order

                    # Check for fills
                    if broker_order.status == OrderStatus.FILLED:
                        orders_filled.labels(broker=broker_name, symbol=broker_order.symbol).inc()
                        await self._publish_order_event(broker_order, "filled")

            except Exception as e:
                logger.warning("Failed to reconcile order", order_id=order_id, error=str(e))
                reconciliation_errors.labels(broker=broker_name).inc()

# FastAPI app
app = FastAPI(title="Broker Adapter Service", version="0.1.0")
broker_service = BrokerAdapterService()

@app.on_event("startup")
async def startup():
    """Initialize service on startup."""
    await broker_service.connect_nats()

    # Add default paper trading adapter
    paper_config = BrokerConfig(
        broker_type=BrokerType.PAPER,
        name="paper",
        config={
            "initial_balance": 100000.0,
            "commission": 1.0,
            "slippage": 0.001,
            "dry_run": True
        },
        enabled=True,
        primary=True
    )
    await broker_service.add_broker(paper_config)

    # Start reconciliation
    await broker_service.start_reconciliation()

@app.on_event("shutdown")
async def shutdown():
    """Clean shutdown."""
    broker_service.reconciliation_running = False

    for adapter in broker_service.adapters.values():
        await adapter.disconnect()

    if broker_service.nats_client:
        await broker_service.nats_client.close()

@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "broker-adapter",
        "timestamp": datetime.utcnow().isoformat(),
        "nats_connected": broker_service.nats_client is not None,
        "active_brokers": list(broker_service.adapters.keys()),
        "total_orders": len(broker_service.orders)
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type="text/plain")

@app.post("/brokers")
async def add_broker(
    broker_type: str,
    name: str,
    config: Dict[str, Any],
    enabled: bool = True,
    primary: bool = False
):
    """Add a new broker adapter."""
    try:
        broker_config = BrokerConfig(
            broker_type=BrokerType(broker_type),
            name=name,
            config=config,
            enabled=enabled,
            primary=primary
        )
        await broker_service.add_broker(broker_config)
        return {"status": "added", "broker": name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/brokers/{name}")
async def remove_broker(name: str):
    """Remove a broker adapter."""
    try:
        await broker_service.remove_broker(name)
        return {"status": "removed", "broker": name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/brokers")
async def list_brokers():
    """List active broker adapters."""
    return {
        "brokers": [
            {
                "name": name,
                "connected": adapter.is_connected,
                "dry_run": adapter.dry_run
            }
            for name, adapter in broker_service.adapters.items()
        ]
    }

@app.post("/orders")
async def submit_order(
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market",
    price: Optional[float] = None,
    broker: Optional[str] = None
):
    """Submit a new order."""
    try:
        order = Order(
            id=str(uuid.uuid4()),
            symbol=symbol.upper(),
            side=OrderSide(side.lower()),
            order_type=OrderType(order_type.lower()),
            quantity=quantity,
            price=price
        )

        submitted_order = await broker_service.submit_order(order, broker)
        return asdict(submitted_order)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an order."""
    try:
        cancelled_order = await broker_service.cancel_order(order_id)
        return asdict(cancelled_order)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get order details."""
    try:
        order = await broker_service.get_order(order_id)
        return asdict(order)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/orders")
async def list_orders(broker: Optional[str] = None, symbol: Optional[str] = None):
    """List orders."""
    try:
        orders = await broker_service.get_orders(broker, symbol)
        return {"orders": [asdict(order) for order in orders]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/positions")
async def list_positions(broker: Optional[str] = None):
    """List positions."""
    try:
        positions = await broker_service.get_positions(broker)
        return {"positions": [asdict(pos) for pos in positions]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/account/{broker}")
async def get_account(broker: str):
    """Get account information."""
    try:
        account = await broker_service.get_account(broker)
        return asdict(account)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
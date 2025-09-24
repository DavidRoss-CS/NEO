"""
Paper trading adapter - internal sandbox for testing without real money.
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import random

from ..base_adapter import BrokerAdapter, BrokerError, OrderError, InsufficientFundsError
from ..models import Order, Fill, Position, Account, OrderStatus, OrderSide

class PaperTradingAdapter(BrokerAdapter):
    """Paper trading adapter for risk-free testing."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.initial_balance = config.get("initial_balance", 100000.0)
        self.commission = config.get("commission", 1.0)  # $1 per trade
        self.slippage = config.get("slippage", 0.001)  # 0.1% slippage

        # Internal state
        self.orders: Dict[str, Order] = {}
        self.fills: Dict[str, Fill] = {}
        self.positions: Dict[str, Position] = {}
        self.cash_balance = self.initial_balance
        self.realized_pnl = 0.0

        # Mock market data
        self.market_data = {
            "AAPL": {"price": 150.0, "bid": 149.95, "ask": 150.05, "volume": 1000000},
            "MSFT": {"price": 300.0, "bid": 299.90, "ask": 300.10, "volume": 800000},
            "GOOGL": {"price": 2500.0, "bid": 2499.50, "ask": 2500.50, "volume": 500000},
            "TSLA": {"price": 800.0, "bid": 799.60, "ask": 800.40, "volume": 2000000},
            "NVDA": {"price": 400.0, "bid": 399.80, "ask": 400.20, "volume": 1500000},
        }

    async def connect(self) -> bool:
        """Connect to paper trading (always succeeds)."""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self.is_connected = True
        return True

    async def disconnect(self):
        """Disconnect from paper trading."""
        self.is_connected = False

    async def submit_order(self, order: Order) -> Order:
        """Submit order for paper trading execution."""
        if not self.is_connected:
            raise BrokerError("Not connected to broker")

        # Generate broker order ID
        order.broker_order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
        order.status = OrderStatus.SUBMITTED
        order.updated_at = datetime.utcnow()

        # Store order
        self.orders[order.id] = order

        # Simulate order processing in background
        asyncio.create_task(self._process_order(order))

        return order

    async def _process_order(self, order: Order):
        """Simulate order execution with realistic delays and fills."""
        await asyncio.sleep(random.uniform(0.1, 2.0))  # Random execution delay

        try:
            # Check if symbol exists in our market data
            if order.symbol not in self.market_data:
                order.status = OrderStatus.REJECTED
                order.updated_at = datetime.utcnow()
                return

            market_price = self.market_data[order.symbol]["price"]

            # Apply slippage
            if order.side == OrderSide.BUY:
                execution_price = market_price * (1 + self.slippage)
            else:
                execution_price = market_price * (1 - self.slippage)

            # Check limit price constraints
            if order.order_type.value == "limit":
                if order.side == OrderSide.BUY and execution_price > order.price:
                    # Limit buy order - price too high, order stays pending
                    return
                elif order.side == OrderSide.SELL and execution_price < order.price:
                    # Limit sell order - price too low, order stays pending
                    return
                execution_price = order.price  # Execute at limit price

            # Check available funds/shares
            total_cost = order.quantity * execution_price + self.commission

            if order.side == OrderSide.BUY:
                if total_cost > self.cash_balance:
                    order.status = OrderStatus.REJECTED
                    order.updated_at = datetime.utcnow()
                    order.metadata = {"reject_reason": "Insufficient funds"}
                    return
            else:  # SELL
                current_position = self.positions.get(order.symbol)
                if not current_position or current_position.quantity < order.quantity:
                    order.status = OrderStatus.REJECTED
                    order.updated_at = datetime.utcnow()
                    order.metadata = {"reject_reason": "Insufficient shares"}
                    return

            # Execute the order
            fill = Fill(
                id=str(uuid.uuid4()),
                order_id=order.id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=execution_price,
                timestamp=datetime.utcnow(),
                commission=self.commission,
                broker_fill_id=f"FILL_{uuid.uuid4().hex[:8]}"
            )

            # Update order
            order.filled_quantity = order.quantity
            order.remaining_quantity = 0
            order.average_fill_price = execution_price
            order.status = OrderStatus.FILLED
            order.updated_at = datetime.utcnow()

            # Store fill
            self.fills[fill.id] = fill

            # Update positions and cash
            self._update_position(fill)
            self._update_cash_balance(fill)

        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.updated_at = datetime.utcnow()
            order.metadata = {"reject_reason": str(e)}

    def _update_position(self, fill: Fill):
        """Update position based on fill."""
        symbol = fill.symbol

        if symbol not in self.positions:
            # New position
            if fill.side == OrderSide.BUY:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=fill.quantity,
                    average_price=fill.price,
                    market_value=fill.quantity * fill.price,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0,
                    updated_at=fill.timestamp
                )
            # Can't sell if no position exists (should be caught earlier)
            return

        position = self.positions[symbol]

        if fill.side == OrderSide.BUY:
            # Add to position
            total_cost = (position.quantity * position.average_price) + (fill.quantity * fill.price)
            position.quantity += fill.quantity
            position.average_price = total_cost / position.quantity
        else:
            # Reduce position (sell)
            # Calculate realized P&L
            realized_pnl = (fill.price - position.average_price) * fill.quantity
            self.realized_pnl += realized_pnl
            position.realized_pnl += realized_pnl

            position.quantity -= fill.quantity

            # Remove position if fully closed
            if position.quantity <= 0:
                del self.positions[symbol]
                return

        # Update market value and unrealized P&L
        current_price = self.market_data.get(symbol, {}).get("price", fill.price)
        position.market_value = position.quantity * current_price
        position.unrealized_pnl = (current_price - position.average_price) * position.quantity
        position.updated_at = fill.timestamp

    def _update_cash_balance(self, fill: Fill):
        """Update cash balance based on fill."""
        if fill.side == OrderSide.BUY:
            # Spent cash
            self.cash_balance -= (fill.quantity * fill.price + fill.commission)
        else:
            # Received cash
            self.cash_balance += (fill.quantity * fill.price - fill.commission)

    async def cancel_order(self, order_id: str) -> Order:
        """Cancel an order."""
        if order_id not in self.orders:
            raise OrderError(f"Order {order_id} not found")

        order = self.orders[order_id]

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            raise OrderError(f"Cannot cancel order in status {order.status.value}")

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.utcnow()
        return order

    async def get_order(self, order_id: str) -> Order:
        """Get order by ID."""
        if order_id not in self.orders:
            raise OrderError(f"Order {order_id} not found")
        return self.orders[order_id]

    async def get_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all orders, optionally filtered by symbol."""
        orders = list(self.orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return sorted(orders, key=lambda x: x.created_at, reverse=True)

    async def get_fills(self, order_id: Optional[str] = None) -> List[Fill]:
        """Get all fills, optionally filtered by order ID."""
        fills = list(self.fills.values())
        if order_id:
            fills = [f for f in fills if f.order_id == order_id]
        return sorted(fills, key=lambda x: x.timestamp, reverse=True)

    async def get_positions(self) -> List[Position]:
        """Get current positions."""
        # Update unrealized P&L with current market prices
        for position in self.positions.values():
            current_price = self.market_data.get(position.symbol, {}).get("price", position.average_price)
            position.market_value = position.quantity * current_price
            position.unrealized_pnl = (current_price - position.average_price) * position.quantity
            position.updated_at = datetime.utcnow()

        return list(self.positions.values())

    async def get_account(self) -> Account:
        """Get account information."""
        positions = await self.get_positions()
        total_market_value = sum(p.market_value for p in positions)
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)

        return Account(
            account_id="PAPER_ACCOUNT",
            cash_balance=self.cash_balance,
            buying_power=self.cash_balance,  # Simplified - no margin
            total_value=self.cash_balance + total_market_value,
            unrealized_pnl=total_unrealized_pnl,
            realized_pnl=self.realized_pnl,
            updated_at=datetime.utcnow(),
            metadata={
                "initial_balance": self.initial_balance,
                "commission_rate": self.commission,
                "slippage_rate": self.slippage
            }
        )

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for symbol."""
        if symbol not in self.market_data:
            raise BrokerError(f"Market data not available for {symbol}")

        # Add some random movement to simulate live prices
        data = self.market_data[symbol].copy()
        price_change = random.gauss(0, data["price"] * 0.001)  # 0.1% volatility
        data["price"] = max(0.01, data["price"] + price_change)
        data["bid"] = data["price"] - 0.05
        data["ask"] = data["price"] + 0.05
        data["timestamp"] = datetime.utcnow().isoformat()

        return data

    async def simulate_market_movement(self):
        """Simulate market price movements for testing."""
        while self.is_connected:
            for symbol, data in self.market_data.items():
                # Random price movement
                change_pct = random.gauss(0, 0.02)  # 2% volatility
                new_price = max(1.0, data["price"] * (1 + change_pct))
                data["price"] = round(new_price, 2)
                data["bid"] = round(new_price * 0.999, 2)
                data["ask"] = round(new_price * 1.001, 2)

            await asyncio.sleep(1)  # Update every second
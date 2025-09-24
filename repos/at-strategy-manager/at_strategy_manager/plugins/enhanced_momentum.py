"""
Enhanced Momentum Strategy Plugin

This is an example strategy that demonstrates the plugin interface.
It implements a momentum strategy with RSI filtering and position sizing.
"""

import asyncio
from typing import Dict, List, Optional, Any
from collections import deque
from datetime import datetime, timedelta
import math

from ..strategy_interface import (
    IStrategy, StrategyConfig, MarketSignal, StrategyDecision,
    DecisionType, StrategyStatus, StrategyPosition, StrategyPerformance
)

# Plugin metadata (required for plugin system)
__plugin_name__ = "enhanced_momentum"
__version__ = "1.2.0"
__author__ = "Trading Team"
__description__ = "Enhanced momentum strategy with RSI filtering and dynamic position sizing"
__dependencies__ = []
__entry_point__ = "EnhancedMomentumStrategy"
__config_schema__ = {
    "momentum_window": {"type": "integer", "default": 20, "min": 5, "max": 100},
    "rsi_window": {"type": "integer", "default": 14, "min": 5, "max": 50},
    "rsi_oversold": {"type": "number", "default": 30, "min": 10, "max": 40},
    "rsi_overbought": {"type": "number", "default": 70, "min": 60, "max": 90},
    "position_size": {"type": "number", "default": 1000, "min": 100, "max": 10000},
    "max_positions": {"type": "integer", "default": 5, "min": 1, "max": 20},
    "stop_loss_pct": {"type": "number", "default": 0.02, "min": 0.005, "max": 0.1}
}

class PriceBuffer:
    """Rolling buffer for price data."""

    def __init__(self, window_size: int):
        self.window_size = window_size
        self.prices = deque(maxlen=window_size)
        self.timestamps = deque(maxlen=window_size)

    def add(self, price: float, timestamp: datetime):
        self.prices.append(price)
        self.timestamps.append(timestamp)

    def is_full(self) -> bool:
        return len(self.prices) == self.window_size

    def get_returns(self) -> List[float]:
        if len(self.prices) < 2:
            return []

        returns = []
        for i in range(1, len(self.prices)):
            returns.append((self.prices[i] - self.prices[i-1]) / self.prices[i-1])
        return returns

    def get_momentum(self) -> float:
        if not self.is_full():
            return 0.0

        return (self.prices[-1] - self.prices[0]) / self.prices[0]

    def calculate_rsi(self, window: int) -> float:
        """Calculate RSI using the price buffer."""
        if len(self.prices) < window + 1:
            return 50.0  # Neutral RSI

        gains = []
        losses = []

        for i in range(-window, 0):
            change = self.prices[i] - self.prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

class EnhancedMomentumStrategy(IStrategy):
    """Enhanced momentum strategy with RSI filtering."""

    def __init__(self, config: StrategyConfig):
        super().__init__(config)

        # Strategy parameters
        self.momentum_window = config.parameters.get("momentum_window", 20)
        self.rsi_window = config.parameters.get("rsi_window", 14)
        self.rsi_oversold = config.parameters.get("rsi_oversold", 30)
        self.rsi_overbought = config.parameters.get("rsi_overbought", 70)
        self.position_size = config.parameters.get("position_size", 1000)
        self.max_positions = config.parameters.get("max_positions", 5)
        self.stop_loss_pct = config.parameters.get("stop_loss_pct", 0.02)

        # Price buffers for each symbol
        self.price_buffers: Dict[str, PriceBuffer] = {}

        # Strategy state
        self.last_decisions: Dict[str, StrategyDecision] = {}
        self.trade_count = 0
        self.winning_trades = 0

        # Risk management
        self.stop_losses: Dict[str, float] = {}  # symbol -> stop loss price

    async def initialize(self) -> bool:
        """Initialize strategy."""
        try:
            # Validate configuration
            if self.momentum_window < 5 or self.momentum_window > 100:
                raise ValueError("Invalid momentum_window")

            if self.rsi_window < 5 or self.rsi_window > 50:
                raise ValueError("Invalid rsi_window")

            if not (10 <= self.rsi_oversold <= 40):
                raise ValueError("Invalid rsi_oversold")

            if not (60 <= self.rsi_overbought <= 90):
                raise ValueError("Invalid rsi_overbought")

            self.status = StrategyStatus.INACTIVE
            return True

        except Exception as e:
            self.status = StrategyStatus.ERROR
            return False

    async def on_signal(self, signal: MarketSignal) -> Optional[StrategyDecision]:
        """Process market signal and generate trading decision."""
        try:
            symbol = signal.symbol

            # Initialize price buffer if needed
            if symbol not in self.price_buffers:
                buffer_size = max(self.momentum_window, self.rsi_window) + 10
                self.price_buffers[symbol] = PriceBuffer(buffer_size)

            buffer = self.price_buffers[symbol]
            buffer.add(signal.price, signal.timestamp)

            # Need enough data for calculations
            if not buffer.is_full():
                return None

            # Calculate indicators
            momentum = buffer.get_momentum()
            rsi = buffer.calculate_rsi(self.rsi_window)

            # Check position count limit
            if len(self.positions) >= self.max_positions:
                # Only allow sells if at position limit
                if symbol not in self.positions:
                    return None

            # Generate decision based on strategy logic
            decision = self._generate_decision(symbol, signal.price, momentum, rsi)

            if decision:
                self.last_decisions[symbol] = decision

                # Set stop loss for buy decisions
                if decision.decision == DecisionType.BUY:
                    self.stop_losses[symbol] = signal.price * (1 - self.stop_loss_pct)

            return decision

        except Exception as e:
            return None

    def _generate_decision(self, symbol: str, price: float, momentum: float, rsi: float) -> Optional[StrategyDecision]:
        """Generate trading decision based on momentum and RSI."""

        current_position = self.positions.get(symbol)

        # Check stop loss if we have a position
        if current_position and current_position.quantity > 0:
            stop_price = self.stop_losses.get(symbol)
            if stop_price and price <= stop_price:
                return StrategyDecision(
                    symbol=symbol,
                    decision=DecisionType.SELL,
                    quantity=current_position.quantity,
                    confidence=0.9,
                    reasoning=f"Stop loss triggered at {price:.2f}"
                )

        # Entry signals
        if not current_position or current_position.quantity == 0:
            # Strong momentum + oversold RSI = Buy
            if momentum > 0.02 and rsi < self.rsi_oversold:
                confidence = min(0.95, 0.5 + abs(momentum) * 10 + (self.rsi_oversold - rsi) / 100)

                return StrategyDecision(
                    symbol=symbol,
                    decision=DecisionType.BUY,
                    quantity=self._calculate_position_size(price),
                    confidence=confidence,
                    reasoning=f"Momentum: {momentum:.3f}, RSI: {rsi:.1f} (oversold)"
                )

        # Exit signals
        else:
            # Negative momentum + overbought RSI = Sell
            if momentum < -0.01 and rsi > self.rsi_overbought:
                confidence = min(0.95, 0.5 + abs(momentum) * 10 + (rsi - self.rsi_overbought) / 100)

                return StrategyDecision(
                    symbol=symbol,
                    decision=DecisionType.SELL,
                    quantity=current_position.quantity,
                    confidence=confidence,
                    reasoning=f"Momentum: {momentum:.3f}, RSI: {rsi:.1f} (overbought)"
                )

        return None

    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size based on price and available capital."""
        # Simple position sizing - in production would consider portfolio value
        shares = self.position_size / price
        return max(1, int(shares))  # At least 1 share

    async def on_fill(self, symbol: str, quantity: float, price: float, commission: float):
        """Handle order fill notification."""
        try:
            # Update position tracking
            self.update_position(symbol, quantity, price)

            # Update trade statistics
            self.trade_count += 1

            # Calculate if this was a winning trade (simplified)
            if quantity < 0:  # Sell
                position = self.positions.get(symbol)
                if position and position.realized_pnl > 0:
                    self.winning_trades += 1

            # Update performance metrics
            self.performance.total_trades = self.trade_count
            self.performance.win_rate = self.winning_trades / self.trade_count if self.trade_count > 0 else 0
            self.performance.active_positions = len(self.positions)

            # Clean up stop loss if position closed
            if symbol in self.positions and self.positions[symbol].quantity == 0:
                self.stop_losses.pop(symbol, None)

        except Exception as e:
            pass  # Log error in production

    async def get_health_status(self) -> Dict[str, Any]:
        """Return strategy health and diagnostic information."""
        return {
            "status": self.status.value,
            "active_symbols": len(self.price_buffers),
            "positions_count": len(self.positions),
            "trade_count": self.trade_count,
            "win_rate": self.performance.win_rate,
            "parameters": {
                "momentum_window": self.momentum_window,
                "rsi_window": self.rsi_window,
                "position_size": self.position_size,
                "max_positions": self.max_positions
            },
            "buffers_ready": sum(1 for buf in self.price_buffers.values() if buf.is_full()),
            "last_update": datetime.utcnow().isoformat()
        }

    async def cleanup(self):
        """Clean up strategy resources."""
        try:
            self.price_buffers.clear()
            self.last_decisions.clear()
            self.stop_losses.clear()
            self.status = StrategyStatus.INACTIVE
        except Exception:
            pass
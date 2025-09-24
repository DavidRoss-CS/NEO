"""
Portfolio risk engine for global risk management.

Responsibilities:
- Real-time position and exposure tracking
- Risk rules enforcement
- Emergency controls
- Risk violation detection and reporting
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

import structlog
from prometheus_client import Counter, Gauge, Histogram

logger = structlog.get_logger()

# Prometheus metrics
risk_violations = Counter('risk_violations_total', 'Total risk violations detected', ['violation_type'])
position_value = Gauge('risk_position_value', 'Current position value by symbol', ['symbol'])
total_exposure = Gauge('risk_total_exposure', 'Total portfolio exposure')
daily_loss = Gauge('risk_daily_loss', 'Daily loss amount')
emergency_stops = Counter('risk_emergency_stops_total', 'Emergency stops triggered')
blocked_orders = Counter('risk_blocked_orders_total', 'Orders blocked by risk engine')

class RiskViolationType(Enum):
    MAX_DAILY_LOSS = "max_daily_loss"
    POSITION_LIMIT = "position_limit"
    CORRELATION_LIMIT = "correlation_limit"
    CONCENTRATION_RISK = "concentration_risk"
    VELOCITY_LIMIT = "velocity_limit"
    EXPOSURE_LIMIT = "exposure_limit"

@dataclass
class Position:
    symbol: str
    quantity: float
    average_price: float
    current_price: float
    timestamp: datetime
    correlation_bucket: str

    @property
    def value(self) -> float:
        return self.quantity * self.current_price

    @property
    def pnl(self) -> float:
        return (self.current_price - self.average_price) * self.quantity

    @property
    def pnl_percent(self) -> float:
        if self.average_price == 0:
            return 0
        return (self.current_price - self.average_price) / self.average_price * 100

@dataclass
class RiskLimits:
    max_daily_loss: float = 10000.0  # Max daily loss in USD
    max_position_value: float = 50000.0  # Max position value per symbol
    max_total_exposure: float = 200000.0  # Max total portfolio exposure
    max_concentration: float = 0.3  # Max 30% in single position
    max_correlated_exposure: float = 100000.0  # Max exposure per correlation bucket
    max_order_velocity: int = 100  # Max orders per minute
    position_limit_per_symbol: int = 1000  # Max shares per symbol

@dataclass
class RiskViolation:
    violation_type: RiskViolationType
    symbol: Optional[str]
    message: str
    severity: str  # "warning", "critical", "emergency"
    timestamp: datetime
    metadata: Dict

class PortfolioRiskEngine:
    def __init__(self, risk_limits: Optional[RiskLimits] = None):
        self.risk_limits = risk_limits or RiskLimits()
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.daily_start_value = 0.0
        self.order_count = defaultdict(int)  # Orders per minute tracking
        self.violations: List[RiskViolation] = []
        self.kill_switch_active = False
        self.blocked_symbols: Set[str] = set()
        self.correlation_buckets = {
            "tech": ["AAPL", "MSFT", "GOOGL", "META", "NVDA"],
            "finance": ["JPM", "BAC", "GS", "MS", "WFC"],
            "energy": ["XOM", "CVX", "COP", "SLB", "OXY"],
            "consumer": ["AMZN", "TSLA", "WMT", "HD", "NKE"]
        }

    def get_correlation_bucket(self, symbol: str) -> str:
        """Get correlation bucket for a symbol."""
        for bucket, symbols in self.correlation_buckets.items():
            if symbol in symbols:
                return bucket
        return "other"

    async def update_position(self, symbol: str, quantity_change: float, price: float):
        """Update position with new trade."""
        if symbol not in self.positions:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity_change,
                average_price=price,
                current_price=price,
                timestamp=datetime.utcnow(),
                correlation_bucket=self.get_correlation_bucket(symbol)
            )
        else:
            position = self.positions[symbol]
            new_quantity = position.quantity + quantity_change

            if new_quantity == 0:
                # Position closed
                del self.positions[symbol]
            else:
                # Update average price on buy
                if quantity_change > 0:
                    total_value = (position.quantity * position.average_price) + (quantity_change * price)
                    position.average_price = total_value / new_quantity

                position.quantity = new_quantity
                position.current_price = price
                position.timestamp = datetime.utcnow()

        # Update metrics
        if symbol in self.positions:
            position_value.labels(symbol=symbol).set(self.positions[symbol].value)

        self._update_exposure_metrics()

    async def update_market_prices(self, prices: Dict[str, float]):
        """Update current market prices for positions."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price

        self._update_exposure_metrics()
        await self._check_risk_limits()

    def _update_exposure_metrics(self):
        """Update exposure metrics."""
        total = sum(pos.value for pos in self.positions.values())
        total_exposure.set(total)

        # Calculate daily PnL
        current_value = sum(pos.value for pos in self.positions.values())
        self.daily_pnl = current_value - self.daily_start_value
        daily_loss.set(abs(min(0, self.daily_pnl)))

    async def check_order_risk(self, symbol: str, action: str, quantity: float, price: float) -> tuple[bool, Optional[RiskViolation]]:
        """Check if an order violates risk limits."""
        if self.kill_switch_active:
            violation = RiskViolation(
                violation_type=RiskViolationType.EXPOSURE_LIMIT,
                symbol=symbol,
                message="Kill switch is active - all trading halted",
                severity="emergency",
                timestamp=datetime.utcnow(),
                metadata={"action": action, "quantity": quantity}
            )
            blocked_orders.inc()
            return False, violation

        if symbol in self.blocked_symbols:
            violation = RiskViolation(
                violation_type=RiskViolationType.POSITION_LIMIT,
                symbol=symbol,
                message=f"Symbol {symbol} is blocked",
                severity="critical",
                timestamp=datetime.utcnow(),
                metadata={"action": action, "quantity": quantity}
            )
            blocked_orders.inc()
            return False, violation

        # Check daily loss limit
        if self.daily_pnl < -self.risk_limits.max_daily_loss:
            violation = RiskViolation(
                violation_type=RiskViolationType.MAX_DAILY_LOSS,
                symbol=symbol,
                message=f"Daily loss limit exceeded: ${abs(self.daily_pnl):.2f}",
                severity="critical",
                timestamp=datetime.utcnow(),
                metadata={"daily_loss": self.daily_pnl, "limit": self.risk_limits.max_daily_loss}
            )
            risk_violations.labels(violation_type="max_daily_loss").inc()
            blocked_orders.inc()
            return False, violation

        # Calculate position after order
        current_position = self.positions.get(symbol)
        if action == "BUY":
            new_quantity = (current_position.quantity if current_position else 0) + quantity
            new_value = new_quantity * price
        elif action == "SELL":
            new_quantity = (current_position.quantity if current_position else 0) - quantity
            new_value = abs(new_quantity * price)
        else:  # HOLD
            return True, None

        # Check position limits
        if new_value > self.risk_limits.max_position_value:
            violation = RiskViolation(
                violation_type=RiskViolationType.POSITION_LIMIT,
                symbol=symbol,
                message=f"Position value ${new_value:.2f} exceeds limit ${self.risk_limits.max_position_value:.2f}",
                severity="warning",
                timestamp=datetime.utcnow(),
                metadata={"new_value": new_value, "limit": self.risk_limits.max_position_value}
            )
            risk_violations.labels(violation_type="position_limit").inc()
            blocked_orders.inc()
            return False, violation

        # Check total exposure
        current_total = sum(pos.value for pos in self.positions.values())
        new_total = current_total + (new_value - (current_position.value if current_position else 0))

        if new_total > self.risk_limits.max_total_exposure:
            violation = RiskViolation(
                violation_type=RiskViolationType.EXPOSURE_LIMIT,
                symbol=symbol,
                message=f"Total exposure ${new_total:.2f} would exceed limit ${self.risk_limits.max_total_exposure:.2f}",
                severity="warning",
                timestamp=datetime.utcnow(),
                metadata={"new_total": new_total, "limit": self.risk_limits.max_total_exposure}
            )
            risk_violations.labels(violation_type="exposure_limit").inc()
            blocked_orders.inc()
            return False, violation

        # Check concentration risk
        if current_total > 0:
            concentration = new_value / new_total
            if concentration > self.risk_limits.max_concentration:
                violation = RiskViolation(
                    violation_type=RiskViolationType.CONCENTRATION_RISK,
                    symbol=symbol,
                    message=f"Position concentration {concentration:.1%} exceeds limit {self.risk_limits.max_concentration:.1%}",
                    severity="warning",
                    timestamp=datetime.utcnow(),
                    metadata={"concentration": concentration, "limit": self.risk_limits.max_concentration}
                )
                risk_violations.labels(violation_type="concentration_risk").inc()
                blocked_orders.inc()
                return False, violation

        # Check correlation bucket limits
        bucket = self.get_correlation_bucket(symbol)
        bucket_exposure = sum(
            pos.value for pos in self.positions.values()
            if pos.correlation_bucket == bucket
        )
        new_bucket_exposure = bucket_exposure + (new_value - (current_position.value if current_position else 0))

        if new_bucket_exposure > self.risk_limits.max_correlated_exposure:
            violation = RiskViolation(
                violation_type=RiskViolationType.CORRELATION_LIMIT,
                symbol=symbol,
                message=f"Correlated exposure in {bucket} ${new_bucket_exposure:.2f} exceeds limit",
                severity="warning",
                timestamp=datetime.utcnow(),
                metadata={
                    "bucket": bucket,
                    "new_exposure": new_bucket_exposure,
                    "limit": self.risk_limits.max_correlated_exposure
                }
            )
            risk_violations.labels(violation_type="correlation_limit").inc()
            blocked_orders.inc()
            return False, violation

        # Check order velocity
        current_minute = datetime.utcnow().replace(second=0, microsecond=0)
        self.order_count[current_minute] += 1

        # Clean old entries
        cutoff = datetime.utcnow() - timedelta(minutes=2)
        self.order_count = {k: v for k, v in self.order_count.items() if k > cutoff}

        if self.order_count[current_minute] > self.risk_limits.max_order_velocity:
            violation = RiskViolation(
                violation_type=RiskViolationType.VELOCITY_LIMIT,
                symbol=symbol,
                message=f"Order velocity {self.order_count[current_minute]} exceeds limit",
                severity="warning",
                timestamp=datetime.utcnow(),
                metadata={
                    "order_count": self.order_count[current_minute],
                    "limit": self.risk_limits.max_order_velocity
                }
            )
            risk_violations.labels(violation_type="velocity_limit").inc()
            blocked_orders.inc()
            return False, violation

        return True, None

    async def _check_risk_limits(self):
        """Periodic check of risk limits."""
        violations = []

        # Check daily loss
        if self.daily_pnl < -self.risk_limits.max_daily_loss:
            violation = RiskViolation(
                violation_type=RiskViolationType.MAX_DAILY_LOSS,
                symbol=None,
                message=f"Daily loss ${abs(self.daily_pnl):.2f} exceeds limit",
                severity="critical",
                timestamp=datetime.utcnow(),
                metadata={"daily_loss": self.daily_pnl, "limit": self.risk_limits.max_daily_loss}
            )
            violations.append(violation)
            risk_violations.labels(violation_type="max_daily_loss").inc()

        # Check total exposure
        total = sum(pos.value for pos in self.positions.values())
        if total > self.risk_limits.max_total_exposure:
            violation = RiskViolation(
                violation_type=RiskViolationType.EXPOSURE_LIMIT,
                symbol=None,
                message=f"Total exposure ${total:.2f} exceeds limit",
                severity="critical",
                timestamp=datetime.utcnow(),
                metadata={"total_exposure": total, "limit": self.risk_limits.max_total_exposure}
            )
            violations.append(violation)
            risk_violations.labels(violation_type="exposure_limit").inc()

        # Store violations
        self.violations.extend(violations)

        # Trigger emergency stop if critical violations
        critical_violations = [v for v in violations if v.severity == "critical"]
        if len(critical_violations) >= 2:
            await self.emergency_stop("Multiple critical risk violations")

    async def emergency_stop(self, reason: str):
        """Activate emergency stop."""
        self.kill_switch_active = True
        emergency_stops.inc()
        logger.critical("Emergency stop activated", reason=reason)

        # Emit risk violation event
        violation = RiskViolation(
            violation_type=RiskViolationType.EXPOSURE_LIMIT,
            symbol=None,
            message=f"Emergency stop: {reason}",
            severity="emergency",
            timestamp=datetime.utcnow(),
            metadata={"reason": reason, "positions": len(self.positions)}
        )
        self.violations.append(violation)

    async def reset_daily_counters(self):
        """Reset daily counters (call at market open)."""
        self.daily_start_value = sum(pos.value for pos in self.positions.values())
        self.daily_pnl = 0.0
        self.order_count.clear()
        logger.info("Daily risk counters reset", start_value=self.daily_start_value)

    def get_risk_summary(self) -> Dict:
        """Get current risk summary."""
        total = sum(pos.value for pos in self.positions.values())
        bucket_exposures = defaultdict(float)

        for position in self.positions.values():
            bucket_exposures[position.correlation_bucket] += position.value

        return {
            "total_exposure": total,
            "daily_pnl": self.daily_pnl,
            "position_count": len(self.positions),
            "largest_position": max(self.positions.values(), key=lambda x: x.value).symbol if self.positions else None,
            "correlation_exposures": dict(bucket_exposures),
            "kill_switch_active": self.kill_switch_active,
            "blocked_symbols": list(self.blocked_symbols),
            "recent_violations": [
                {
                    "type": v.violation_type.value,
                    "message": v.message,
                    "severity": v.severity,
                    "timestamp": v.timestamp.isoformat()
                }
                for v in self.violations[-10:]  # Last 10 violations
            ]
        }

    async def emit_risk_violation(self, violation: RiskViolation, nats_client, js):
        """Emit risk violation event to NATS."""
        try:
            event_data = {
                "violation_type": violation.violation_type.value,
                "symbol": violation.symbol,
                "message": violation.message,
                "severity": violation.severity,
                "timestamp": violation.timestamp.isoformat(),
                "metadata": violation.metadata
            }

            await js.publish(
                "risk.violations",
                json.dumps(event_data).encode()
            )

            logger.warning("Risk violation emitted",
                         violation_type=violation.violation_type.value,
                         severity=violation.severity)

        except Exception as e:
            logger.error("Failed to emit risk violation", error=str(e))
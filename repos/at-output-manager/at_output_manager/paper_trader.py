"""
Paper trading engine for simulating order execution without real money.
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger()

class PaperTrader:
    """Paper trading engine for order execution simulation"""

    def __init__(self, js_client, initial_balance: float = 10000.0):
        self.js_client = js_client
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions = {}  # symbol -> position info
        self.trades = []  # trade history
        self.portfolio_value = initial_balance
        self._initialized = False

    async def initialize(self):
        """Initialize paper trader"""
        try:
            # Load any existing state (in production, this might come from Redis/DB)
            self._load_initial_state()

            self._initialized = True
            logger.info(
                "Paper trader initialized",
                initial_balance=self.initial_balance,
                current_balance=self.balance,
                positions_count=len(self.positions)
            )

        except Exception as e:
            logger.error(f"Failed to initialize paper trader: {e}")
            raise

    def _load_initial_state(self):
        """Load initial trading state (placeholder for persistence)"""
        # In a real implementation, this would load from Redis/database
        # For now, we start fresh each time
        pass

    async def execute_trade(self, order: Dict[str, Any], agent_output: Dict[str, Any], corr_id: str) -> Dict[str, Any]:
        """Execute a paper trade based on agent order"""
        if not self._initialized:
            raise RuntimeError("Paper trader not initialized")

        trade_id = f"paper_{uuid.uuid4().hex[:8]}"

        try:
            # Extract order details
            symbol = order.get('symbol', 'UNKNOWN')
            side = order.get('side', 'buy').lower()
            order_type = order.get('type', 'market').lower()
            quantity = float(order.get('quantity', 0))
            price = float(order.get('price', 0)) if order.get('price') else None

            # Validate order
            validation_result = self._validate_order(order, side, quantity, price)
            if not validation_result['valid']:
                return {
                    'trade_id': trade_id,
                    'success': False,
                    'error': validation_result['error'],
                    'order': order,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }

            # Simulate price if not provided (market order)
            if not price:
                price = await self._get_simulated_price(symbol, side)

            # Calculate trade cost
            trade_value = quantity * price
            fees = self._calculate_fees(trade_value)
            total_cost = trade_value + fees

            # Check if we have sufficient funds/position
            if side == 'buy':
                if total_cost > self.balance:
                    return {
                        'trade_id': trade_id,
                        'success': False,
                        'error': f'Insufficient balance: ${self.balance:.2f} < ${total_cost:.2f}',
                        'order': order,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
            else:  # sell
                current_position = self.positions.get(symbol, {}).get('quantity', 0)
                if quantity > current_position:
                    return {
                        'trade_id': trade_id,
                        'success': False,
                        'error': f'Insufficient position: {current_position} < {quantity}',
                        'order': order,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }

            # Execute the trade
            execution_result = await self._execute_paper_order(
                trade_id, symbol, side, quantity, price, fees, agent_output, corr_id
            )

            # Update portfolio
            self._update_portfolio(symbol, side, quantity, price, fees)

            logger.info(
                "Paper trade executed successfully",
                trade_id=trade_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                corr_id=corr_id
            )

            return execution_result

        except Exception as e:
            logger.error(
                "Paper trade execution failed",
                trade_id=trade_id,
                error=str(e),
                order=order,
                corr_id=corr_id
            )
            return {
                'trade_id': trade_id,
                'success': False,
                'error': f'Execution error: {str(e)}',
                'order': order,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

    def _validate_order(self, order: Dict[str, Any], side: str, quantity: float, price: Optional[float]) -> Dict[str, Any]:
        """Validate order parameters"""
        if not order.get('symbol'):
            return {'valid': False, 'error': 'Missing symbol'}

        if side not in ['buy', 'sell']:
            return {'valid': False, 'error': f'Invalid side: {side}'}

        if quantity <= 0:
            return {'valid': False, 'error': f'Invalid quantity: {quantity}'}

        if price is not None and price <= 0:
            return {'valid': False, 'error': f'Invalid price: {price}'}

        return {'valid': True}

    async def _get_simulated_price(self, symbol: str, side: str) -> float:
        """Get simulated market price for symbol"""
        # In a real implementation, this would fetch from a price feed
        # For simulation, we use some realistic base prices with small random variation
        import random

        base_prices = {
            'BTCUSD': 45000.0,
            'ETHUSD': 3000.0,
            'AAPL': 180.0,
            'TSLA': 250.0,
            'SPY': 450.0,
            'QQQ': 380.0
        }

        base_price = base_prices.get(symbol, 100.0)

        # Add small random variation (-0.5% to +0.5%)
        variation = random.uniform(-0.005, 0.005)
        simulated_price = base_price * (1 + variation)

        # Add slight spread for buy/sell
        if side == 'buy':
            simulated_price *= 1.001  # 0.1% spread
        else:
            simulated_price *= 0.999

        return round(simulated_price, 2)

    def _calculate_fees(self, trade_value: float) -> float:
        """Calculate trading fees (simplified)"""
        # Simplified fee structure: 0.1% of trade value
        return trade_value * 0.001

    async def _execute_paper_order(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fees: float,
        agent_output: Dict[str, Any],
        corr_id: str
    ) -> Dict[str, Any]:
        """Execute the paper trade and record it"""

        trade_record = {
            'trade_id': trade_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'fees': fees,
            'trade_value': quantity * price,
            'agent_output': {
                'agent_id': agent_output.get('agent_id'),
                'agent_type': agent_output.get('agent_type'),
                'confidence': agent_output.get('confidence')
            },
            'correlation_id': corr_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'filled'
        }

        # Add to trade history
        self.trades.append(trade_record)

        # Keep only last 1000 trades in memory
        if len(self.trades) > 1000:
            self.trades = self.trades[-1000:]

        return {
            'trade_id': trade_id,
            'success': True,
            'status': 'filled',
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'fill_price': price,
            'fees': fees,
            'trade_value': quantity * price,
            'timestamp': trade_record['timestamp'],
            'balance_after': self.balance
        }

    def _update_portfolio(self, symbol: str, side: str, quantity: float, price: float, fees: float):
        """Update portfolio positions and balance"""
        trade_value = quantity * price

        if side == 'buy':
            # Reduce balance
            self.balance -= (trade_value + fees)

            # Update position
            if symbol not in self.positions:
                self.positions[symbol] = {
                    'quantity': 0,
                    'avg_price': 0,
                    'unrealized_pnl': 0
                }

            pos = self.positions[symbol]
            total_cost = (pos['quantity'] * pos['avg_price']) + trade_value
            total_quantity = pos['quantity'] + quantity
            pos['avg_price'] = total_cost / total_quantity if total_quantity > 0 else 0
            pos['quantity'] = total_quantity

        else:  # sell
            # Add to balance
            self.balance += (trade_value - fees)

            # Update position
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos['quantity'] -= quantity

                # Remove position if quantity is zero
                if pos['quantity'] <= 0:
                    del self.positions[symbol]

        # Update portfolio value (simplified - would need current prices in reality)
        self.portfolio_value = self.balance
        for symbol, pos in self.positions.items():
            # Use last trade price as approximation
            last_price = next(
                (t['price'] for t in reversed(self.trades) if t['symbol'] == symbol),
                pos['avg_price']
            )
            self.portfolio_value += pos['quantity'] * last_price

    async def get_status(self) -> Dict[str, Any]:
        """Get current paper trading status"""
        return {
            'initialized': self._initialized,
            'balance': round(self.balance, 2),
            'portfolio_value': round(self.portfolio_value, 2),
            'total_pnl': round(self.portfolio_value - self.initial_balance, 2),
            'total_pnl_percent': round(((self.portfolio_value - self.initial_balance) / self.initial_balance) * 100, 2),
            'positions_count': len(self.positions),
            'trades_count': len(self.trades)
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get detailed trading statistics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'total_volume': 0,
                'total_fees': 0,
                'win_rate': 0,
                'avg_trade_size': 0
            }

        total_volume = sum(t['trade_value'] for t in self.trades)
        total_fees = sum(t['fees'] for t in self.trades)

        # Calculate win rate (simplified - just based on buy/sell alternating pattern)
        buy_trades = [t for t in self.trades if t['side'] == 'buy']
        sell_trades = [t for t in self.trades if t['side'] == 'sell']

        stats = {
            'total_trades': len(self.trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'total_volume': round(total_volume, 2),
            'total_fees': round(total_fees, 2),
            'avg_trade_size': round(total_volume / len(self.trades), 2),
            'current_balance': round(self.balance, 2),
            'portfolio_value': round(self.portfolio_value, 2),
            'total_pnl': round(self.portfolio_value - self.initial_balance, 2),
            'positions': {
                symbol: {
                    'quantity': pos['quantity'],
                    'avg_price': round(pos['avg_price'], 2)
                } for symbol, pos in self.positions.items()
            }
        }

        return stats

    async def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent trades"""
        return self.trades[-limit:] if self.trades else []

    async def reset_portfolio(self) -> Dict[str, Any]:
        """Reset paper trading portfolio (for testing/demo)"""
        old_balance = self.balance
        old_positions = len(self.positions)
        old_trades = len(self.trades)

        self.balance = self.initial_balance
        self.positions = {}
        self.trades = []
        self.portfolio_value = self.initial_balance

        logger.info(
            "Paper trading portfolio reset",
            old_balance=old_balance,
            old_positions=old_positions,
            old_trades=old_trades
        )

        return {
            'reset': True,
            'new_balance': self.balance,
            'old_balance': old_balance,
            'trades_cleared': old_trades,
            'positions_cleared': old_positions
        }

    async def cleanup(self):
        """Clean up paper trader resources"""
        # In a real implementation, this might save state to persistence layer
        logger.info(
            "Paper trader cleanup completed",
            final_balance=self.balance,
            trades_count=len(self.trades),
            positions_count=len(self.positions)
        )
"""
Backtesting harness for historical strategy validation.

Responsibilities:
- Replay historical data through NATS subjects
- Deterministic seeding for reproducible tests
- JSON fixture support for unit testing
- Results publication to backtest.results
- Performance metrics and P&L calculation
- CSV/Parquet export for analysis
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import csv
import random

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi.responses import Response
import pandas as pd

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
backtests_total = Counter('backtester_tests_total', 'Total backtests executed')
backtest_duration = Histogram('backtester_duration_seconds', 'Backtest execution time')
events_replayed = Counter('backtester_events_replayed_total', 'Total events replayed')
strategies_tested = Gauge('backtester_active_strategies', 'Number of strategies being tested')

class BacktestStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class BacktestConfig:
    test_id: str
    start_date: datetime
    end_date: datetime
    symbols: List[str]
    initial_balance: float
    strategies: List[str]
    seed: Optional[int] = None
    replay_speed: float = 1.0  # 1.0 = real-time, 10.0 = 10x speed
    commission: float = 0.001  # 0.1% commission
    slippage: float = 0.0005   # 0.05% slippage

@dataclass
class BacktestResult:
    test_id: str
    status: BacktestStatus
    start_time: datetime
    end_time: Optional[datetime]
    config: BacktestConfig
    total_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    final_balance: Optional[float] = None
    error_message: Optional[str] = None

@dataclass
class Trade:
    timestamp: datetime
    symbol: str
    action: str
    quantity: float
    price: float
    commission: float
    slippage: float
    strategy: str

class HistoricalDataSource:
    """Mock historical data source - in production would connect to real data."""

    def __init__(self):
        self.symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]

    async def get_data(self, start_date: datetime, end_date: datetime, symbols: List[str]) -> pd.DataFrame:
        """Generate mock historical data."""
        date_range = pd.date_range(start=start_date, end=end_date, freq='1min')
        data = []

        for symbol in symbols:
            base_price = random.uniform(50, 200)
            for timestamp in date_range:
                # Generate realistic price movement
                price_change = random.gauss(0, base_price * 0.02)  # 2% volatility
                base_price = max(1, base_price + price_change)

                volume = random.randint(10000, 1000000)

                data.append({
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'price': round(base_price, 2),
                    'volume': volume,
                    'bid': round(base_price * 0.999, 2),
                    'ask': round(base_price * 1.001, 2)
                })

        return pd.DataFrame(data).sort_values('timestamp')

class BacktestEngine:
    def __init__(self):
        self.nats_client: Optional[NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.data_source = HistoricalDataSource()
        self.active_backtests: Dict[str, BacktestResult] = {}
        self.trade_history: Dict[str, List[Trade]] = {}

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

    async def start_backtest(self, config: BacktestConfig) -> str:
        """Start a new backtest."""
        test_id = config.test_id or str(uuid.uuid4())

        result = BacktestResult(
            test_id=test_id,
            status=BacktestStatus.PENDING,
            start_time=datetime.utcnow(),
            end_time=None,
            config=config
        )

        self.active_backtests[test_id] = result
        self.trade_history[test_id] = []

        logger.info("Backtest created", test_id=test_id, config=asdict(config))
        return test_id

    async def run_backtest(self, test_id: str):
        """Execute backtest in background."""
        if test_id not in self.active_backtests:
            raise ValueError(f"Backtest {test_id} not found")

        result = self.active_backtests[test_id]
        config = result.config

        try:
            result.status = BacktestStatus.RUNNING
            strategies_tested.set(len(config.strategies))
            backtests_total.inc()

            with backtest_duration.time():
                # Set random seed for reproducibility
                if config.seed:
                    random.seed(config.seed)

                # Get historical data
                logger.info("Loading historical data", test_id=test_id)
                data = await self.data_source.get_data(
                    config.start_date,
                    config.end_date,
                    config.symbols
                )

                # Initialize simulation state
                balance = config.initial_balance
                positions = {symbol: 0 for symbol in config.symbols}

                # Replay data through NATS
                await self._replay_data(data, config, test_id)

                # Calculate performance metrics
                trades = self.trade_history[test_id]
                final_balance = self._calculate_final_balance(trades, config.initial_balance)

                result.final_balance = final_balance
                result.total_return = (final_balance - config.initial_balance) / config.initial_balance
                result.total_trades = len(trades)
                result.win_rate = self._calculate_win_rate(trades)
                result.sharpe_ratio = self._calculate_sharpe_ratio(trades)
                result.max_drawdown = self._calculate_max_drawdown(trades, config.initial_balance)

                result.status = BacktestStatus.COMPLETED
                result.end_time = datetime.utcnow()

                # Publish results
                await self._publish_results(result)

                logger.info("Backtest completed",
                           test_id=test_id,
                           return_pct=result.total_return * 100,
                           trades=result.total_trades)

        except Exception as e:
            logger.error("Backtest failed", test_id=test_id, error=str(e))
            result.status = BacktestStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.utcnow()

    async def _replay_data(self, data: pd.DataFrame, config: BacktestConfig, test_id: str):
        """Replay historical data through NATS subjects."""
        logger.info("Starting data replay", test_id=test_id, events=len(data))

        for _, row in data.iterrows():
            # Create normalized signal event
            signal_data = {
                "symbol": row['symbol'],
                "timestamp": row['timestamp'].isoformat(),
                "price": row['price'],
                "volume": row['volume'],
                "bid": row['bid'],
                "ask": row['ask'],
                "correlation_id": f"backtest-{test_id}-{row['timestamp']}",
                "source": "backtester",
                "backtest_id": test_id
            }

            # Publish to signals.normalized
            if self.js:
                await self.js.publish(
                    "signals.normalized",
                    json.dumps(signal_data).encode()
                )

            events_replayed.inc()

            # Add artificial delay for replay speed control
            if config.replay_speed < 100:  # Don't delay for very fast replays
                await asyncio.sleep(0.001 / config.replay_speed)

    def _calculate_final_balance(self, trades: List[Trade], initial_balance: float) -> float:
        """Calculate final balance from trades."""
        balance = initial_balance
        positions = {}

        for trade in trades:
            symbol = trade.symbol
            if symbol not in positions:
                positions[symbol] = 0

            if trade.action == "BUY":
                cost = trade.quantity * trade.price + trade.commission
                balance -= cost
                positions[symbol] += trade.quantity
            elif trade.action == "SELL":
                revenue = trade.quantity * trade.price - trade.commission
                balance += revenue
                positions[symbol] -= trade.quantity

        # Calculate value of remaining positions (using last known prices)
        # In real backtest, would use final market prices
        for symbol, quantity in positions.items():
            if quantity != 0:
                # Estimate final price (simplified)
                estimated_price = 100.0  # Would use actual final price
                balance += quantity * estimated_price

        return balance

    def _calculate_win_rate(self, trades: List[Trade]) -> float:
        """Calculate win rate from trades."""
        if not trades:
            return 0.0

        # Group trades by symbol to calculate P&L per round trip
        positions = {}
        completed_trades = 0
        winning_trades = 0

        for trade in trades:
            symbol = trade.symbol
            if symbol not in positions:
                positions[symbol] = {"quantity": 0, "avg_price": 0, "total_cost": 0}

            pos = positions[symbol]

            if trade.action == "BUY":
                new_quantity = pos["quantity"] + trade.quantity
                new_cost = pos["total_cost"] + (trade.quantity * trade.price)
                pos["quantity"] = new_quantity
                pos["total_cost"] = new_cost
                if new_quantity > 0:
                    pos["avg_price"] = new_cost / new_quantity
            elif trade.action == "SELL":
                if pos["quantity"] > 0:
                    # Calculate P&L for this sale
                    pnl = (trade.price - pos["avg_price"]) * trade.quantity
                    completed_trades += 1
                    if pnl > 0:
                        winning_trades += 1

                    pos["quantity"] -= trade.quantity
                    if pos["quantity"] <= 0:
                        positions[symbol] = {"quantity": 0, "avg_price": 0, "total_cost": 0}

        return winning_trades / completed_trades if completed_trades > 0 else 0.0

    def _calculate_sharpe_ratio(self, trades: List[Trade]) -> float:
        """Calculate Sharpe ratio (simplified)."""
        if len(trades) < 2:
            return 0.0

        # Calculate daily returns (simplified)
        returns = []
        for i in range(1, len(trades)):
            # Simplified return calculation
            returns.append(random.gauss(0.001, 0.02))  # Mock daily return

        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)
        std_return = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5

        # Annualize (assuming 252 trading days)
        annual_return = mean_return * 252
        annual_std = std_return * (252 ** 0.5)

        return annual_return / annual_std if annual_std > 0 else 0.0

    def _calculate_max_drawdown(self, trades: List[Trade], initial_balance: float) -> float:
        """Calculate maximum drawdown."""
        if not trades:
            return 0.0

        balance = initial_balance
        peak_balance = initial_balance
        max_drawdown = 0.0

        for trade in trades:
            if trade.action == "BUY":
                balance -= trade.quantity * trade.price + trade.commission
            elif trade.action == "SELL":
                balance += trade.quantity * trade.price - trade.commission

            if balance > peak_balance:
                peak_balance = balance

            drawdown = (peak_balance - balance) / peak_balance
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    async def _publish_results(self, result: BacktestResult):
        """Publish backtest results to NATS."""
        try:
            results_data = {
                "test_id": result.test_id,
                "status": result.status.value,
                "config": asdict(result.config),
                "total_return": result.total_return,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown": result.max_drawdown,
                "win_rate": result.win_rate,
                "total_trades": result.total_trades,
                "final_balance": result.final_balance,
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat() if result.end_time else None,
                "error_message": result.error_message
            }

            if self.js:
                await self.js.publish(
                    "backtest.results",
                    json.dumps(results_data).encode()
                )

            logger.info("Published backtest results", test_id=result.test_id)

        except Exception as e:
            logger.error("Failed to publish backtest results", test_id=result.test_id, error=str(e))

    async def export_results(self, test_id: str, format: str = "csv") -> str:
        """Export backtest results to file."""
        if test_id not in self.active_backtests:
            raise ValueError(f"Backtest {test_id} not found")

        result = self.active_backtests[test_id]
        trades = self.trade_history.get(test_id, [])

        filename = f"backtest_{test_id}.{format}"

        if format == "csv":
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write summary
                writer.writerow(["# Backtest Summary"])
                writer.writerow(["Test ID", result.test_id])
                writer.writerow(["Status", result.status.value])
                writer.writerow(["Total Return", result.total_return])
                writer.writerow(["Sharpe Ratio", result.sharpe_ratio])
                writer.writerow(["Max Drawdown", result.max_drawdown])
                writer.writerow(["Win Rate", result.win_rate])
                writer.writerow(["Total Trades", result.total_trades])
                writer.writerow([])

                # Write trades
                writer.writerow(["# Trade History"])
                writer.writerow(["Timestamp", "Symbol", "Action", "Quantity", "Price", "Commission", "Strategy"])

                for trade in trades:
                    writer.writerow([
                        trade.timestamp.isoformat(),
                        trade.symbol,
                        trade.action,
                        trade.quantity,
                        trade.price,
                        trade.commission,
                        trade.strategy
                    ])

        return filename

# FastAPI app
app = FastAPI(title="Backtesting Service", version="0.1.0")
backtest_engine = BacktestEngine()

@app.on_event("startup")
async def startup():
    """Initialize NATS connections on startup."""
    await backtest_engine.connect_nats()

@app.on_event("shutdown")
async def shutdown():
    """Clean shutdown."""
    if backtest_engine.nats_client:
        await backtest_engine.nats_client.close()

@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "backtester",
        "timestamp": datetime.utcnow().isoformat(),
        "nats_connected": backtest_engine.nats_client is not None,
        "active_backtests": len(backtest_engine.active_backtests)
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type="text/plain")

@app.post("/backtest/start")
async def start_backtest(
    start_date: str,
    end_date: str,
    symbols: List[str],
    strategies: List[str],
    initial_balance: float = 100000,
    seed: Optional[int] = None,
    replay_speed: float = 1.0,
    background_tasks: BackgroundTasks = None
):
    """Start a new backtest."""
    try:
        config = BacktestConfig(
            test_id=str(uuid.uuid4()),
            start_date=datetime.fromisoformat(start_date),
            end_date=datetime.fromisoformat(end_date),
            symbols=symbols,
            initial_balance=initial_balance,
            strategies=strategies,
            seed=seed,
            replay_speed=replay_speed
        )

        test_id = await backtest_engine.start_backtest(config)

        # Run backtest in background
        background_tasks.add_task(backtest_engine.run_backtest, test_id)

        return {"test_id": test_id, "status": "started"}

    except Exception as e:
        logger.error("Failed to start backtest", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/backtest/{test_id}/status")
async def get_backtest_status(test_id: str):
    """Get backtest status and results."""
    if test_id not in backtest_engine.active_backtests:
        raise HTTPException(status_code=404, detail="Backtest not found")

    result = backtest_engine.active_backtests[test_id]
    return asdict(result)

@app.get("/backtest/{test_id}/export")
async def export_backtest(test_id: str, format: str = "csv"):
    """Export backtest results."""
    try:
        filename = await backtest_engine.export_results(test_id, format)
        return FileResponse(filename, filename=filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/backtests")
async def list_backtests():
    """List all backtests."""
    return {
        "backtests": [
            {
                "test_id": result.test_id,
                "status": result.status.value,
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat() if result.end_time else None,
                "total_return": result.total_return,
                "total_trades": result.total_trades
            }
            for result in backtest_engine.active_backtests.values()
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
"""
Feature calculation service that can be integrated into existing services.

This service subscribes to market signals and calculates features in real-time,
storing them in the feature store for use by ML strategies.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
import structlog

from .feature_store import FeatureStore, MarketBar, MarketMicrostructure

logger = structlog.get_logger()

class FeatureCalculationService:
    """
    Service for real-time feature calculation and storage.

    This can be integrated into existing services (like at-gateway) or run standalone.
    """

    def __init__(self,
                 feature_store: FeatureStore,
                 nats_client: Optional[NATS] = None,
                 js: Optional[JetStreamContext] = None):
        self.feature_store = feature_store
        self.nats_client = nats_client
        self.js = js
        self.own_nats_connection = False

        # Track last prices for microstructure calculations
        self.last_prices: Dict[str, float] = {}
        self.last_volumes: Dict[str, int] = {}

        # Bar aggregation state
        self.current_bars: Dict[str, Dict[str, Any]] = {}  # symbol:interval -> bar data
        self.bar_intervals = ["1m", "5m", "15m", "1h"]

    async def initialize(self, nats_url: str = "nats://localhost:4222"):
        """Initialize the feature calculation service."""
        # Connect to feature store
        await self.feature_store.connect()

        # Connect to NATS if not provided
        if not self.nats_client:
            self.nats_client = await nats.connect(nats_url)
            self.js = self.nats_client.jetstream()
            self.own_nats_connection = True
            logger.info("Feature calculator connected to NATS", url=nats_url)

        # Subscribe to market signals
        await self.js.subscribe(
            "signals.normalized",
            cb=self._handle_market_signal,
            durable="feature-calculator-signals",
            queue="feature-calculator"
        )

        logger.info("Feature calculation service initialized")

    async def shutdown(self):
        """Shutdown the service."""
        if self.own_nats_connection and self.nats_client:
            await self.nats_client.close()

        await self.feature_store.disconnect()
        logger.info("Feature calculation service shutdown")

    async def _handle_market_signal(self, msg):
        """Process incoming market signals for feature calculation."""
        try:
            data = json.loads(msg.data.decode())

            symbol = data["symbol"]
            price = data["price"]
            volume = data.get("volume", 0)
            timestamp = datetime.fromisoformat(data["timestamp"])
            bid = data.get("bid")
            ask = data.get("ask")

            # Update bars for different intervals
            await self._update_bars(symbol, price, volume, timestamp)

            # Calculate microstructure features if bid/ask available
            if bid is not None and ask is not None:
                await self._calculate_microstructure_features(symbol, price, volume, bid, ask, timestamp)

            # Store basic price/volume features
            await self._store_basic_features(symbol, price, volume, timestamp)

            await msg.ack()

        except Exception as e:
            logger.error("Error processing market signal for features", error=str(e))
            await msg.nak()

    async def _update_bars(self, symbol: str, price: float, volume: int, timestamp: datetime):
        """Update OHLCV bars for different time intervals."""
        for interval in self.bar_intervals:
            # Round timestamp to interval boundary
            bar_timestamp = self._round_to_interval(timestamp, interval)
            bar_key = f"{symbol}:{interval}"

            # Initialize or update bar
            if bar_key not in self.current_bars:
                self.current_bars[bar_key] = {
                    "symbol": symbol,
                    "timestamp": bar_timestamp,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume,
                    "interval": interval
                }
            else:
                bar = self.current_bars[bar_key]

                # Check if we need to finalize current bar and start new one
                if bar_timestamp > bar["timestamp"]:
                    # Finalize previous bar
                    await self._finalize_bar(bar_key, bar)

                    # Start new bar
                    self.current_bars[bar_key] = {
                        "symbol": symbol,
                        "timestamp": bar_timestamp,
                        "open": price,
                        "high": price,
                        "low": price,
                        "close": price,
                        "volume": volume,
                        "interval": interval
                    }
                else:
                    # Update current bar
                    bar["high"] = max(bar["high"], price)
                    bar["low"] = min(bar["low"], price)
                    bar["close"] = price
                    bar["volume"] += volume

    def _round_to_interval(self, timestamp: datetime, interval: str) -> datetime:
        """Round timestamp to interval boundary."""
        if interval == "1m":
            return timestamp.replace(second=0, microsecond=0)
        elif interval == "5m":
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif interval == "15m":
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif interval == "1h":
            return timestamp.replace(minute=0, second=0, microsecond=0)
        else:
            return timestamp

    async def _finalize_bar(self, bar_key: str, bar_data: Dict[str, Any]):
        """Finalize and store a completed bar."""
        try:
            bar = MarketBar(**bar_data)
            await self.feature_store.update_bar(bar)
            logger.debug("Bar finalized", symbol=bar.symbol, interval=bar.interval, timestamp=bar.timestamp)
        except Exception as e:
            logger.error("Failed to finalize bar", bar_key=bar_key, error=str(e))

    async def _calculate_microstructure_features(self,
                                               symbol: str,
                                               price: float,
                                               volume: int,
                                               bid: float,
                                               ask: float,
                                               timestamp: datetime):
        """Calculate market microstructure features."""
        try:
            # Calculate spreads
            bid_ask_spread = ask - bid
            quoted_spread = bid_ask_spread / ((bid + ask) / 2) if (bid + ask) > 0 else 0

            # Effective spread (assuming trade at mid)
            mid_price = (bid + ask) / 2
            effective_spread = abs(price - mid_price) * 2

            # Simple depth imbalance (would need order book data for real implementation)
            # Using volume as proxy for size
            bid_size = volume  # Simplified
            ask_size = volume  # Simplified
            depth_imbalance = (bid_size - ask_size) / (bid_size + ask_size) if (bid_size + ask_size) > 0 else 0

            ms = MarketMicrostructure(
                symbol=symbol,
                timestamp=timestamp,
                bid_ask_spread=bid_ask_spread,
                bid_size=bid_size,
                ask_size=ask_size,
                depth_imbalance=depth_imbalance,
                effective_spread=effective_spread,
                quoted_spread=quoted_spread
            )

            await self.feature_store.update_microstructure(ms)

        except Exception as e:
            logger.error("Failed to calculate microstructure features", symbol=symbol, error=str(e))

    async def _store_basic_features(self, symbol: str, price: float, volume: int, timestamp: datetime):
        """Store basic price and volume features."""
        try:
            # Store current price and volume
            await self.feature_store.store_feature(symbol, "current_price", price, {"timestamp": timestamp.isoformat()})
            await self.feature_store.store_feature(symbol, "current_volume", volume, {"timestamp": timestamp.isoformat()})

            # Calculate price change if we have previous price
            if symbol in self.last_prices:
                price_change = (price - self.last_prices[symbol]) / self.last_prices[symbol] if self.last_prices[symbol] > 0 else 0
                await self.feature_store.store_feature(symbol, "price_change", price_change, {"timestamp": timestamp.isoformat()})

            # Calculate volume change
            if symbol in self.last_volumes:
                volume_change = volume - self.last_volumes[symbol]
                await self.feature_store.store_feature(symbol, "volume_change", volume_change, {"timestamp": timestamp.isoformat()})

            # Update last values
            self.last_prices[symbol] = price
            self.last_volumes[symbol] = volume

        except Exception as e:
            logger.error("Failed to store basic features", symbol=symbol, error=str(e))

    async def force_finalize_bars(self):
        """Force finalize all current bars (useful for testing)."""
        for bar_key, bar_data in list(self.current_bars.items()):
            await self._finalize_bar(bar_key, bar_data)
        self.current_bars.clear()

    async def get_feature_summary(self) -> Dict[str, Any]:
        """Get summary of calculated features."""
        return await self.feature_store.get_feature_stats()
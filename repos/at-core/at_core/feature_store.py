"""
ML Feature Store Stub - Foundation for ML-based strategies

This module provides a Redis-backed feature cache for machine learning strategies.
It handles rolling window calculations, market microstructure features, and feature versioning.
"""

import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import deque
import numpy as np
import pandas as pd
import redis
from redis import asyncio as aioredis
import structlog

logger = structlog.get_logger()

@dataclass
class FeatureConfig:
    """Configuration for a feature."""
    name: str
    window_size: int
    calculation_type: str  # rolling, ewma, static
    ttl_seconds: int
    version: str

@dataclass
class MarketBar:
    """OHLCV bar data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    interval: str  # 1m, 5m, 15m, 1h, 1d

@dataclass
class MarketMicrostructure:
    """Market microstructure features."""
    symbol: str
    timestamp: datetime
    bid_ask_spread: float
    bid_size: int
    ask_size: int
    depth_imbalance: float  # (bid_size - ask_size) / (bid_size + ask_size)
    effective_spread: float
    quoted_spread: float

@dataclass
class Feature:
    """Computed feature with metadata."""
    name: str
    value: Any
    timestamp: datetime
    version: str
    metadata: Dict[str, Any]

class FeatureStore:
    """
    Redis-backed feature store for ML strategies.

    Features are stored with keys: feature:{symbol}:{name}:{version}
    TTL is automatically managed based on feature configuration.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 0):
        self.redis_url = redis_url
        self.db = db
        self.redis_client: Optional[aioredis.Redis] = None
        self.feature_configs: Dict[str, FeatureConfig] = {}
        self.bars_cache: Dict[str, deque] = {}  # symbol:interval -> deque of MarketBar

        # Standard feature configurations
        self._register_default_features()

    def _register_default_features(self):
        """Register default feature configurations."""
        # Price-based features
        self.feature_configs["sma_20"] = FeatureConfig("sma_20", 20, "rolling", 300, "1.0")
        self.feature_configs["sma_50"] = FeatureConfig("sma_50", 50, "rolling", 300, "1.0")
        self.feature_configs["ema_12"] = FeatureConfig("ema_12", 12, "ewma", 300, "1.0")
        self.feature_configs["ema_26"] = FeatureConfig("ema_26", 26, "ewma", 300, "1.0")

        # Volatility features
        self.feature_configs["volatility_20"] = FeatureConfig("volatility_20", 20, "rolling", 300, "1.0")
        self.feature_configs["atr_14"] = FeatureConfig("atr_14", 14, "rolling", 300, "1.0")

        # Volume features
        self.feature_configs["vwap"] = FeatureConfig("vwap", 20, "rolling", 300, "1.0")
        self.feature_configs["volume_ratio"] = FeatureConfig("volume_ratio", 20, "rolling", 300, "1.0")

        # Microstructure features
        self.feature_configs["avg_spread"] = FeatureConfig("avg_spread", 100, "rolling", 60, "1.0")
        self.feature_configs["depth_imbalance"] = FeatureConfig("depth_imbalance", 100, "rolling", 60, "1.0")

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = await aioredis.from_url(
                self.redis_url,
                db=self.db,
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Connected to Redis feature store", url=self.redis_url)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()

    async def update_bar(self, bar: MarketBar):
        """Update OHLCV bar data."""
        cache_key = f"{bar.symbol}:{bar.interval}"

        if cache_key not in self.bars_cache:
            self.bars_cache[cache_key] = deque(maxlen=200)  # Keep last 200 bars

        self.bars_cache[cache_key].append(bar)

        # Store in Redis for persistence
        redis_key = f"bars:{cache_key}:{bar.timestamp.timestamp()}"
        await self._store_feature(redis_key, asdict(bar), ttl=86400)  # 24h TTL

        # Trigger feature recalculation
        await self._calculate_bar_features(bar.symbol, bar.interval)

    async def _calculate_bar_features(self, symbol: str, interval: str):
        """Calculate features from bar data."""
        cache_key = f"{symbol}:{interval}"
        bars = self.bars_cache.get(cache_key)

        if not bars or len(bars) < 2:
            return

        # Convert to DataFrame for easier calculation
        df = pd.DataFrame([asdict(bar) for bar in bars])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)

        # Calculate SMA features
        if len(bars) >= 20:
            sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
            await self.store_feature(symbol, "sma_20", sma_20, {"interval": interval})

        if len(bars) >= 50:
            sma_50 = df['close'].rolling(window=50).mean().iloc[-1]
            await self.store_feature(symbol, "sma_50", sma_50, {"interval": interval})

        # Calculate EMA features
        if len(bars) >= 12:
            ema_12 = df['close'].ewm(span=12, adjust=False).mean().iloc[-1]
            await self.store_feature(symbol, "ema_12", ema_12, {"interval": interval})

        if len(bars) >= 26:
            ema_26 = df['close'].ewm(span=26, adjust=False).mean().iloc[-1]
            await self.store_feature(symbol, "ema_26", ema_26, {"interval": interval})

        # Calculate volatility (standard deviation of returns)
        if len(bars) >= 20:
            returns = df['close'].pct_change().dropna()
            volatility_20 = returns.rolling(window=20).std().iloc[-1] if len(returns) >= 20 else 0
            await self.store_feature(symbol, "volatility_20", volatility_20, {"interval": interval})

        # Calculate ATR (Average True Range)
        if len(bars) >= 14:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr_14 = true_range.rolling(window=14).mean().iloc[-1]
            await self.store_feature(symbol, "atr_14", atr_14, {"interval": interval})

        # Calculate VWAP (Volume Weighted Average Price)
        if len(bars) >= 20:
            df['vwap'] = (df['close'] * df['volume']).rolling(window=20).sum() / df['volume'].rolling(window=20).sum()
            vwap = df['vwap'].iloc[-1]
            await self.store_feature(symbol, "vwap", vwap, {"interval": interval})

        # Calculate Volume Ratio (current vs average)
        if len(bars) >= 20:
            avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            await self.store_feature(symbol, "volume_ratio", volume_ratio, {"interval": interval})

    async def update_microstructure(self, ms: MarketMicrostructure):
        """Update market microstructure features."""
        # Store microstructure snapshot
        redis_key = f"microstructure:{ms.symbol}:{ms.timestamp.timestamp()}"
        await self._store_feature(redis_key, asdict(ms), ttl=3600)  # 1h TTL

        # Calculate rolling microstructure features
        await self.store_feature(ms.symbol, "bid_ask_spread", ms.bid_ask_spread, {"type": "current"})
        await self.store_feature(ms.symbol, "depth_imbalance", ms.depth_imbalance, {"type": "current"})
        await self.store_feature(ms.symbol, "effective_spread", ms.effective_spread, {"type": "current"})

    async def store_feature(self, symbol: str, feature_name: str, value: Any, metadata: Dict[str, Any] = None):
        """Store a computed feature."""
        if feature_name not in self.feature_configs:
            logger.warning("Unknown feature", feature=feature_name)
            return

        config = self.feature_configs[feature_name]
        feature = Feature(
            name=feature_name,
            value=value,
            timestamp=datetime.utcnow(),
            version=config.version,
            metadata=metadata or {}
        )

        key = f"feature:{symbol}:{feature_name}:{config.version}"
        await self._store_feature(key, asdict(feature), ttl=config.ttl_seconds)

    async def _store_feature(self, key: str, value: Dict[str, Any], ttl: int):
        """Store feature in Redis with TTL."""
        if not self.redis_client:
            return

        try:
            # Convert datetime to ISO format for JSON serialization
            for k, v in value.items():
                if isinstance(v, datetime):
                    value[k] = v.isoformat()

            json_value = json.dumps(value)
            await self.redis_client.set(key, json_value, ex=ttl)

        except Exception as e:
            logger.error("Failed to store feature", key=key, error=str(e))

    async def get_feature(self, symbol: str, feature_name: str, version: str = None) -> Optional[Feature]:
        """Retrieve a feature from the store."""
        if not self.redis_client:
            return None

        if feature_name not in self.feature_configs:
            return None

        config = self.feature_configs[feature_name]
        version = version or config.version
        key = f"feature:{symbol}:{feature_name}:{version}"

        try:
            json_value = await self.redis_client.get(key)
            if json_value:
                data = json.loads(json_value)
                # Convert ISO format back to datetime
                if 'timestamp' in data:
                    data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                return Feature(**data)

        except Exception as e:
            logger.error("Failed to get feature", key=key, error=str(e))

        return None

    async def get_features_batch(self, symbol: str, feature_names: List[str]) -> Dict[str, Feature]:
        """Retrieve multiple features in batch."""
        features = {}

        for feature_name in feature_names:
            feature = await self.get_feature(symbol, feature_name)
            if feature:
                features[feature_name] = feature

        return features

    async def get_feature_vector(self, symbol: str, feature_names: List[str]) -> np.ndarray:
        """Get feature vector for ML model input."""
        features = await self.get_features_batch(symbol, feature_names)

        vector = []
        for feature_name in feature_names:
            if feature_name in features:
                value = features[feature_name].value
                # Convert to float if possible
                if isinstance(value, (int, float)):
                    vector.append(float(value))
                else:
                    vector.append(0.0)  # Default value for missing features
            else:
                vector.append(0.0)

        return np.array(vector)

    async def expire_old_features(self, older_than: timedelta):
        """Expire features older than specified time."""
        if not self.redis_client:
            return

        try:
            cutoff = datetime.utcnow() - older_than
            pattern = "feature:*"

            cursor = 0
            expired_count = 0

            while True:
                cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)

                for key in keys:
                    json_value = await self.redis_client.get(key)
                    if json_value:
                        data = json.loads(json_value)
                        timestamp = datetime.fromisoformat(data.get('timestamp', ''))

                        if timestamp < cutoff:
                            await self.redis_client.delete(key)
                            expired_count += 1

                if cursor == 0:
                    break

            logger.info("Expired old features", count=expired_count)

        except Exception as e:
            logger.error("Failed to expire features", error=str(e))

    async def get_feature_stats(self) -> Dict[str, Any]:
        """Get statistics about stored features."""
        if not self.redis_client:
            return {}

        try:
            # Count features by type
            feature_counts = {}
            pattern = "feature:*"

            cursor = 0
            total_features = 0

            while True:
                cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)

                for key in keys:
                    parts = key.split(':')
                    if len(parts) >= 3:
                        feature_name = parts[2]
                        feature_counts[feature_name] = feature_counts.get(feature_name, 0) + 1
                        total_features += 1

                if cursor == 0:
                    break

            # Get Redis memory usage
            info = await self.redis_client.info('memory')
            memory_used = info.get('used_memory_human', 'unknown')

            return {
                "total_features": total_features,
                "feature_counts": feature_counts,
                "memory_used": memory_used,
                "cache_size": len(self.bars_cache),
                "registered_features": len(self.feature_configs)
            }

        except Exception as e:
            logger.error("Failed to get feature stats", error=str(e))
            return {}

    def calculate_feature_hash(self, feature_names: List[str], version: str = "1.0") -> str:
        """Calculate hash for feature set (for model versioning)."""
        feature_string = ":".join(sorted(feature_names)) + ":" + version
        return hashlib.sha256(feature_string.encode()).hexdigest()[:16]
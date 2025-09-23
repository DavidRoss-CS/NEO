# Momentum Agent

**Detects price momentum conditions and trend strength for trading signals.**

## Purpose

The momentum agent analyzes normalized market signals to identify momentum-based trading opportunities. It applies technical analysis techniques including moving averages, RSI, and volume analysis to determine trend direction and strength. The agent emits enriched signals that downstream orchestration can use for trade decision-making.

## Algorithm Overview

### Core Analysis Components

1. **Moving Average Crossover**:
   - Short-term vs. long-term moving average comparison
   - Golden cross (bullish) and death cross (bearish) detection
   - Configurable period lengths (default: 10/20)

2. **RSI Trend Confirmation**:
   - Relative Strength Index calculation
   - Overbought/oversold level detection
   - Momentum divergence identification

3. **Volume-Weighted Analysis**:
   - Volume confirmation of price moves
   - Above/below average volume detection
   - Volume-price relationship scoring

4. **Confidence Scoring**:
   - Multi-factor confidence calculation
   - Signal strength normalization (0.0 to 1.0)
   - Minimum confidence thresholding

### Signal Processing Flow

```
Normalized Signal Input
        ↓
 Historical Price Cache Lookup
        ↓
 Moving Average Calculation
        ↓
 RSI Calculation
        ↓
 Volume Analysis
        ↓
 Confidence Scoring
        ↓
 Enriched Signal Output
```

## Input/Output Specification

### Input Schema

**Subscribes to**: `signals.normalized`

```json
{
  "corr_id": "req_abc123",
  "source": "tradingview",
  "instrument": "EURUSD",
  "price": 1.0945,
  "side": "buy",
  "strength": 0.75,
  "timestamp": "2024-01-15T10:30:00Z",
  "normalized_at": "2024-01-15T10:30:01Z"
}
```

### Output Schema

**Publishes to**: `signals.enriched.momentum`

```json
{
  "schema_version": "1.0.0",
  "agent_name": "momentum",
  "agent_version": "1.2.1",
  "corr_id": "req_abc123",
  "source_signal": {
    "instrument": "EURUSD",
    "price": 1.0945,
    "side": "buy",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "enriched_at": "2024-01-15T10:30:02.145Z",
  "analysis": {
    "momentum_strength": 0.78,
    "trend_direction": "bullish",
    "confidence": 0.82,
    "technical_indicators": {
      "ma_signal": "golden_cross",
      "ma_short": 1.0940,
      "ma_long": 1.0920,
      "rsi_value": 68.5,
      "rsi_signal": "neutral",
      "volume_ratio": 1.3,
      "volume_confirmation": true
    },
    "recommendation": {
      "action": "strong_buy",
      "priority": "high",
      "time_horizon": "short_term"
    }
  }
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MOMENTUM_LOOKBACK_PERIODS` | `20` | Historical periods for MA calculation |
| `MOMENTUM_MA_SHORT_PERIOD` | `10` | Short-term moving average period |
| `MOMENTUM_MA_LONG_PERIOD` | `20` | Long-term moving average period |
| `MOMENTUM_RSI_PERIOD` | `14` | RSI calculation period |
| `MOMENTUM_RSI_THRESHOLD_HIGH` | `70` | RSI overbought threshold |
| `MOMENTUM_RSI_THRESHOLD_LOW` | `30` | RSI oversold threshold |
| `MOMENTUM_VOLUME_LOOKBACK` | `10` | Periods for volume average |
| `MOMENTUM_MIN_CONFIDENCE` | `0.6` | Minimum confidence for signal emission |
| `MOMENTUM_CACHE_TTL_SECONDS` | `3600` | Historical data cache TTL |

### Sample Configuration

```bash
# Basic configuration
MOMENTUM_LOOKBACK_PERIODS=20
MOMENTUM_MIN_CONFIDENCE=0.65

# Aggressive momentum detection
MOMENTUM_MA_SHORT_PERIOD=5
MOMENTUM_MA_LONG_PERIOD=15
MOMENTUM_RSI_THRESHOLD_HIGH=75
MOMENTUM_RSI_THRESHOLD_LOW=25

# Conservative momentum detection
MOMENTUM_MA_SHORT_PERIOD=15
MOMENTUM_MA_LONG_PERIOD=30
MOMENTUM_MIN_CONFIDENCE=0.8
```

## Example Event Processing

### Bullish Momentum Detection

**Input Signal**:
```json
{
  "corr_id": "example_001",
  "instrument": "EURUSD",
  "price": 1.1000,
  "side": "buy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Historical Context**:
- Recent prices: [1.0950, 1.0960, 1.0970, 1.0980, 1.0990]
- MA(10): 1.0975
- MA(20): 1.0960
- RSI: 72
- Volume: 150% of average

**Analysis Logic**:
1. **MA Crossover**: Short MA (1.0975) > Long MA (1.0960) → Bullish
2. **Price vs MA**: Current price (1.1000) > Short MA → Uptrend
3. **RSI**: 72 > 70 → Overbought but still bullish
4. **Volume**: 1.5x average → Strong confirmation
5. **Confidence**: High volume + clear trend = 0.85

**Output Signal**:
```json
{
  "analysis": {
    "momentum_strength": 0.82,
    "trend_direction": "bullish",
    "confidence": 0.85,
    "technical_indicators": {
      "ma_signal": "bullish_trend",
      "rsi_signal": "overbought_bullish",
      "volume_confirmation": true
    },
    "recommendation": {
      "action": "strong_buy",
      "priority": "high"
    }
  }
}
```

### Bearish Momentum Detection

**Input Signal**:
```json
{
  "corr_id": "example_002",
  "instrument": "GBPUSD",
  "price": 1.2450,
  "side": "sell",
  "timestamp": "2024-01-15T14:22:00Z"
}
```

**Historical Context**:
- Recent prices: [1.2550, 1.2530, 1.2510, 1.2490, 1.2470]
- MA(10): 1.2510
- MA(20): 1.2530
- RSI: 28
- Volume: 200% of average

**Analysis Logic**:
1. **MA Crossover**: Short MA (1.2510) < Long MA (1.2530) → Bearish
2. **Price vs MA**: Current price (1.2450) < Short MA → Downtrend
3. **RSI**: 28 < 30 → Oversold but still bearish
4. **Volume**: 2.0x average → Very strong confirmation
5. **Confidence**: High volume + clear downtrend = 0.88

**Output Signal**:
```json
{
  "analysis": {
    "momentum_strength": 0.85,
    "trend_direction": "bearish",
    "confidence": 0.88,
    "technical_indicators": {
      "ma_signal": "death_cross",
      "rsi_signal": "oversold_bearish",
      "volume_confirmation": true
    },
    "recommendation": {
      "action": "strong_sell",
      "priority": "high"
    }
  }
}
```

### Sideways Market (No Signal)

**Input Signal**:
```json
{
  "corr_id": "example_003",
  "instrument": "USDJPY",
  "price": 110.25,
  "timestamp": "2024-01-15T16:45:00Z"
}
```

**Historical Context**:
- Recent prices: [110.20, 110.30, 110.15, 110.35, 110.22]
- MA(10): 110.24
- MA(20): 110.26
- RSI: 52
- Volume: 80% of average

**Analysis Logic**:
1. **MA Crossover**: MAs very close → No clear trend
2. **Price vs MA**: Price oscillating around MAs → Sideways
3. **RSI**: 52 → Neutral
4. **Volume**: Below average → Low conviction
5. **Confidence**: Low due to unclear signals = 0.35

**Result**: No signal emitted (below minimum confidence threshold)

## Algorithm Implementation Details

### Moving Average Calculation

```python
def calculate_moving_averages(self, prices: List[float]) -> Dict[str, float]:
    """Calculate short and long term moving averages."""
    if len(prices) < self.config.ma_long_period:
        return {'ma_short': None, 'ma_long': None}
    
    ma_short = sum(prices[-self.config.ma_short_period:]) / self.config.ma_short_period
    ma_long = sum(prices[-self.config.ma_long_period:]) / self.config.ma_long_period
    
    return {
        'ma_short': ma_short,
        'ma_long': ma_long,
        'crossover': self._detect_crossover(ma_short, ma_long)
    }

def _detect_crossover(self, ma_short: float, ma_long: float) -> str:
    """Detect moving average crossover patterns."""
    if ma_short > ma_long * 1.002:  # 0.2% threshold to avoid noise
        return 'golden_cross'
    elif ma_short < ma_long * 0.998:
        return 'death_cross'
    else:
        return 'neutral'
```

### RSI Calculation

```python
def calculate_rsi(self, prices: List[float]) -> Dict[str, float]:
    """Calculate Relative Strength Index."""
    if len(prices) < self.config.rsi_period + 1:
        return {'rsi': 50, 'signal': 'insufficient_data'}
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [max(0, delta) for delta in deltas]
    losses = [max(0, -delta) for delta in deltas]
    
    avg_gain = sum(gains[-self.config.rsi_period:]) / self.config.rsi_period
    avg_loss = sum(losses[-self.config.rsi_period:]) / self.config.rsi_period
    
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    return {
        'rsi': rsi,
        'signal': self._interpret_rsi(rsi)
    }

def _interpret_rsi(self, rsi: float) -> str:
    """Interpret RSI value for momentum signals."""
    if rsi >= self.config.rsi_threshold_high:
        return 'overbought'
    elif rsi <= self.config.rsi_threshold_low:
        return 'oversold'
    elif rsi > 55:
        return 'bullish'
    elif rsi < 45:
        return 'bearish'
    else:
        return 'neutral'
```

### Confidence Scoring

```python
def calculate_confidence(self, analysis: Dict) -> float:
    """Calculate overall signal confidence."""
    confidence_factors = []
    
    # MA signal strength
    ma_confidence = self._ma_confidence(analysis['ma_signal'], analysis['ma_separation'])
    confidence_factors.append(('ma', ma_confidence, 0.4))
    
    # RSI confirmation
    rsi_confidence = self._rsi_confidence(analysis['rsi_signal'])
    confidence_factors.append(('rsi', rsi_confidence, 0.3))
    
    # Volume confirmation
    volume_confidence = self._volume_confidence(analysis['volume_ratio'])
    confidence_factors.append(('volume', volume_confidence, 0.3))
    
    # Weighted average
    weighted_sum = sum(conf * weight for name, conf, weight in confidence_factors)
    total_weight = sum(weight for name, conf, weight in confidence_factors)
    
    return weighted_sum / total_weight
```

## Monitoring and Metrics

### Agent-Specific Metrics

- `momentum_signals_generated_total{direction}` - Signals by direction (bullish/bearish)
- `momentum_confidence_histogram` - Distribution of confidence scores
- `momentum_processing_time_seconds` - Time to analyze each signal
- `momentum_cache_hits_total` - Historical data cache performance
- `momentum_insufficient_data_total` - Signals skipped due to lack of history

### Health Indicators

- Average confidence score > 0.7
- Processing time p95 < 50ms
- Cache hit rate > 90%
- Signal generation rate aligned with market activity

### Alerting Thresholds

- **Critical**: No signals generated for 30+ minutes during market hours
- **Warning**: Average confidence < 0.6 for 1 hour
- **Info**: Cache hit rate < 80%

## Deployment and Scaling

### Resource Requirements

- **Memory**: 256MB baseline + 10MB per 10K cached price points
- **CPU**: 0.2 cores for 1K signals/second
- **Latency**: Target < 50ms processing time

### Scaling Configuration

```yaml
# Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: momentum-agent
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: momentum-agent
        image: trading/momentum-agent:1.2.1
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        env:
        - name: NATS_URL
          value: "nats://nats-cluster:4222"
        - name: MOMENTUM_MIN_CONFIDENCE
          value: "0.65"
```

### Horizontal Scaling

- Multiple instances process signals in parallel
- NATS durable consumers distribute load automatically
- Each instance maintains independent price history cache
- Stateless design enables easy scaling

## Development and Testing

### Running Locally

```bash
# Start dependencies
docker compose up -d nats

# Set environment variables
export NATS_URL=nats://localhost:4222
export MOMENTUM_MIN_CONFIDENCE=0.6

# Run agent
cd agents/momentum
python agent.py
```

### Testing

```bash
# Unit tests
pytest tests/test_momentum_logic.py

# Integration tests
pytest tests/test_momentum_integration.py

# Load testing
pytest tests/test_momentum_performance.py -m soak
```

### Configuration Tuning

1. **Low Latency Trading**:
   - Reduce MA periods (5/10)
   - Lower confidence threshold (0.5)
   - Increase processing frequency

2. **Conservative Signals**:
   - Increase MA periods (20/50)
   - Higher confidence threshold (0.8)
   - Require volume confirmation

3. **High Frequency Markets**:
   - Shorter cache TTL (900s)
   - Smaller lookback periods (10)
   - Dynamic thresholds based on volatility

---

**For implementation details, see [AGENT_TEMPLATE.md](../AGENT_TEMPLATE.md) and the momentum agent source code.**
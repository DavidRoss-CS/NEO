# Risk Agent

**Monitors position risk and exposure limits for trading signals.**

## Purpose

The risk agent analyzes normalized market signals to assess risk exposure and position limits. It evaluates potential position sizes, correlation risks, volatility impacts, and generates risk alerts. The agent ensures trading activities remain within defined risk parameters and helps prevent excessive exposure.

## Algorithm Overview

### Core Risk Components

1. **Position Size Validation**:
   - Maximum position size as percentage of capital
   - Instrument-specific position limits
   - Concentration risk assessment

2. **Correlation-Based Exposure**:
   - Cross-instrument correlation analysis
   - Portfolio-wide exposure calculation
   - Currency correlation clustering

3. **Volatility-Adjusted Sizing**:
   - Historical volatility calculation
   - Dynamic position sizing based on vol
   - Risk-adjusted returns estimation

4. **Real-Time Risk Monitoring**:
   - Drawdown tracking
   - VaR (Value at Risk) calculation
   - Stop-loss level recommendations

### Risk Assessment Flow

```
Normalized Signal Input
        ↓
Current Position Lookup
        ↓
Volatility Calculation
        ↓
Correlation Analysis
        ↓
Position Size Validation
        ↓
Risk Alert Generation
        ↓
Enriched Risk Signal Output
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

**Publishes to**: `signals.enriched.risk`

```json
{
  "schema_version": "1.0.0",
  "agent_name": "risk",
  "agent_version": "2.0.0",
  "corr_id": "req_abc123",
  "source_signal": {
    "instrument": "EURUSD",
    "price": 1.0945,
    "side": "buy",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "enriched_at": "2024-01-15T10:30:02.245Z",
  "analysis": {
    "risk_level": "medium",
    "overall_score": 0.65,
    "position_sizing": {
      "max_position_size": 10000,
      "recommended_size": 7500,
      "volatility_adjusted_size": 6800,
      "size_rationale": "reduced_due_to_high_volatility"
    },
    "exposure_analysis": {
      "current_exposure_pct": 0.15,
      "max_exposure_pct": 0.20,
      "currency_exposure": {
        "EUR": 0.12,
        "USD": -0.08
      },
      "correlation_risk": 0.45
    },
    "volatility_metrics": {
      "historical_vol_30d": 0.08,
      "current_vol_estimate": 0.12,
      "vol_percentile": 75,
      "vol_regime": "high"
    },
    "risk_alerts": [
      {
        "type": "exposure_warning",
        "severity": "medium",
        "message": "EUR exposure approaching 15% limit",
        "threshold": 0.20,
        "current": 0.15
      }
    ],
    "recommendations": {
      "action": "proceed_with_caution",
      "suggested_stop_loss": 1.0900,
      "max_risk_per_trade": 0.02,
      "position_duration": "short_term"
    }
  }
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RISK_MAX_POSITION_PCT` | `0.05` | Maximum position size as % of capital |
| `RISK_MAX_EXPOSURE_PCT` | `0.20` | Maximum exposure per currency/sector |
| `RISK_MAX_CORRELATION` | `0.70` | Maximum correlation between positions |
| `RISK_VOLATILITY_WINDOW` | `30` | Days for volatility calculation |
| `RISK_VAR_CONFIDENCE` | `0.95` | VaR confidence level |
| `RISK_ALERT_THRESHOLDS` | `{"low":0.3,"medium":0.6,"high":0.8}` | Risk level thresholds |
| `RISK_POSITION_CACHE_TTL` | `300` | Position cache TTL in seconds |
| `RISK_ENABLE_DYNAMIC_SIZING` | `true` | Enable volatility-adjusted sizing |
| `RISK_MIN_LIQUIDITY_SCORE` | `0.7` | Minimum liquidity requirement |

### Sample Configuration Profiles

**Conservative Profile**:
```bash
RISK_MAX_POSITION_PCT=0.02
RISK_MAX_EXPOSURE_PCT=0.10
RISK_MAX_CORRELATION=0.50
RISK_VAR_CONFIDENCE=0.99
```

**Aggressive Profile**:
```bash
RISK_MAX_POSITION_PCT=0.10
RISK_MAX_EXPOSURE_PCT=0.30
RISK_MAX_CORRELATION=0.85
RISK_VAR_CONFIDENCE=0.90
```

**Scalping Profile**:
```bash
RISK_MAX_POSITION_PCT=0.01
RISK_VOLATILITY_WINDOW=5
RISK_POSITION_CACHE_TTL=60
```

## Example Risk Assessments

### Low Risk Signal

**Input Signal**:
```json
{
  "corr_id": "risk_example_001",
  "instrument": "EURUSD",
  "price": 1.0945,
  "side": "buy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Risk Context**:
- Current EUR exposure: 5%
- Historical volatility: 6% (low)
- Correlation with existing positions: 0.3
- Liquidity score: 0.95 (excellent)

**Risk Analysis**:
1. **Position Size**: 5% of capital allowed
2. **Exposure**: Well within 20% limit
3. **Volatility**: Low vol allows larger size
4. **Correlation**: Low correlation reduces portfolio risk

**Output**:
```json
{
  "analysis": {
    "risk_level": "low",
    "overall_score": 0.25,
    "position_sizing": {
      "max_position_size": 50000,
      "recommended_size": 45000,
      "size_rationale": "favorable_conditions"
    },
    "risk_alerts": [],
    "recommendations": {
      "action": "proceed",
      "max_risk_per_trade": 0.05
    }
  }
}
```

### High Risk Signal

**Input Signal**:
```json
{
  "corr_id": "risk_example_002",
  "instrument": "GBPJPY",
  "price": 185.50,
  "side": "buy",
  "timestamp": "2024-01-15T16:45:00Z"
}
```

**Risk Context**:
- Current GBP exposure: 18%
- Historical volatility: 15% (very high)
- Correlation with existing GBP positions: 0.8
- Recent drawdown: 8%

**Risk Analysis**:
1. **Position Size**: Reduced due to high volatility
2. **Exposure**: Approaching GBP limit
3. **Correlation**: High correlation increases risk
4. **Volatility**: Extreme vol requires smaller position

**Output**:
```json
{
  "analysis": {
    "risk_level": "high",
    "overall_score": 0.85,
    "position_sizing": {
      "max_position_size": 10000,
      "recommended_size": 3000,
      "volatility_adjusted_size": 2500,
      "size_rationale": "high_volatility_and_correlation"
    },
    "risk_alerts": [
      {
        "type": "high_volatility",
        "severity": "high",
        "message": "GBPJPY volatility at 90th percentile"
      },
      {
        "type": "exposure_limit",
        "severity": "medium",
        "message": "GBP exposure near 20% limit"
      }
    ],
    "recommendations": {
      "action": "reduce_size_or_skip",
      "suggested_stop_loss": 182.00,
      "max_risk_per_trade": 0.01
    }
  }
}
```

### Blocked Signal

**Input Signal**:
```json
{
  "corr_id": "risk_example_003",
  "instrument": "USDCHF",
  "price": 0.9125,
  "side": "sell",
  "timestamp": "2024-01-15T20:15:00Z"
}
```

**Risk Context**:
- Current USD exposure: 22% (over limit)
- Daily loss limit reached: -5%
- Market hours: After regular trading (low liquidity)
- VaR exceeded: 105% of daily limit

**Risk Analysis**:
1. **Exposure**: Over maximum USD exposure
2. **Daily Loss**: Loss limit already reached
3. **Liquidity**: Poor execution conditions
4. **VaR**: Risk budget exhausted

**Output**:
```json
{
  "analysis": {
    "risk_level": "blocked",
    "overall_score": 1.0,
    "position_sizing": {
      "max_position_size": 0,
      "recommended_size": 0,
      "size_rationale": "risk_limits_exceeded"
    },
    "risk_alerts": [
      {
        "type": "exposure_exceeded",
        "severity": "critical",
        "message": "USD exposure 22% exceeds 20% limit"
      },
      {
        "type": "daily_loss_limit",
        "severity": "critical",
        "message": "Daily loss limit of -5% reached"
      },
      {
        "type": "low_liquidity",
        "severity": "high",
        "message": "Trading outside regular hours"
      }
    ],
    "recommendations": {
      "action": "block_trade",
      "reason": "multiple_risk_limits_exceeded",
      "next_review": "2024-01-16T09:00:00Z"
    }
  }
}
```

## Algorithm Implementation Details

### Volatility Calculation

```python
def calculate_volatility(self, prices: List[float], window: int = 30) -> Dict:
    """Calculate historical volatility and current regime."""
    if len(prices) < window:
        return {'vol': 0.10, 'regime': 'unknown'}
    
    # Calculate returns
    returns = [(prices[i] / prices[i-1] - 1) for i in range(1, len(prices))]
    
    # Rolling volatility
    vol_window = returns[-window:]
    volatility = np.std(vol_window) * np.sqrt(252)  # Annualized
    
    # Volatility regime classification
    vol_percentiles = np.percentile(returns[-252:], [25, 50, 75])  # 1 year
    
    if volatility < vol_percentiles[0]:
        regime = 'low'
    elif volatility < vol_percentiles[1]:
        regime = 'normal'
    elif volatility < vol_percentiles[2]:
        regime = 'high'
    else:
        regime = 'extreme'
    
    return {
        'volatility': volatility,
        'regime': regime,
        'percentile': self._calculate_percentile(volatility, returns)
    }
```

### Position Sizing Algorithm

```python
def calculate_position_size(self, signal: Dict, risk_metrics: Dict) -> Dict:
    """Calculate risk-adjusted position size."""
    base_capital = self.get_available_capital()
    
    # Base position size (% of capital)
    base_size = base_capital * self.config.max_position_pct
    
    # Volatility adjustment
    vol_multiplier = self._volatility_adjustment(risk_metrics['volatility'])
    vol_adjusted_size = base_size * vol_multiplier
    
    # Correlation adjustment
    corr_multiplier = self._correlation_adjustment(signal['instrument'])
    corr_adjusted_size = vol_adjusted_size * corr_multiplier
    
    # Exposure limit check
    exposure_adjusted_size = self._apply_exposure_limits(
        signal['instrument'], corr_adjusted_size
    )
    
    # Liquidity adjustment
    final_size = self._apply_liquidity_constraints(
        signal['instrument'], exposure_adjusted_size
    )
    
    return {
        'base_size': base_size,
        'volatility_adjusted': vol_adjusted_size,
        'correlation_adjusted': corr_adjusted_size,
        'exposure_adjusted': exposure_adjusted_size,
        'final_size': final_size,
        'adjustments': {
            'volatility_multiplier': vol_multiplier,
            'correlation_multiplier': corr_multiplier
        }
    }

def _volatility_adjustment(self, volatility: float) -> float:
    """Adjust position size based on volatility."""
    # Target volatility (e.g., 10% annualized)
    target_vol = 0.10
    
    # Inverse relationship: higher vol = smaller position
    multiplier = min(target_vol / volatility, 2.0)  # Cap at 2x
    return max(multiplier, 0.1)  # Minimum 10% of base size
```

### Correlation Analysis

```python
def analyze_correlations(self, instrument: str) -> Dict:
    """Analyze correlation with existing positions."""
    current_positions = self.get_current_positions()
    
    if not current_positions:
        return {'max_correlation': 0, 'correlated_instruments': []}
    
    correlations = []
    for position in current_positions:
        corr = self.get_correlation(instrument, position['instrument'])
        correlations.append({
            'instrument': position['instrument'],
            'correlation': corr,
            'position_size': position['size']
        })
    
    max_correlation = max(c['correlation'] for c in correlations)
    
    # Calculate portfolio correlation risk
    portfolio_correlation = self._calculate_portfolio_correlation(
        instrument, correlations
    )
    
    return {
        'max_correlation': max_correlation,
        'portfolio_correlation': portfolio_correlation,
        'correlated_instruments': [
            c for c in correlations if c['correlation'] > 0.5
        ]
    }
```

### Risk Alert System

```python
def generate_risk_alerts(self, signal: Dict, analysis: Dict) -> List[Dict]:
    """Generate risk alerts based on current conditions."""
    alerts = []
    
    # Exposure alerts
    exposure = analysis['exposure_analysis']
    if exposure['current_exposure_pct'] > self.config.max_exposure_pct * 0.8:
        alerts.append({
            'type': 'exposure_warning',
            'severity': 'medium',
            'message': f"Exposure approaching {self.config.max_exposure_pct*100}% limit",
            'current': exposure['current_exposure_pct'],
            'threshold': self.config.max_exposure_pct
        })
    
    # Volatility alerts
    vol_metrics = analysis['volatility_metrics']
    if vol_metrics['vol_percentile'] > 90:
        alerts.append({
            'type': 'high_volatility',
            'severity': 'high',
            'message': f"{signal['instrument']} volatility at {vol_metrics['vol_percentile']}th percentile",
            'current_vol': vol_metrics['current_vol_estimate']
        })
    
    # Correlation alerts
    if analysis['exposure_analysis']['correlation_risk'] > self.config.max_correlation:
        alerts.append({
            'type': 'high_correlation',
            'severity': 'medium',
            'message': f"High correlation with existing positions",
            'correlation': analysis['exposure_analysis']['correlation_risk']
        })
    
    # Daily loss alerts
    daily_pnl = self.get_daily_pnl()
    if daily_pnl < -0.05:  # -5% daily loss
        alerts.append({
            'type': 'daily_loss_limit',
            'severity': 'critical',
            'message': f"Daily loss limit exceeded: {daily_pnl:.1%}",
            'current_pnl': daily_pnl
        })
    
    return alerts
```

## Monitoring and Metrics

### Agent-Specific Metrics

- `risk_assessments_total{level}` - Risk assessments by level (low/medium/high/blocked)
- `risk_alerts_generated_total{type, severity}` - Risk alerts by type and severity
- `position_size_adjustments_total{reason}` - Position size adjustments by reason
- `risk_processing_time_seconds` - Risk calculation latency
- `portfolio_exposure_pct{currency}` - Current exposure by currency
- `volatility_regime_duration_seconds{regime}` - Time in each volatility regime

### Portfolio Risk Metrics

- `portfolio_var_estimate` - Current Value at Risk estimate
- `portfolio_correlation_score` - Overall portfolio correlation
- `daily_pnl_pct` - Current daily P&L percentage
- `max_drawdown_pct` - Maximum drawdown from peak

### Health Indicators

- Risk calculations complete within 100ms
- Alert response time < 5 seconds
- Position data freshness < 30 seconds
- Risk model accuracy > 85%

### Alerting Rules

- **Critical**: Daily loss > -5% or exposure > 25%
- **High**: VaR > 110% of limit or correlation > 0.85
- **Medium**: Multiple medium-severity alerts within 1 hour
- **Info**: New risk regime detected

## Deployment and Integration

### Resource Requirements

- **Memory**: 512MB baseline + 50MB per 1K active positions
- **CPU**: 0.3 cores for 1K risk assessments/second
- **Latency**: Target < 100ms for risk calculation
- **Data**: Real-time position feeds and market data

### External Dependencies

- **Position Service**: Current position and P&L data
- **Market Data**: Price history and volatility data
- **Reference Data**: Instrument correlations and specifications
- **Configuration Service**: Risk limits and parameters

### Integration Points

```python
# Position service integration
class PositionService:
    async def get_current_positions(self) -> List[Dict]:
        """Fetch current portfolio positions."""
        pass
    
    async def get_daily_pnl(self) -> float:
        """Get current daily P&L percentage."""
        pass

# Market data integration
class MarketDataService:
    async def get_price_history(self, instrument: str, periods: int) -> List[float]:
        """Fetch historical prices for volatility calculation."""
        pass
    
    async def get_correlation_matrix(self, instruments: List[str]) -> Dict:
        """Get correlation matrix for instruments."""
        pass
```

### Configuration Management

```yaml
# Risk limits configuration
risk_limits:
  position_limits:
    max_position_pct: 0.05
    max_exposure_pct: 0.20
    max_correlation: 0.70
  
  loss_limits:
    daily_loss_pct: -0.05
    weekly_loss_pct: -0.15
    monthly_loss_pct: -0.25
  
  volatility_adjustments:
    target_volatility: 0.10
    min_multiplier: 0.1
    max_multiplier: 2.0
  
  alert_thresholds:
    exposure_warning: 0.8
    volatility_percentile: 90
    correlation_warning: 0.6
```

---

**For implementation details, see [AGENT_TEMPLATE.md](../AGENT_TEMPLATE.md) and the risk agent source code.**
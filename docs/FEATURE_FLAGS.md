# Feature Flags Configuration

This document defines the feature flags used in the NEO trading system for safe rollout of new functionality and A/B testing.

## Overview

Feature flags allow us to:
- Deploy code with features disabled by default
- Enable features gradually for specific environments or users
- Quickly disable problematic features without code deployment
- Test new functionality with a subset of signals/agents

## Flag Definitions

### Core System Flags

#### `FF_TV_SLICE` - TradingView Signal Processing
- **Default**: `false`
- **Purpose**: Enable enhanced TradingView webhook processing with intelligent categorization
- **Components**: at-gateway signal normalization, strength scoring, deduplication
- **Rollout**: Enable in dev → staging → production

#### `FF_AGENT_GPT` - GPT Agent Integration
- **Default**: `false`
- **Purpose**: Enable GPT-4/Claude agents via MCP for signal analysis
- **Components**: at-agent-orchestrator, MCP tool integration, context persistence
- **Rollout**: Enable per agent type, monitor token usage and costs

#### `FF_OUTPUT_SLACK` - Slack Notifications
- **Default**: `false`
- **Purpose**: Enable Slack webhook notifications for agent outputs
- **Components**: at-output-manager Slack adapter, message formatting
- **Rollout**: Enable for test channels first, then production channels

#### `FF_OUTPUT_TELEGRAM` - Telegram Notifications
- **Default**: `false`
- **Purpose**: Enable Telegram bot notifications for trading alerts
- **Components**: at-output-manager Telegram adapter, bot API integration
- **Rollout**: Private channels first, then broader distribution

#### `FF_EXEC_PAPER` - Paper Trading Execution
- **Default**: `true`
- **Purpose**: Enable paper trading execution for agent recommendations
- **Components**: at-exec-sim paper trading engine, portfolio simulation
- **Rollout**: Should remain enabled for testing and development

#### `FF_EXEC_LIVE` - Live Trading Execution
- **Default**: `false`
- **Purpose**: Enable live trading execution with real money
- **Components**: at-broker-adapters, real broker connections
- **Rollout**: Extreme caution, small position sizes initially

### Development and Testing Flags

#### `FF_ENHANCED_LOGGING` - Verbose Logging
- **Default**: `false`
- **Purpose**: Enable detailed debug logging for troubleshooting
- **Components**: All services with enhanced log verbosity
- **Impact**: Increased log volume, potential performance impact

#### `FF_MOCK_EXTERNAL_APIS` - Mock Mode
- **Default**: `false`
- **Purpose**: Replace external API calls with mocks for testing
- **Components**: Slack, Telegram, broker APIs replaced with mocks
- **Use**: Development and testing environments only

#### `FF_FAST_MODE` - Accelerated Processing
- **Default**: `false`
- **Purpose**: Reduce timeouts and delays for faster testing
- **Components**: Reduced debounce windows, shorter retry delays
- **Use**: Unit tests and development only

### Performance and Reliability Flags

#### `FF_CIRCUIT_BREAKER` - Circuit Breaker Protection
- **Default**: `true`
- **Purpose**: Enable circuit breakers for external service calls
- **Components**: All services with external dependencies
- **Behavior**: Auto-disable failing services, gradual recovery

#### `FF_RATE_LIMITING` - Rate Limiting
- **Default**: `true`
- **Purpose**: Enable rate limiting for API calls and message processing
- **Components**: at-gateway, at-agent-orchestrator, at-output-manager
- **Behavior**: Throttle excessive requests, prevent API abuse

#### `FF_METRICS_COLLECTION` - Enhanced Metrics
- **Default**: `true`
- **Purpose**: Enable detailed Prometheus metrics collection
- **Components**: All services with business logic metrics
- **Impact**: Slight performance overhead for comprehensive monitoring

### Experimental Features

#### `FF_ML_SIGNAL_SCORING` - ML-Based Signal Scoring
- **Default**: `false`
- **Purpose**: Use ML models to score signal strength and confidence
- **Components**: at-gateway with TensorFlow/PyTorch integration
- **Status**: Experimental, heavy resource usage

#### `FF_SENTIMENT_ANALYSIS` - News Sentiment Analysis
- **Default**: `false`
- **Purpose**: Integrate news sentiment into trading decisions
- **Components**: at-agent-orchestrator with news API integration
- **Status**: Experimental, external data dependency

## Configuration Management

### Environment Variables

Feature flags are configured via environment variables:

```bash
# Core flags
export FF_TV_SLICE=true
export FF_AGENT_GPT=false
export FF_OUTPUT_SLACK=false
export FF_EXEC_PAPER=true

# Development flags
export FF_ENHANCED_LOGGING=true
export FF_MOCK_EXTERNAL_APIS=true
```

### Docker Compose Configuration

```yaml
# docker-compose.minimal.yml
environment:
  - FF_TV_SLICE=true
  - FF_EXEC_PAPER=true
  - FF_ENHANCED_LOGGING=${FF_ENHANCED_LOGGING:-false}

# docker-compose.production.yml
environment:
  - FF_TV_SLICE=true
  - FF_AGENT_GPT=true
  - FF_OUTPUT_SLACK=true
  - FF_EXEC_PAPER=true
  - FF_CIRCUIT_BREAKER=true
```

### Runtime Configuration

Feature flags can be modified at runtime through:

1. **Environment variable updates** (requires service restart)
2. **Configuration API** (future enhancement)
3. **Admin dashboard** (future enhancement)

## Flag Lifecycle

### Development Phase
1. **Create flag** with `false` default
2. **Implement feature** behind flag
3. **Add unit tests** for both enabled/disabled states
4. **Test in development** environment

### Rollout Phase
1. **Enable in staging** environment
2. **Run integration tests** with flag enabled
3. **Monitor metrics** and error rates
4. **Gradual production** rollout

### Cleanup Phase
1. **Monitor flag usage** for 30+ days
2. **Confirm stability** with flag permanently enabled
3. **Remove flag** and simplify code
4. **Update documentation**

## Monitoring and Alerting

### Metrics to Track
- `feature_flag_enabled{flag_name}` - Flag status per service
- `feature_flag_evaluation_total{flag_name, result}` - Flag evaluation count
- `feature_flag_error_total{flag_name}` - Flag evaluation errors

### Alerts
- Flag evaluation errors above threshold
- Unexpected flag state changes
- Performance degradation when flags enabled
- High error rates correlated with flag changes

## Best Practices

### Flag Naming
- Use descriptive prefixes: `FF_` for feature flags
- Include component context: `FF_OUTPUT_SLACK` vs `FF_SLACK`
- Use consistent naming patterns across related flags

### Implementation
- Check flags close to feature code, not at service startup
- Provide meaningful default values for all environments
- Log flag evaluations for debugging (at DEBUG level)
- Keep flag logic simple - avoid complex conditional chains

### Testing
- Test both enabled and disabled states in CI
- Include flag state in test fixtures
- Use flags to enable/disable expensive tests
- Mock flag values in unit tests for predictability

### Rollout Strategy
- Start with internal/development environments
- Use canary deployments with flags enabled for small traffic percentage
- Monitor business metrics closely during rollouts
- Have rollback plans ready (disable flag immediately)

## Flag Status Dashboard

| Flag | Production | Staging | Development | Rollout Date | Cleanup Target |
|------|------------|---------|-------------|--------------|----------------|
| FF_TV_SLICE | ✅ true | ✅ true | ✅ true | 2025-09-24 | 2025-12-01 |
| FF_AGENT_GPT | ❌ false | ✅ true | ✅ true | - | TBD |
| FF_OUTPUT_SLACK | ❌ false | ✅ true | ✅ true | - | TBD |
| FF_EXEC_PAPER | ✅ true | ✅ true | ✅ true | 2025-09-24 | Permanent |
| FF_EXEC_LIVE | ❌ false | ❌ false | ❌ false | - | TBD |

---

**Version**: 1.0.0
**Last Updated**: 2025-09-24
**Maintainer**: NEO Platform Team
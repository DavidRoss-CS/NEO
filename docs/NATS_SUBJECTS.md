# NATS Subject Taxonomy v1

This document defines the NATS subject hierarchy used in the NEO trading system for message routing and organization.

## Subject Structure

All subjects follow a hierarchical dot-notation format designed for efficient routing and filtering:

```
{domain}.{category}.{priority}.{instrument}.{type}
```

## Core Subject Categories

### 1. Signals - Market Data and Trading Signals

**Format**: `signals.{subcategory}.{priority}.{instrument}.{type}`

#### Raw Signals
- `signals.raw` - Unprocessed webhook payloads
- Used for: Raw TradingView alerts, manual signals, backtest data

#### Normalized Signals
- `signals.normalized.{priority}.{instrument}.{type}`
- **Priority**: `high` | `std` (standard)
- **Instrument**: `BTCUSD`, `ETHUSD`, `ES1!`, etc.
- **Type**: `momentum`, `breakout`, `indicator`, `sentiment`, `custom`

**Examples**:
```
signals.normalized.std.BTCUSD.momentum
signals.normalized.high.ES1!.breakout
signals.normalized.std.ETHUSD.sentiment
```

### 2. Intents - Agent Execution Requests

**Format**: `intents.{subcategory}.{agent}`

- `intents.agent_run.{agent}` - Request to run specific agent
- **Agent**: `mcp_gpt_trend`, `momentum_scanner`, `risk_monitor`

**Examples**:
```
intents.agent_run.mcp_gpt_trend
intents.agent_run.momentum_scanner
```

### 3. Decisions - Agent Analysis Results

**Format**: `decisions.{subcategory}.{agent}.{severity}`

- `decisions.agent_output.{agent}.{severity}`
- **Agent**: Agent identifier
- **Severity**: `info`, `warn`, `critical`

**Examples**:
```
decisions.agent_output.mcp_gpt_trend.info
decisions.agent_output.risk_monitor.critical
decisions.agent_output.momentum_scanner.warn
```

### 4. Outputs - External Deliveries

**Format**: `outputs.{destination}.{channel}`

#### Notifications
- `outputs.notification.{channel}`
- **Channel**: `slack`, `telegram`, `discord`, `email`, `sms`

#### Execution
- `outputs.execution.{venue}`
- **Venue**: `paper`, `live`, `sim`, `backtest`

**Examples**:
```
outputs.notification.slack
outputs.notification.telegram
outputs.execution.paper
outputs.execution.live
```

### 5. Executions - Trade Confirmations

**Format**: `executions.{type}.{venue}.{status}`

- `executions.fill.{venue}.{status}`
- **Venue**: `paper`, `ib`, `alpaca`, `sim`
- **Status**: `filled`, `partial`, `rejected`, `canceled`

**Examples**:
```
executions.fill.paper.filled
executions.fill.ib.partial
executions.fill.alpaca.rejected
```

### 6. Audit - System Events

**Format**: `audit.{category}`

- `audit.events` - All audit events
- `audit.compliance` - Regulatory compliance events
- `audit.errors` - Error tracking
- `audit.metrics` - Performance metrics

### 7. Dead Letter Queue (DLQ)

**Format**: `dlq.{original_subject}`

Failed messages are routed to DLQ with original subject preserved:
```
dlq.signals.normalized.std.BTCUSD.momentum
dlq.decisions.agent_output.mcp_gpt_trend.info
```

## Subject Patterns for Subscriptions

### Wildcards
- `*` matches exactly one token
- `>` matches one or more tokens (must be at end)

### Common Subscription Patterns

```bash
# All normalized signals
signals.normalized.*

# All BTC signals regardless of type
signals.normalized.*.BTCUSD.*

# All high-priority signals
signals.normalized.high.*

# All agent outputs
decisions.agent_output.*

# Specific agent outputs
decisions.agent_output.mcp_gpt_trend.*

# All notifications
outputs.notification.*

# All executions
executions.*

# Everything (use with caution)
>
```

## Message Headers

Standard headers should be included with all messages:

```json
{
  "Corr-ID": "correlation_id",
  "Source": "signal_source",
  "Agent-ID": "agent_identifier",
  "Instrument": "BTCUSD",
  "Strategy": "strategy_name",
  "Priority": "high|standard",
  "Nats-Msg-Id": "unique_message_id"
}
```

## JetStream Configuration

### Stream: `trading-events`
- **Subjects**: `signals.*, decisions.*, outputs.*, executions.*, audit.*`
- **Retention**: Limits-based, 7 days
- **Storage**: File-based
- **Replicas**: 1 (single node)
- **Max Messages**: 1,000,000
- **Max Age**: 7 days

### Consumer Configuration
- **Ack Policy**: Explicit acknowledgment required
- **Max Deliver**: 3 attempts before DLQ
- **Ack Wait**: 30 seconds
- **Replay Policy**: Instant (new messages only)

## Best Practices

### 1. Subject Design
- Keep subjects descriptive but concise
- Use consistent naming conventions
- Avoid deep nesting (max 5 levels)
- Use uppercase for instruments (`BTCUSD`, not `btcusd`)

### 2. Message Flow
- Always include correlation IDs for tracing
- Use appropriate priority levels (`high` for urgent signals)
- Include all relevant headers for filtering
- Set message expiration for time-sensitive data

### 3. Error Handling
- Monitor DLQ subjects for failed messages
- Implement retry logic with exponential backoff
- Log all message processing errors with correlation IDs
- Set up alerts for DLQ message accumulation

### 4. Performance
- Use specific subjects for subscriptions (avoid `>`)
- Implement consumer groups for load balancing
- Set appropriate batch sizes for bulk operations
- Monitor stream lag and consumer performance

## Migration and Evolution

### Adding New Subjects
1. Document the new subject pattern
2. Update this taxonomy document
3. Add to JetStream stream configuration
4. Test with sample messages before production use

### Deprecating Subjects
1. Announce deprecation with 2-sprint notice
2. Dual-publish during transition period
3. Monitor for zero traffic before removal
4. Update documentation and consumer code

---

**Version**: 1.0.0
**Last Updated**: 2025-09-24
**Maintainer**: NEO Platform Team
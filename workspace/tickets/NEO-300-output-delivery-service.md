# NEO-300: Output Delivery Service Implementation

**Phase**: 3 - Output Delivery
**Priority**: CRITICAL
**Status**: 🔄 IN_PROGRESS
**Assignee**: Claude
**Created**: 2025-09-24

## Scope

Implement the output delivery service that manages multi-channel notifications and paper trading execution based on agent decisions.

### Files to Create
- `repos/at-output-manager/` (new service directory)
- `repos/at-output-manager/at_output_manager/app.py`
- `repos/at-output-manager/at_output_manager/slack_adapter.py`
- `repos/at-output-manager/at_output_manager/telegram_adapter.py`
- `repos/at-output-manager/at_output_manager/paper_trader.py`
- `repos/at-output-manager/at_output_manager/notification_formatter.py`
- `repos/at-output-manager/requirements.txt`
- `repos/at-output-manager/Dockerfile`
- `repos/at-output-manager/tests/`

### Technical Requirements
- FastAPI service on port 8008
- NATS subscription to `decisions.agent_output.*`
- NATS publishing to `outputs.notification.*` and `outputs.execution.*`
- Slack webhook integration (FF_OUTPUT_SLACK)
- Telegram bot integration (FF_OUTPUT_TELEGRAM)
- Paper trading execution with simulation
- Message formatting and templating
- Delivery confirmation tracking

## Definition of Done

### Functional Requirements
- [ ] Service subscribes to agent decision events
- [ ] Formats agent outputs into human-readable notifications
- [ ] Delivers notifications to Slack channels
- [ ] Delivers notifications via Telegram bot
- [ ] Executes paper trades based on agent orders
- [ ] Tracks delivery status and confirmations
- [ ] Provides delivery analytics and metrics

### Technical Requirements
- [ ] Docker container builds and runs
- [ ] Integration with Phase 0 schema registry
- [ ] Feature flags for channel control (FF_OUTPUT_SLACK, FF_OUTPUT_TELEGRAM)
- [ ] Error handling with delivery retry logic
- [ ] Comprehensive logging with correlation IDs
- [ ] Prometheus metrics for delivery success rates

### Testing Requirements
- [ ] Unit tests for all delivery adapters
- [ ] Notification formatting tests
- [ ] Paper trading execution tests
- [ ] End-to-end delivery workflow tests
- [ ] Delivery failure and retry testing

## Implementation Steps

1. Create service directory structure
2. Implement FastAPI application with NATS integration
3. Build Slack webhook adapter with formatting
4. Build Telegram bot adapter with rich messages
5. Implement paper trading execution logic
6. Add notification formatting and templating
7. Create comprehensive test suite
8. Add Docker configuration
9. Update docker-compose files

## Dependencies

- Phase 0: Schema registry (✅ Complete)
- Phase 1: Enhanced gateway (✅ Complete)
- Phase 2: Agent orchestrator (✅ Complete)
- Slack webhook configuration
- Telegram bot token and configuration

## Integration Points

### Input Sources
- `decisions.agent_output.{agent}.{severity}` from agent orchestrator
- Manual notification triggers via REST API

### Output Destinations
- `outputs.notification.slack`
- `outputs.notification.telegram`
- `outputs.execution.paper`
- `audit.events` for delivery activity logging

### External Services
- Slack webhook API for channel notifications
- Telegram Bot API for message delivery
- Paper trading simulation engine

## Success Criteria

- Agent decisions automatically trigger relevant notifications
- Slack channels receive formatted trading alerts
- Telegram delivers rich trading notifications
- Paper trades execute based on agent orders
- Performance SLO: Notification delivery within 2 seconds P95
- Zero message loss with proper error handling

## Message Templates

### Slack Notification Format
```
🚨 Trading Signal Alert
📊 Instrument: BTCUSD
📈 Signal: Momentum Bullish
💪 Confidence: 85%
💰 Suggested Order: BUY 0.1 BTC @ $45,000
🤖 Agent: GPT Trend Analyzer
⏰ Time: 2025-09-24 10:30:00 UTC
```

### Telegram Notification Format
```
🎯 NEO Trading Alert

📊 **Instrument**: BTCUSD
📈 **Signal**: Momentum Bullish
💪 **Confidence**: 85%

💰 **Suggested Trade**:
   • BUY 0.1 BTC @ $45,000
   • Expected P&L: +2.5%

🤖 **Agent**: GPT Trend Analyzer
📋 **Reasoning**: Strong momentum indicators with RSI oversold
⏰ **Time**: 2025-09-24 10:30:00 UTC
```

## Rollback Procedure

```bash
# Stop new service
docker-compose stop output-manager
# Remove from compose files
git checkout HEAD -- docker-compose*.yml
# Remove service directory
rm -rf repos/at-output-manager/
```

## Notes

- This service is the final piece connecting AI analysis to actionable outputs
- Notification formatting is critical for user experience
- Paper trading provides safe execution environment
- Feature flags enable gradual channel rollout
- Delivery confirmation prevents silent failures

**Last Updated**: 2025-09-24
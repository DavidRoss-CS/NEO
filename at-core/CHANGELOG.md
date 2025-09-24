# at-core schemas — CHANGELOG

All notable changes to NEO message schemas and validation utilities will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-09-24 - Phase 0 Foundation

### Added

#### Schemas
- **SignalEventV1.json**: Normalized trading signals from TradingView, webhooks, backtests
  - Required fields: schema_version, intent_id, correlation_id, source, instrument, type, strength, payload, ts_iso
  - Signal types: momentum, breakout, indicator, sentiment, custom
  - Priority levels: high, standard
  - Source types: tradingview, webhook, backtest, manual

- **AgentOutputV1.json**: GPT agent analysis results and trading recommendations
  - Required fields: schema_version, intent_id, agent, confidence, summary, recommendation, rationale, risk, metadata, ts_iso
  - Recommendation actions: none, analyze, alert, paper_order, live_order
  - Embedded OrderIntentEmbed for direct order specifications
  - Risk management fields: max_drawdown_pct, stop_loss, take_profit

- **OrderIntentV1.json**: Trading order specifications for execution
  - Required fields: schema_version, order_id, intent_id, account, instrument, side, qty, type, time_in_force, ts_iso
  - Order types: market, limit
  - Time in force: day, gtc, ioc, fok
  - Optional: limit_price, stop_loss, take_profit

#### Validation Infrastructure
- **Schema loading utilities**: Cached loading with error handling
- **Validation functions**: Strict and non-strict validation modes
- **Convenience validators**: Type-specific validation functions
- **Version detection**: Auto-detect schema type from payload
- **Error handling**: Clear error messages with payload snippets

### Technical Details
- All schemas use JSONSchema Draft 2020-12
- Schema IDs follow NEO convention: `https://neo.at-core/schemas/{SchemaName}.json`
- Caching implemented for performance in high-throughput scenarios
- Structured logging for validation failures
- Support for schema evolution with version checking

### Migration Notes
- This is the initial release - no migration needed
- All message producers should include `schema_version: "1.0.0"`
- Use strict validation in production, non-strict for development/testing

## [Unreleased]

### Planned
- SignalEventV2 with enhanced metadata fields
- Support for crypto futures and options instruments
- Agent confidence scoring improvements
- Order intent validation with broker-specific fields
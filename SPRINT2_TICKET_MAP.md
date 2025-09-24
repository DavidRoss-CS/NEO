# Sprint 2 Ticket Map

**Sprint Goal**: Multi-agent orchestration, risk management, and production readiness

## BLOCKER Priority (Must complete first)

### T-2001: Meta-agent Service (at-meta-agent) MVP
**Scope**: Core orchestration service for multi-agent coordination
- [ ] Consume `signals.normalized` from NATS
- [ ] Subscribe to `decisions.order_intent` from all agents
- [ ] Implement consensus/voting logic for conflicting decisions
- [ ] Emit `decisions.meta` with coordinated actions
- [ ] gRPC/HTTP control plane: pause/resume strategies, risk overrides
- [ ] Metrics: `meta_coordinations_total`, `meta_latency_seconds`, `meta_overrides_total`
**Estimate**: 5 days

### T-2002: Portfolio Risk Engine
**Scope**: Global risk management across all positions
- [ ] Real-time position and exposure tracking
- [ ] Implement risk rules:
  - Max daily loss limits
  - Per-instrument position caps
  - Correlation bucket limits
  - Emergency kill-switch
- [ ] Emit `risk.violations` events
- [ ] Block dangerous `decisions.order_intent`
- [ ] Risk dashboard in Grafana
**Estimate**: 4 days

### T-2003: Backtesting Harness (at-backtester)
**Scope**: Historical strategy validation framework
- [ ] Replay historical data through NATS subjects
- [ ] Deterministic seeding for reproducible tests
- [ ] JSON fixture support for unit testing
- [ ] Results publication to `backtest.results`
- [ ] Performance metrics and P&L calculation
- [ ] CSV/Parquet export for analysis
**Estimate**: 3 days

### T-2004: Broker Adapter Skeletons (at-broker-adapters)
**Scope**: Foundation for real broker connectivity
- [ ] Common order model and adapter interface
- [ ] Paper trading adapter (internal sandbox)
- [ ] Interactive Brokers adapter skeleton
- [ ] Alpaca adapter skeleton
- [ ] Dry-run mode with signing stubs
- [ ] Order state machine and reconciliation
**Estimate**: 4 days

## MAJOR Priority (Core features)

### T-2005: Strategy Plugin API v1
**Scope**: Dynamic strategy loading and management
- [ ] Plugin registry and discovery
- [ ] Lifecycle management (load/unload/reload)
- [ ] Standard interface for strategies
- [ ] Hot-reload without restart
- [ ] Strategy versioning and rollback
**Estimate**: 3 days

### T-2006: ML Feature Store Stub
**Scope**: Foundation for ML-based strategies
- [ ] Redis-backed feature cache
- [ ] Rolling window calculations (bars, volatility)
- [ ] Market microstructure features
- [ ] Liquidity and spread metrics
- [ ] Feature versioning and TTL
**Estimate**: 3 days

### T-2007: Cross-Service Observability Dashboards
**Scope**: Production-grade monitoring
- [ ] Golden Path dashboard with hop-by-hop latency
- [ ] Strategy performance comparison board
- [ ] Risk exposure heat map
- [ ] System health overview
- [ ] Alert summary panel
**Estimate**: 2 days

### T-2008: Chaos and Backpressure Tests
**Scope**: Resilience validation
- [ ] NATS latency injection tests
- [ ] Consumer crash/restart scenarios
- [ ] Duplicate message handling
- [ ] Large payload stress tests
- [ ] Network partition simulation
**Estimate**: 2 days

### T-2009: Audit Trail System
**Scope**: Regulatory compliance and debugging
- [ ] Persist all decision inputs and rationale
- [ ] Immutable event log with hashes
- [ ] Query API for audit retrieval
- [ ] Compliance report generation
- [ ] Integration with monitoring
**Estimate**: 3 days

## MINOR Priority (Polish and tooling)

### T-2010: Idempotency Conformance Tests
**Scope**: Ensure all services handle duplicates correctly
- [ ] Test suite for idempotency keys
- [ ] Automated validation in CI
- [ ] Performance impact assessment
**Estimate**: 1 day

### T-2011: SLOs and Alert Definitions
**Scope**: Production SLI/SLO framework
- [ ] Define golden signals per service
- [ ] 99th percentile latency < 500ms
- [ ] Error rate < 1% budget
- [ ] Missed fill detection
- [ ] Alert routing and escalation
**Estimate**: 2 days

### T-2012: Developer Experience (Makefiles)
**Scope**: One-click operations
- [ ] Makefile targets for all operations
- [ ] Development environment setup script
- [ ] Log aggregation shortcuts
- [ ] Performance profiling helpers
**Estimate**: 1 day

### T-2013: Deployment Annotations
**Scope**: Correlate deployments with metrics
- [ ] GitHub Actions → Grafana annotations
- [ ] Incident timeline markers
- [ ] Strategy change tracking
- [ ] Rollback annotations
**Estimate**: 1 day

## NICE-TO-HAVE Priority

### T-2014: WebSocket API for Real-time Updates
- [ ] Stream positions and P&L to UI
- [ ] Real-time decision feed
- [ ] Market data distribution

### T-2015: Strategy Marketplace
- [ ] Strategy sharing platform
- [ ] Performance leaderboard
- [ ] Backtesting competitions

### T-2016: Cloud-Native Deployment
- [ ] Kubernetes manifests
- [ ] Helm charts
- [ ] Auto-scaling policies

## Sprint 2 Timeline

**Week 1**: Blockers (T-2001 to T-2004)
- Days 1-2: Meta-agent service
- Days 3-4: Portfolio risk engine
- Day 5: Backtesting harness start

**Week 2**: Major features (T-2005 to T-2009)
- Days 6-7: Complete backtesting, start broker adapters
- Days 8-9: Strategy API and ML feature store
- Day 10: Observability and chaos testing

**Week 3**: Polish and production prep
- Days 11-12: Audit trail and conformance tests
- Days 13-14: SLOs, tooling, documentation
- Day 15: Integration testing and demo prep

## Success Metrics

1. **Technical**
   - All blocker tickets complete
   - End-to-end latency P95 < 500ms
   - Zero message loss under chaos testing
   - 100% idempotency test coverage

2. **Functional**
   - Meta-agent successfully coordinates 3+ strategies
   - Risk engine prevents overleveraging
   - Backtesting reproduces live results ±5%
   - Paper trading adapter processes 1000 orders/sec

3. **Operational**
   - All services have SLO dashboards
   - Alerts fire correctly on violations
   - One-click deployment works
   - Audit trail captures 100% of decisions

## Dependencies

- Sprint 1 must be fully complete and tested
- NATS cluster must support 10K msgs/sec
- Redis instance for feature store (T-2006)
- Historical data source for backtesting (T-2003)

## Risk Mitigation

1. **Broker API delays**: Start with paper trading only
2. **ML complexity**: Keep feature store simple initially
3. **Performance bottlenecks**: Profile early and often
4. **Integration issues**: Daily smoke tests

## Definition of Done

- [ ] All blocker tickets closed
- [ ] Integration tests passing
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Security review complete
- [ ] Demo recording available
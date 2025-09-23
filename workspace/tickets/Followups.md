# Sprint 1 Follow-up Tickets

## Critical Path (Must Complete for Sprint 1)

### T-1101: Fix port conflicts in master guide
- **File**: MASTER_GUIDE.md
- **Change**: Update ports table to show at-mcp:8002, at-exec-sim:8004
- **Rationale**: Prevent service startup conflicts
- **Priority**: Blocker

### T-1102: Update MCP port configuration
- **File**: repos/at-mcp/README.md
- **Change**: Change port from 8003 to 8002 throughout documentation
- **Rationale**: Resolve conflict with at-exec-sim
- **Priority**: Blocker

### T-1103: Standardize gateway environment variables
- **File**: repos/at-gateway/README.md
- **Change**: Add complete environment variables table
- **Rationale**: Ensure proper service configuration
- **Priority**: Blocker

### T-1104: Standardize core environment variables
- **File**: repos/at-core/README.md
- **Change**: Add NATS and service configuration variables
- **Rationale**: Enable proper NATS integration
- **Priority**: Blocker

### T-1105: Standardize agents environment variables
- **File**: repos/at-agents/README.md
- **Change**: Add complete environment variables table
- **Rationale**: Ensure agent configuration consistency
- **Priority**: Blocker

### T-1106: Standardize orchestrator environment variables
- **File**: repos/at-orchestrator/README.md
- **Change**: Add complete environment variables table
- **Rationale**: Ensure orchestrator configuration consistency
- **Priority**: Blocker

### T-1107: Update MCP environment variables
- **File**: repos/at-mcp/README.md
- **Change**: Standardize environment variable naming and add missing vars
- **Rationale**: Align with system-wide standards
- **Priority**: Blocker

### T-1108: Complete gateway auth headers
- **File**: repos/at-gateway/API_SPEC.md
- **Change**: Add X-Nonce, Idempotency-Key, X-API-Version headers
- **Rationale**: Ensure webhook security completeness
- **Priority**: Blocker

### T-1109: Complete MCP auth headers
- **File**: repos/at-mcp/SECURITY.md
- **Change**: Add missing auth headers to requirements
- **Rationale**: Ensure tool call security consistency
- **Priority**: Blocker

## High Priority (Complete by Sprint 1.5)

### T-1110: Fix MCP idempotency TTL
- **File**: repos/at-mcp/MCP_OVERVIEW.md
- **Change**: Change TTL from 300s to 3600s
- **Rationale**: Standardize duplicate detection window
- **Priority**: Major

### T-1111: Fix MCP payload limits
- **File**: repos/at-mcp/SERVER_TEMPLATE.md
- **Change**: Correct payload limit from 10MB to 1MB
- **Rationale**: Standardize HTTP payload limits
- **Priority**: Major

### T-1112: Create gateway error catalog
- **File**: repos/at-gateway/ERROR_CATALOG.md
- **Change**: Implement complete GW-xxx error code system
- **Rationale**: Enable proper error handling and debugging
- **Priority**: Major

### T-1113: Create core error catalog
- **File**: repos/at-core/ERROR_CATALOG.md
- **Change**: Implement complete CORE-xxx error code system
- **Rationale**: Enable proper error handling and debugging
- **Priority**: Major

### T-1114: Update observability port targets
- **File**: repos/at-observability/prometheus.yml
- **Change**: Update MCP target from 8003 to 8002
- **Rationale**: Align with corrected port assignments
- **Priority**: Major

## Medium Priority (Sprint 2)

### T-1115: Fix broken architecture link
- **File**: ARCHITECTURE_OVERVIEW.md
- **Change**: Correct link from METRICS.md to OBSERVABILITY_MODEL.md
- **Rationale**: Fix documentation navigation
- **Priority**: Minor

### T-1116: Add gateway health check documentation
- **File**: repos/at-gateway/RUNBOOK.md
- **Change**: Document /healthz endpoint usage and monitoring
- **Rationale**: Complete observability documentation
- **Priority**: Minor

### T-1117: Document enriched signal subjects
- **File**: repos/at-agents/AGENTS_OVERVIEW.md
- **Change**: Add signals.enriched.* subject pattern documentation
- **Rationale**: Complete NATS subject taxonomy
- **Priority**: Minor

### T-1118: Document order intent subjects
- **File**: repos/at-orchestrator/STATE_MANAGEMENT.md
- **Change**: Explicitly document decisions.order_intent subject
- **Rationale**: Complete workflow subject documentation
- **Priority**: Minor

### T-1119: Add gateway versioning documentation
- **File**: repos/at-gateway/DEVELOPER_GUIDE.md
- **Change**: Add SemVer compliance and dual-accept window details
- **Rationale**: Complete API versioning strategy
- **Priority**: Minor

### T-1120: Add core schema versioning
- **File**: repos/at-core/SCHEMA_REGISTRY.md
- **Change**: Document dual-accept window and migration process
- **Rationale**: Complete schema evolution strategy
- **Priority**: Minor

### T-1121: Verify metric naming compliance
- **File**: repos/at-observability/ALERTS.md
- **Change**: Audit all metric names against ADR-0003 standards
- **Rationale**: Ensure observability consistency
- **Priority**: Minor

### T-1122: Systematic link validation
- **File**: All repositories
- **Change**: Validate and fix all relative links across documentation
- **Rationale**: Improve developer experience
- **Priority**: Minor

### T-1123: Remove placeholder text
- **File**: All repositories
- **Change**: Identify and replace any remaining placeholder content
- **Rationale**: Complete documentation polish
- **Priority**: Minor

## Questions for Clarification

### Q1: Port Assignment Strategy
- **Issue**: Should we reserve specific port ranges for different service types?
- **Context**: Current ad-hoc assignment (8001, 8002, 8004) could lead to future conflicts
- **Recommendation**: Define port ranges (8000-8099 for services, 9000-9099 for monitoring)

### Q2: Environment Variable Inheritance
- **Issue**: Should services inherit common variables from a base configuration?
- **Context**: Repetitive NATS_*, LOG_LEVEL, ENV variables across all services
- **Recommendation**: Create common environment variable template

### Q3: Error Code Coordination
- **Issue**: How should error codes be coordinated across services to prevent conflicts?
- **Context**: Need to ensure GW-xxx, CORE-xxx, MCP-xxx don't overlap in meaning
- **Recommendation**: Create centralized error code registry

### Q4: Idempotency Key Format
- **Issue**: Should idempotency key format be standardized across all services?
- **Context**: Different services may generate keys differently
- **Recommendation**: Define standard key generation algorithm

### Q5: Payload Size Consistency
- **Issue**: Should different services have different payload limits based on use case?
- **Context**: MCP tools might need larger payloads than webhooks
- **Recommendation**: Define per-service limits with justification

## Implementation Notes

### Patch Application Order
1. Apply port fixes first (T-1101, T-1102) to prevent conflicts
2. Apply environment variable patches (T-1103 through T-1107) together
3. Apply auth header patches (T-1108, T-1109) as security improvements
4. Apply remaining patches in priority order

### Testing Requirements
- Verify port conflicts resolved with `docker compose up`
- Test environment variable loading in each service
- Validate auth header processing in gateway and MCP
- Confirm error codes generate proper responses
- Check all documentation links resolve correctly

### Dependencies
- **T-1102** depends on **T-1101** (port coordination)
- **T-1114** depends on **T-1102** (observability config update)
- **T-1112, T-1113** can be done in parallel (independent error catalogs)
- Link validation tickets (T-1115, T-1122) should be done after other patches

### Success Criteria
- [ ] All services start without port conflicts
- [ ] Environment variables documented consistently across repos
- [ ] Auth headers complete and consistent
- [ ] Error codes follow namespace conventions
- [ ] Documentation links resolve correctly
- [ ] Idempotency TTL standardized to 3600s
- [ ] Payload limits consistent at 1MB for HTTP

**Next Actions**: Apply patches in priority order, validate changes, and create follow-up PRs for each ticket.
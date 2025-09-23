# Sprint 1 Cross-Repo Audit Report

## Executive Summary

The Sprint 1 audit identified **23 critical inconsistencies** across the Agentic Trading Architecture that require immediate attention. The most severe issues involve port conflicts between services, missing standardized environment variables, and incomplete authentication header specifications. These inconsistencies could lead to deployment failures and security vulnerabilities.

**Impact Assessment:**
- **Deployment Risk**: Port conflicts between at-mcp (8003) and at-exec-sim (8003) will cause service startup failures
- **Security Risk**: Missing auth headers (X-Nonce, Idempotency-Key) leave webhook endpoints vulnerable
- **Operational Risk**: Inconsistent environment variables prevent reliable cross-service configuration

**Recommendation**: Address all blocker and major issues before Sprint 1 completion. Minor issues can be deferred to Sprint 2.

## Detailed Findings

| Severity | Repo/File | Section | Issue | Proposed Fix |
|----------|-----------|---------|--------|--------------|
| **blocker** | MASTER_GUIDE.md | Ports Table | at-exec-sim shows port 8003, conflicts with at-mcp | Change at-exec-sim to port 8004 |
| **blocker** | at-mcp/README.md | Configuration | Port 8003 conflicts with exec-sim | Update all MCP references to use port 8002 |
| **blocker** | at-gateway/API_SPEC.md | Authentication | Missing X-Nonce, Idempotency-Key headers | Add complete auth header specification |
| **major** | at-gateway/README.md | Environment Variables | Missing API_KEY_HMAC_SECRET, IDEMPOTENCY_TTL_SEC | Add standardized env var table |
| **major** | at-core/README.md | Environment Variables | Missing NATS_* variables documentation | Add NATS configuration section |
| **major** | at-agents/README.md | Environment Variables | Missing SERVICE_NAME, RATE_LIMIT_RPS | Add service configuration section |
| **major** | at-orchestrator/README.md | Environment Variables | Missing complete env var list | Add standardized env var table |
| **major** | at-mcp/MCP_OVERVIEW.md | Idempotency | TTL shows 300s instead of 3600s | Change to 3600s (1 hour) |
| **major** | at-mcp/SERVER_TEMPLATE.md | Payload Limits | Shows 10MB instead of 1MB | Correct to 1MB for HTTP payloads |
| **major** | at-observability/prometheus.yml | Targets | Shows at-mcp:8003, should be 8002 | Update target port |
| **major** | at-gateway/ERROR_CATALOG.md | Error Codes | Missing GW-xxx namespace errors | Add complete error code catalog |
| **major** | at-core/ERROR_CATALOG.md | Error Codes | Missing CORE-xxx namespace errors | Add complete error code catalog |
| **minor** | at-gateway/RUNBOOK.md | Health Checks | Missing /healthz endpoint documentation | Add health check procedures |
| **minor** | at-agents/AGENTS_OVERVIEW.md | NATS Subjects | Missing signals.enriched.* subject pattern | Document enriched signal subjects |
| **minor** | at-orchestrator/STATE_MANAGEMENT.md | NATS Subjects | Missing decisions.order_intent documentation | Add order intent subject details |
| **minor** | at-mcp/SECURITY.md | Auth Headers | Missing X-API-Version header | Add version header requirement |
| **minor** | at-observability/ALERTS.md | Metrics | Metric names not verified against ADR-0003 | Verify metric naming compliance |
| **minor** | ARCHITECTURE_OVERVIEW.md | Links | Reference to at-observability/METRICS.md doesn't exist | Fix link to OBSERVABILITY_MODEL.md |
| **minor** | at-gateway/DEVELOPER_GUIDE.md | Versioning | Missing SemVer compliance documentation | Add versioning strategy section |
| **minor** | at-core/SCHEMA_REGISTRY.md | Versioning | Missing dual-accept window details | Add schema migration process |
| **minor** | at-agents/TEST_STRATEGY.md | Links | Relative links may not resolve | Verify all internal links |
| **minor** | at-orchestrator/META_AGENT_TEMPLATE.md | Links | References to undefined sections | Fix section references |
| **minor** | at-mcp/PROMPTS.md | Links | Cross-references to missing content | Update link targets |

## Affected Service Summary

### at-gateway (6 issues)
- **Critical**: Missing auth headers, environment variables
- **Impact**: Webhook security vulnerabilities, configuration drift

### at-mcp (5 issues)
- **Critical**: Port conflict, payload limits, TTL inconsistency
- **Impact**: Service startup failures, incorrect behavior

### at-core (3 issues)
- **Critical**: Missing environment variables, error codes
- **Impact**: Service integration failures

### at-agents (3 issues)
- **Critical**: Missing environment variables, NATS subjects
- **Impact**: Agent startup and communication issues

### at-orchestrator (3 issues)
- **Critical**: Missing environment variables, NATS subjects
- **Impact**: Workflow coordination failures

### at-observability (2 issues)
- **Critical**: Port configuration, metric compliance
- **Impact**: Monitoring blind spots

### Root Documentation (1 issue)
- **Critical**: Port conflict in master guide
- **Impact**: Developer confusion, deployment errors

## Compliance Matrix

| Invariant | Gateway | Core | Agents | Orchestrator | MCP | Observability |
|-----------|---------|------|--------|--------------|-----|---------------|
| Ports (8001,9090,3000,4222) | ✅ | N/A | N/A | N/A | ❌ | ✅ |
| NATS Subjects | ⚠️ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ |
| Environment Variables | ❌ | ❌ | ❌ | ❌ | ⚠️ | ✅ |
| Auth Headers | ❌ | N/A | N/A | N/A | ⚠️ | N/A |
| Idempotency TTL (3600s) | ⚠️ | ✅ | ✅ | ✅ | ❌ | N/A |
| Payload Limits (1MB) | ⚠️ | N/A | N/A | N/A | ❌ | N/A |
| Error Namespaces | ❌ | ❌ | N/A | N/A | ✅ | N/A |
| Observability Endpoints | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Versioning (SemVer) | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Link Resolution | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |

**Legend**: ✅ Compliant | ⚠️ Partially Compliant | ❌ Non-Compliant | N/A Not Applicable

## Risk Assessment

### High Risk (Blockers)
1. **Port Conflicts**: Services cannot start simultaneously
2. **Missing Auth Headers**: Security vulnerabilities in production
3. **Environment Variable Gaps**: Services fail to configure properly

### Medium Risk (Major Issues)
1. **Idempotency Inconsistencies**: Duplicate processing risks
2. **Error Code Gaps**: Poor debugging experience
3. **Payload Limit Variations**: Unexpected request rejections

### Low Risk (Minor Issues)
1. **Documentation Links**: Developer experience degradation
2. **Metric Naming**: Monitoring consistency concerns
3. **Versioning Gaps**: Future upgrade complications

## Recommended Action Plan

### Phase 1: Critical Fixes (Sprint 1)
1. Resolve port conflicts (T-1101, T-1102)
2. Standardize environment variables (T-1103 through T-1107)
3. Complete auth header specifications (T-1108, T-1109)

### Phase 2: Major Fixes (Sprint 1.5)
1. Fix idempotency and payload limits (T-1110, T-1111)
2. Complete error catalogs (T-1112, T-1113)
3. Update observability configurations (T-1114)

### Phase 3: Minor Fixes (Sprint 2)
1. Fix documentation links (T-1115 through T-1120)
2. Verify metric naming compliance (T-1121)
3. Complete versioning documentation (T-1122, T-1123)

## Success Criteria

- [ ] All services start without port conflicts
- [ ] All webhook endpoints have complete auth header validation
- [ ] All services document required environment variables
- [ ] Idempotency TTL standardized to 3600s across all services
- [ ] Error codes follow GW-xxx, CORE-xxx, MCP-xxx patterns
- [ ] All relative links resolve correctly
- [ ] Prometheus targets use correct ports

**Next Steps**: Review consistency matrix, apply patches from sprint1_patches.json, and execute follow-up tickets in priority order.
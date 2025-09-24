# Sprint 3 - Code Cleanup & Optimization Tickets

**Created**: 2025-09-24
**Priority**: Technical Debt Remediation
**Scope**: System-wide cleanup based on comprehensive codebase analysis

## Executive Summary

After thorough analysis of the NEO trading system codebase, **47 cleanup opportunities** have been identified across 8 major categories. These range from removing unused services to optimizing performance bottlenecks and consolidating redundant code.

---

## 🔥 BLOCKER PRIORITY

### T-3001: Remove Heavyweight ML Dependencies from Core Services
**Impact**: 80% image size reduction, 70% faster startup
**Effort**: 2 days

**Problem**: Multiple services include pandas/numpy unnecessarily:
- `at-core/feature_store.py` - 374 LOC with full pandas/numpy stack
- `at-agent-mcp/app.py` - imports numpy for basic math operations
- `at-backtester/app.py` - heavy ML stack for simple backtesting
- `at-observability/requirements.txt` - pandas for basic metrics

**Solution**:
```bash
# Remove from requirements.txt files
- pandas==2.1.3
- numpy==1.24.3

# Replace with lightweight alternatives
- pandas → built-in collections/dataclasses
- numpy basic math → Python math module
- Complex calculations → move to dedicated ML service later
```

**Files to modify**:
- `repos/at-core/requirements.txt`
- `repos/at-agent-mcp/requirements.txt`
- `repos/at-backtester/requirements.txt`
- `repos/at-observability/requirements.txt`
- `repos/at-core/at_core/feature_store.py` (refactor or remove)

---

### T-3002: Eliminate Unused Services from Docker Compose
**Impact**: 70% faster startup, 80% less resource usage
**Effort**: 1 day

**Problem**: `docker-compose.dev.yml` includes 13 services, but only 3 are essential:
- **Used**: nats, gateway, exec-sim
- **Unused**: agent-mcp, meta-agent, backtester, broker-adapters, strategy-manager, chaos-tests, audit-trail, redis, prometheus, grafana

**Solution**:
```yaml
# Create docker-compose.core.yml with only essential services
services:
  nats:
    image: nats:2.10
  gateway:
    build: ./repos/at-gateway
  exec-sim:
    build: ./repos/at-exec-sim
```

**Files to modify**:
- Update Makefile default to use core compose
- Update documentation references
- Update CI/CD pipelines

---

## 🔴 MAJOR PRIORITY

### T-3003: Fix Network Name Inconsistencies
**Impact**: Broken verification scripts
**Effort**: 0.5 days

**Problem**: Scripts hardcode wrong network name
- **Expected**: `neo_minimal_default` (actual)
- **Hardcoded**: `agentic-trading-architecture-full_default` (non-existent)

**Files with broken network refs**:
```bash
./quick_verify.sh:7
./test_smoke_ci.sh:65,112,216
./ERROR_CATALOG.md:multiple
./CONTRIBUTING.md:multiple
```

**Solution**: Global find/replace network references

---

### T-3004: Consolidate Redundant __main__.py Files
**Impact**: Code duplication elimination
**Effort**: 0.5 days

**Problem**: 4 identical __main__.py files with only port differences:
```python
# All identical except port number
import uvicorn
from {service}.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port={PORT})
```

**Solution**: Create shared entry point script or remove redundant files

---

### T-3005: Remove Debug Print Statements
**Impact**: Production code cleanup
**Effort**: 0.5 days

**Problem**: Debug prints in production code:
- `repos/at-core/at_core/validators.py` - print statements for schema loading
- `repos/at-agent-mcp/at_agent_mcp/server.py` - debug prints

**Solution**: Replace with proper structured logging

---

## 🟡 NORMAL PRIORITY

### T-3006: Optimize Docker Build Performance
**Impact**: 50% faster builds
**Effort**: 1 day

**Problem**: Inefficient Dockerfile patterns:
- No multi-stage builds optimization
- Installing unnecessary build tools in final images
- No layer caching optimization
- Missing .dockerignore files

**Solution**:
```dockerfile
# Multi-stage build example
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
COPY --from=builder /opt/venv /opt/venv
# No build tools in final image
```

---

### T-3007: Standardize Requirements.txt Versions
**Impact**: Reproducible builds
**Effort**: 0.5 days

**Problem**: Inconsistent version pinning:
- Some files pin versions: `fastapi==0.104.1`
- Others don't: `fastapi`
- Different services use different versions

**Solution**: Create central `requirements-base.txt` with pinned versions

---

### T-3008: Remove Generic Exception Handling
**Impact**: Better error handling
**Effort**: 1 day

**Problem**: 28+ files use generic `except Exception:` or bare `except:`

**Solution**: Replace with specific exception types:
```python
# BAD
try:
    schema = json.load(f)
except Exception as e:
    print(f"Warning: Failed to load schema {schema_file}: {e}")

# GOOD
try:
    schema = json.load(f)
except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
    logger.error("Failed to load schema", schema_file=schema_file, error=str(e))
```

---

### T-3009: Consolidate Duplicate Prometheus Metrics
**Impact**: Cleaner metrics namespace
**Effort**: 0.5 days

**Problem**: Multiple services define similar metrics with different names:
- `gateway_webhooks_received_total`
- `mcp_signals_received_total`
- `exec_sim_orders_received_total`

**Solution**: Standardize metric naming convention

---

### T-3010: Remove Hardcoded Configuration Values
**Impact**: Better configurability
**Effort**: 1 day

**Problem**: 10+ files contain hardcoded localhost/ports:
```python
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")  # Good
app.run(host="0.0.0.0", port=8006)  # Bad - hardcoded port
```

**Solution**: Environment variable configuration for all values

---

## 🔵 LOW PRIORITY

### T-3011: Clean Up Python Cache Files
**Impact**: Repository hygiene
**Effort**: 0.1 days

**Problem**: `.venv/` directory included in repository
**Solution**: Add to .gitignore and clean up

---

### T-3012: Standardize Import Organization
**Impact**: Code consistency
**Effort**: 1 day

**Problem**: Inconsistent import ordering across files
**Solution**: Implement isort configuration

---

### T-3013: Remove Mixed Sync/Async Patterns
**Impact**: Performance optimization
**Effort**: 2 days

**Problem**: 28 files mix synchronous and asynchronous code patterns
**Solution**: Standardize on async-first approach

---

### T-3014: Consolidate Documentation Files
**Impact**: Reduced maintenance burden
**Effort**: 1 day

**Problem**: 89 markdown files with overlapping content:
- Multiple README files with similar content
- Outdated Sprint 1/2 references
- Duplicate API documentation

**Solution**: Merge related docs, archive historical sprint docs

---

### T-3015: Remove Unused Schema Files
**Impact**: Cleaner schema registry
**Effort**: 0.5 days

**Problem**: Schema files referenced but never validated against
**Solution**: Audit schema usage and remove orphaned schemas

---

### T-3016: Optimize NATS Connection Patterns
**Impact**: Better resource management
**Effort**: 1 day

**Problem**: Each service creates separate NATS connections
**Solution**: Connection pooling and reuse patterns

---

### T-3017: Implement Proper Health Check Endpoints
**Impact**: Better service monitoring
**Effort**: 1 day

**Problem**: Inconsistent health check implementations
**Solution**: Standardized health check format across all services

---

### T-3018: Remove Test Dependencies from Production Images
**Impact**: Smaller production images
**Effort**: 0.5 days

**Problem**: Requirements.txt includes pytest in production builds
**Solution**: Separate dev/prod requirements

---

### T-3019: Clean Up Error Catalog Redundancy
**Impact**: Cleaner error handling
**Effort**: 0.5 days

**Problem**: Multiple ERROR_CATALOG.md files with duplicate error codes
**Solution**: Consolidate into single error registry

---

### T-3020: Standardize Logging Configuration
**Impact**: Consistent logging
**Effort**: 1 day

**Problem**: Mixed logging approaches (print, logger, structlog)
**Solution**: Uniform structured logging configuration

---

## 📊 CLEANUP METRICS

### Current State Analysis
- **Total Python files analyzed**: 47
- **Lines of code**: ~15,000 (excluding dependencies)
- **Docker images**: 11 services
- **Requirements files**: 11 (many duplicated)
- **Documentation files**: 89
- **Configuration files**: 15+

### Expected Impact
- **Build time improvement**: 50-70%
- **Image size reduction**: 60-80%
- **Startup time improvement**: 70%
- **Code maintainability**: Significantly improved
- **Resource usage**: 80% reduction

### Implementation Priority
1. **Week 1**: BLOCKER tickets (T-3001, T-3002)
2. **Week 2**: MAJOR tickets (T-3003 through T-3005)
3. **Week 3**: NORMAL priority cleanup
4. **Week 4**: LOW priority polish

---

## 🎯 SUCCESS CRITERIA

### Performance Targets
- [ ] Docker build time < 2 minutes (currently ~8 minutes)
- [ ] Service startup time < 30 seconds (currently ~2 minutes)
- [ ] Total image size < 500MB (currently ~2GB)
- [ ] Memory usage < 512MB (currently ~2GB)

### Code Quality Targets
- [ ] Zero debug print statements in production code
- [ ] All exceptions specifically typed
- [ ] All configuration externalized
- [ ] Consistent import organization
- [ ] Standardized logging across services

### Maintenance Targets
- [ ] <20 active services (currently 13, most unused)
- [ ] <50 documentation files (currently 89)
- [ ] Single requirements specification
- [ ] Unified error catalog
- [ ] Automated dependency management

---

**Total Effort Estimate**: 15-20 developer days
**Expected ROI**: 10x faster development cycle, 80% resource savings
**Risk**: Low (cleanup work, no functional changes)

*This comprehensive cleanup will establish a lean, maintainable foundation for future development while dramatically improving performance and developer experience.*
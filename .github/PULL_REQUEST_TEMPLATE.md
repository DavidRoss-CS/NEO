## Summary
[Provide a brief description of the changes in this PR]

## Motivation
[Explain why these changes are needed. Link to relevant issues or tickets.]

Closes #[issue number]
Refs: [Ticket/ADR references]

## Changes
[Describe what was changed, added, or removed]

### Code Changes
- [ ] New feature implementation
- [ ] Bug fix
- [ ] Refactoring
- [ ] Performance improvement
- [ ] Security enhancement
- [ ] Dependency update

### Breaking Changes
- [ ] API changes that affect existing clients
- [ ] Schema changes that require migration
- [ ] Configuration changes
- [ ] Database schema changes

[If breaking changes are present, describe migration path]

## Screenshots/Logs
[Include relevant screenshots, log snippets, or command outputs that demonstrate the changes]

```
[Paste relevant logs or command outputs here]
```

## Testing
[Describe how the changes were tested]

### Test Coverage
- [ ] Unit tests added/updated
- [ ] Contract tests added/updated
- [ ] Integration tests added/updated
- [ ] End-to-end tests added/updated
- [ ] Load/performance tests added/updated

### Manual Testing
- [ ] Tested locally with development setup
- [ ] Tested against staging environment
- [ ] Tested error conditions and edge cases
- [ ] Tested with realistic data volumes

### Test Evidence
[Provide evidence that tests pass]
```bash
# Example test run output
make test-all
# All tests passing
```

## Documentation and Compliance

### Documentation Updates
- [ ] README.md updated
- [ ] API_SPEC.md updated
- [ ] ERROR_CATALOG.md updated (if new error codes)
- [ ] TEST_STRATEGY.md updated
- [ ] RUNBOOK.md updated
- [ ] ADR created/updated for architectural changes

### Contract Management
- [ ] Event schemas versioned appropriately
- [ ] Backward compatibility verified
- [ ] Contract tests validate schema changes
- [ ] Migration plan documented for breaking changes

### Observability
- [ ] Metrics added for new functionality
- [ ] Structured logging includes correlation IDs
- [ ] Error handling includes appropriate error codes
- [ ] Dashboards updated for new metrics
- [ ] Alert rules updated if needed

### Security Review
- [ ] HMAC signature validation maintained
- [ ] Rate limiting applied to new endpoints
- [ ] Input validation covers all user inputs
- [ ] No secrets committed to repository
- [ ] PII handling reviewed and compliant
- [ ] Authentication/authorization logic reviewed
- [ ] Dependency security scan passed

## Risk Assessment and Rollback

### Risk Level
- [ ] Low - Minimal impact, easy to rollback
- [ ] Medium - Some impact, rollback procedures in place
- [ ] High - Significant impact, extensive testing required

### Rollback Plan
[Describe how to rollback these changes if issues occur]

**Rollback Steps**:
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Rollback Validation**:
- [ ] Service health checks pass
- [ ] Core functionality verified
- [ ] Monitoring shows normal operation

### Deployment Strategy
- [ ] Can be deployed during business hours
- [ ] Requires maintenance window
- [ ] Needs coordination with other teams
- [ ] Requires database migration
- [ ] Needs configuration changes

## Quality Checklist

### Code Quality
- [ ] Code follows established patterns and conventions
- [ ] Error handling is comprehensive
- [ ] Resource cleanup is properly handled
- [ ] Performance impact is acceptable
- [ ] Code is readable and well-commented

### Testing Quality
- [ ] Tests cover happy path scenarios
- [ ] Tests cover error conditions
- [ ] Tests are deterministic and reliable
- [ ] Test data is realistic and comprehensive
- [ ] Tests run in reasonable time

### Operational Quality
- [ ] Service startup/shutdown is graceful
- [ ] Configuration is externalized
- [ ] Logging provides sufficient detail for debugging
- [ ] Metrics provide visibility into service health
- [ ] Error messages are actionable

## Links and References

### Related Work
- **Tickets**: [Link to implementation tickets]
- **ADRs**: [Link to relevant architectural decisions]
- **Dependencies**: [Link to related PRs or changes]

### Documentation
- **API Changes**: [Link to API documentation]
- **Runbook Updates**: [Link to operational procedures]
- **Migration Guides**: [Link to upgrade instructions]

## Reviewer Notes
[Any specific guidance for reviewers, areas to focus on, or known limitations]

### Review Focus Areas
- [ ] Security implications
- [ ] Performance impact
- [ ] Error handling
- [ ] Test coverage
- [ ] Documentation completeness

### Known Limitations
[List any known limitations or technical debt introduced]

---

## For Reviewers

### Review Checklist
- [ ] Code changes align with architectural decisions
- [ ] Security best practices are followed
- [ ] Performance implications are acceptable
- [ ] Error handling is comprehensive
- [ ] Tests adequately cover the changes
- [ ] Documentation is complete and accurate
- [ ] Rollback plan is feasible

### Approval Criteria
- [ ] All automated checks pass
- [ ] Manual testing completed successfully
- [ ] Security review completed (for security-sensitive changes)
- [ ] Performance impact assessed (for performance-sensitive changes)
- [ ] Documentation review completed

/cc @team-platform @team-security
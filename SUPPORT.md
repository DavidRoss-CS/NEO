# Support

Welcome! This document explains how to get help with the Agentic Trading Architecture project.

## How to Get Help

### 🐛 Bug Reports

**For bugs and technical issues**, please open a GitHub issue with:

#### Required Information
- **Summary**: Brief description of the issue
- **Environment**: OS, Python version, service version
- **Steps to reproduce**: Exact steps that trigger the issue
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Logs and errors**: Include relevant log entries with correlation IDs
- **Configuration**: Relevant environment variables (redact secrets)

#### Log Collection
Include correlation IDs for faster debugging:
```bash
# Example log search
grep "corr_id":"req_abc123" /var/log/at-gateway.log

# Health check status
curl http://localhost:8001/healthz

# Recent metrics
curl http://localhost:8001/metrics | grep gateway_
```

#### Issue Template
```markdown
**Summary**: [Brief description]

**Environment**:
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.12.0]
- Service: [e.g., at-gateway v1.0.0]
- Docker: [e.g., 24.0.0]

**Steps to Reproduce**:
1. [First step]
2. [Second step]
3. [Issue occurs]

**Expected**: [What should happen]
**Actual**: [What actually happens]

**Logs**:
```
[Paste relevant logs with correlation IDs]
```

**Configuration**:
```
[Relevant environment variables, redact secrets]
```
```

### 🔒 Security Issues

**For security vulnerabilities**, please email `security@example.com` directly.

**Do NOT** open public GitHub issues for security concerns.

#### Security Report Format
- **Summary**: Brief description of vulnerability
- **Impact**: Potential security impact
- **Reproduction**: Step-by-step reproduction instructions
- **Affected versions**: Which versions are affected
- **Mitigation**: Suggested fixes or workarounds

See [SECURITY.md](SECURITY.md) for complete security reporting guidelines.

### 💬 Questions and Discussions

**For general questions, feature requests, and discussions**:

- **GitHub Discussions**: [Link to discussions] - Best for technical questions
- **Slack Channel**: `#trading-platform` - Real-time chat and quick questions
- **Documentation**: Start with [MASTER_GUIDE.md](MASTER_GUIDE.md) and service-specific README files

#### Good Questions Include
- **Context**: What are you trying to accomplish?
- **What you've tried**: Steps you've already taken
- **Specific issue**: Exact error messages or unexpected behavior
- **Environment**: Relevant setup details

### 📚 Documentation Issues

**For documentation problems** (unclear instructions, missing information, errors):

- Open a GitHub issue labeled `documentation`
- Suggest specific improvements
- Include which document needs updating
- Provide correct information if you know it

## Response Times and Support Levels

### Triage SLAs

| Priority | Response Time | Resolution Target | Examples |
|----------|---------------|-------------------|----------|
| **Critical** | < 4 hours | < 24 hours | Service down, security breach, data loss |
| **High** | < 1 business day | < 3 business days | Authentication failures, rate limiting issues |
| **Normal** | < 3 business days | < 1 week | Feature requests, documentation improvements |
| **Low** | < 1 week | Best effort | Enhancement suggestions, nice-to-have features |

### Priority Definitions

**Critical**:
- Service completely unavailable
- Security vulnerability being exploited
- Data corruption or loss
- Regulatory compliance impact

**High**:
- Significant functionality impaired
- Authentication/authorization issues
- Performance degradation affecting users
- Integration failures

**Normal**:
- Minor functionality issues
- Documentation problems
- Feature enhancement requests
- Configuration questions

**Low**:
- Cosmetic issues
- General questions
- Future feature discussions

## Self-Service Resources

### 📖 Documentation

Start with these documents before opening issues:

1. **[ONBOARDING.md](ONBOARDING.md)**: 15-minute setup guide
2. **[MASTER_GUIDE.md](MASTER_GUIDE.md)**: System overview and quickstart
3. **[ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)**: System design and data flow
4. **[CONTRIBUTING.md](CONTRIBUTING.md)**: Development workflow
5. **Service-specific docs**: Each repo has README, API_SPEC, RUNBOOK, TEST_STRATEGY

### 🔧 Troubleshooting Guides

**Common Issues**:
- **[Gateway RUNBOOK](repos/at-gateway/RUNBOOK.md)**: Operational procedures and troubleshooting
- **[Error Catalog](repos/at-gateway/ERROR_CATALOG.md)**: Error codes and solutions
- **Setup Issues**: See [ONBOARDING.md](ONBOARDING.md) "Common Pitfalls" section

**Quick Checks**:
```bash
# Service health
curl http://localhost:8001/healthz

# Infrastructure status
docker compose ps

# NATS connectivity
nats server ping

# Recent errors
docker compose logs --tail=50 gateway | grep ERROR
```

### 🎯 FAQ

**Q: How do I generate a valid webhook signature?**

A: See the authentication example in [ONBOARDING.md](ONBOARDING.md#test-4-send-test-webhook) or [Gateway API_SPEC](repos/at-gateway/API_SPEC.md#complete-authentication-example).

**Q: Why am I getting 401 authentication errors?**

A: Common causes:
1. Incorrect HMAC secret
2. Clock skew > 30 seconds
3. Reused nonce
4. Malformed signature header

See [Gateway ERROR_CATALOG](repos/at-gateway/ERROR_CATALOG.md#gw-001-invalid-signature) for detailed troubleshooting.

**Q: How do I check if NATS is working?**

A:
```bash
# Test NATS connectivity
nats server ping

# Check streams
nats stream ls

# Monitor events
nats sub "signals.*"
```

**Q: Where can I find error codes and their meanings?**

A: Each service has an ERROR_CATALOG.md file (e.g., [Gateway Error Catalog](repos/at-gateway/ERROR_CATALOG.md)) with complete error code references.

**Q: How do I contribute to the project?**

A: Start with [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, then pick a ticket from `workspace/tickets/`.

## Community Guidelines

### Getting Better Help

1. **Search first**: Check existing issues and documentation
2. **Be specific**: Include error messages, correlation IDs, and configuration
3. **Be patient**: Maintainers are volunteers with day jobs
4. **Be kind**: Follow our [Code of Conduct](CODE_OF_CONDUCT.md)
5. **Help others**: Answer questions you know the answer to

### What Makes a Good Issue

✅ **Good Example**:
```
Title: "Gateway returns 401 for valid TradingView webhooks after key rotation"

Environment: at-gateway v1.2.0, Python 3.12, Docker 24.0.0

Steps:
1. Rotated API_KEY_HMAC_SECRET from X to Y
2. Updated TradingView webhook config with new signature
3. Sent test webhook with correct timestamp and nonce

Expected: 202 Accepted
Actual: 401 with error code GW-001

Logs:
{
  "level": "ERROR",
  "corr_id": "req_abc123",
  "error": "invalid_signature",
  "client_ip": "1.2.3.4"
}

Configuration:
API_KEY_HMAC_SECRET=[REDACTED]
REPLAY_WINDOW_SEC=300
```

❌ **Poor Example**:
```
Title: "Webhooks not working"

it doesn't work, help???
```

### Response Expectations

- **Acknowledgment**: We'll acknowledge your issue within our SLA timeframes
- **Investigation**: We may ask for additional information
- **Updates**: We'll provide status updates for complex issues
- **Resolution**: We'll let you know when issues are resolved

## Contributing Back

### Ways to Help

- **Answer questions**: Help other users in discussions
- **Improve documentation**: Fix unclear or outdated docs
- **Report bugs**: Help us identify and fix issues
- **Submit PRs**: Contribute code improvements
- **Write tests**: Add test coverage for edge cases

### Recognition

We appreciate all contributions! Contributors may be:
- Listed in release notes
- Mentioned in documentation
- Invited to maintainer discussions
- Given GitHub repository permissions

## Contact Information

### Primary Contacts

- **General Support**: [GitHub Issues](../../issues)
- **Security Issues**: `security@example.com`
- **Community Chat**: Slack `#trading-platform`
- **Documentation**: [GitHub Discussions](../../discussions)

### Escalation Path

For urgent issues:
1. **Platform Team**: `#trading-platform-alerts` (Slack)
2. **On-call Engineer**: PagerDuty escalation
3. **Team Lead**: Direct message in Slack
4. **Management**: Follow company escalation procedures

### Business Hours

- **Primary Support**: Monday-Friday, 9 AM - 5 PM UTC
- **Emergency Support**: 24/7 via PagerDuty (critical issues only)
- **Community Support**: Best effort, depends on volunteer availability

## External Resources

### Related Projects

- **NATS**: [Official Documentation](https://docs.nats.io/)
- **FastAPI**: [Documentation](https://fastapi.tiangolo.com/)
- **Prometheus**: [Documentation](https://prometheus.io/docs/)
- **Grafana**: [Documentation](https://grafana.com/docs/)

### Learning Resources

- **Event-driven Architecture**: [Martin Fowler's Guide](https://martinfowler.com/articles/201701-event-driven.html)
- **HMAC Authentication**: [RFC 2104](https://tools.ietf.org/html/rfc2104)
- **Microservices Patterns**: [Chris Richardson's Patterns](https://microservices.io/patterns/)

---

**Thank you for using the Agentic Trading Architecture! We're here to help. 🚀**
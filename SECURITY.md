# Security Policy

## Scope and Threat Model

### Architecture Security Boundaries
- **Ingress**: Only via at-gateway HTTP endpoints with HMAC authentication
- **Secrets**: Environment variables only; production via secret manager
- **Data**: No PII in events; structured logging with correlation IDs
- **Inter-service**: NATS-only communication with least-privilege credentials

### Threat Model

| Threat | Impact | Mitigation |
|--------|--------|-----------|
| API key theft | Unauthorized webhook injection | HMAC rotation, monitoring for signature spikes |
| Replay attacks | Duplicate signal processing | Timestamp + nonce validation with 300s window |
| Schema poisoning | Downstream service crashes | Contract tests, schema validation at ingress |
| NATS credential misuse | Cross-repo data access | Subject-level ACLs, least-privilege principles |
| Rate limit bypass | Service degradation | Per-source tracking, fail-closed on overload |
| Insider threats | Data exfiltration | Audit logging, principle of least access |

## Inbound Authentication

### HMAC-SHA256 Implementation

**Required Headers**:
- `X-Signature`: `sha256=<hex_digest>`
- `X-Timestamp`: ISO8601 UTC timestamp
- `X-Nonce`: UUID4 for replay protection

**Verification Steps**:
1. Parse timestamp and verify within `REPLAY_WINDOW_SEC` ± 30s clock skew
2. Check nonce not in cache (TTL = replay window)
3. Compute HMAC-SHA256 over raw request body
4. Constant-time comparison with provided signature
5. Store nonce in cache, reject if any step fails

**Sample Verification (Python)**:
```python
import hmac
import hashlib
from datetime import datetime, timedelta

def verify_signature(body: bytes, signature: str, timestamp: str, nonce: str, secret: str) -> bool:
    # Check timestamp window
    req_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    now = datetime.utcnow().replace(tzinfo=req_time.tzinfo)
    if abs((now - req_time).total_seconds()) > REPLAY_WINDOW_SEC + 30:
        return False

    # Check nonce cache (implementation specific)
    if nonce in nonce_cache:
        return False

    # Verify signature
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = signature.replace('sha256=', '')

    # Constant-time comparison
    if not hmac.compare_digest(expected, provided):
        return False

    # Store nonce
    nonce_cache[nonce] = datetime.utcnow()
    return True
```

## Secrets Management

### Development
- Use `.env.example` as template, copy to `.env` for local development
- **Never commit `.env` files** - add to `.gitignore`
- Use safe defaults for non-production environments

### Production
- Store secrets in dedicated secret manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate `API_KEY_HMAC_SECRET` monthly using dual-key acceptance pattern
- Minimum secret length: 32 characters for HMAC keys

### Key Rotation Procedure
1. Generate new secret, deploy with comma-separated dual acceptance: `old-key,new-key`
2. Verify both keys work in production
3. Update all clients to use new key
4. Remove old key from configuration after 24-hour overlap
5. Monitor for authentication failures during transition

### Secret Scanning
Enable automated secret scanning:
- **GitHub**: Enable secret scanning and push protection
- **Pre-commit**: Use tools like `detect-secrets` or `truffleHog`
- **CI/CD**: Scan container images and dependency trees

## NATS Hardening

### Credential Management
- Use separate NATS credentials per repository
- Generate JWTs with subject-level permissions
- Rotate NATS credentials quarterly

### Subject ACL Examples
```json
{
  "pub": {
    "allow": ["signals.raw", "signals.normalized"]
  },
  "sub": {
    "deny": ["admin.*", "system.*"]
  }
}
```

### Connection Security
- **TLS**: Enable TLS for all NATS connections in production
- **Firewall**: Restrict NATS port (4222) to known service IPs
- **Monitoring**: Alert on unauthorized connection attempts

## Data Handling

### PII Prevention
- **No personal data** in event payloads
- Use anonymized trader/client IDs only
- Redact sensitive fields in logs:
  ```python
  # Good
  logger.info("Order processed", extra={"client_id": "anon_12345", "instrument": "EURUSD"})

  # Bad
  logger.info("Order processed", extra={"email": "user@example.com", "account": "123456789"})
  ```

### Data Retention
See [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) for complete retention policy:
- Signals: 7 days
- Decisions: 30 days
- Executions: 365 days
- Logs: 30 days (ERROR/WARN), 7 days (INFO)

### Data Export
- All exports require audit logging
- Use correlation IDs for traceability
- Encrypt data in transit and at rest

## Dependency Security

### Vulnerability Scanning
- **Python**: Run `pip-audit` weekly in CI/CD
- **Node.js**: Run `npm audit` weekly in CI/CD
- **Docker**: Scan base images with `trivy` or similar

### Version Management
- Pin exact versions in `requirements.txt` / `package-lock.json`
- Use Dependabot or Renovate for automated updates
- Test dependency updates in staging before production

### Supply Chain Security
- Verify package signatures where available
- Use private registries for internal packages
- Monitor for typosquatting in package names

## Incident Response

### Immediate Contacts
- **Security Team**: `security@example.com`
- **Platform Team**: `#trading-platform-alerts`
- **On-call**: PagerDuty escalation policy

### Evidence Collection
1. **Preserve logs**: Capture relevant log entries with correlation IDs
2. **Metrics snapshot**: Export Grafana dashboard during incident window
3. **Configuration state**: Document current environment variables and settings
4. **Network traces**: Capture relevant traffic if NATS communication involved

### Immediate Controls

**Service Isolation**:
```bash
# Enable maintenance mode
export MAINTENANCE_MODE=true
sudo systemctl restart at-gateway
```

**Rate Limiting**:
```bash
# Reduce rate limits
export RATE_LIMIT_RPS=10
sudo systemctl restart at-gateway
```

**Key Rotation**:
```bash
# Emergency key rotation
export API_KEY_HMAC_SECRET="new-emergency-key"
sudo systemctl restart at-gateway
```

## Security Checklists

### Pre-Merge Security Review
- [ ] No secrets committed to repository
- [ ] HMAC implementation uses constant-time comparison
- [ ] Rate limiting implemented for new endpoints
- [ ] Input validation covers all required fields
- [ ] Error messages don't leak sensitive information
- [ ] Logging excludes PII and credentials
- [ ] Tests include security negative cases
- [ ] Dependencies updated and scanned

### Release Security Checklist
- [ ] Rotate API keys in staging and production
- [ ] Update schema versions if contracts changed
- [ ] Verify rate limiting configuration
- [ ] Test authentication with both old and new keys
- [ ] Confirm NATS ACLs are current
- [ ] Update monitoring alerts for new endpoints
- [ ] Document security changes in release notes
- [ ] Verify backup and rollback procedures

### Security Monitoring
- [ ] Authentication failure rates within normal range
- [ ] No unexpected rate limit violations
- [ ] NATS connection attempts from authorized IPs only
- [ ] Error rates consistent with historical patterns
- [ ] Schema validation failures investigated

## Vulnerability Reporting

### Responsible Disclosure
- **Contact**: `security@example.com`
- **Response SLA**: 24 hours acknowledgment, 5 days initial assessment
- **GPG Key**: [To be provided]

### Report Format
- **Summary**: Brief description of vulnerability
- **Impact**: Potential security impact and affected components
- **Reproduction**: Step-by-step reproduction instructions
- **Mitigation**: Suggested fixes or workarounds
- **Timeline**: Disclosure timeline expectations

### Security Advisory Process
1. **Triage**: Security team evaluates severity (CVSS scoring)
2. **Investigation**: Engineering team confirms and assesses impact
3. **Patching**: Develop and test fix in private repository
4. **Disclosure**: Coordinate with reporter on disclosure timeline
5. **Release**: Deploy fix and publish security advisory

## Compliance and Auditing

### Audit Logging
All security-relevant events are logged with:
- **Correlation ID**: For request tracing
- **Client IP**: Source of request
- **Timestamp**: ISO8601 UTC timestamp
- **Event Type**: Authentication, authorization, data access
- **Result**: Success/failure with error codes

### Regulatory Considerations
- **Financial Data**: Follow relevant financial regulations for market data handling
- **Data Protection**: Comply with applicable privacy laws (GDPR, CCPA)
- **Audit Trails**: Maintain immutable logs for regulatory reporting

### Security Metrics
- Authentication failure rate: Target <1% of requests
- Time to detect security events: Target <5 minutes
- Time to contain security incidents: Target <1 hour
- Security patch deployment time: Target <24 hours for critical vulnerabilities
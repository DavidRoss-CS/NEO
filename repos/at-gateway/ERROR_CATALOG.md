# Gateway Error Catalog

| Code | HTTP Status | Title | When It Happens | Operator Fix | Client Fix | Telemetry |
|------|-------------|-------|-----------------|--------------|------------|----------|
| GW-001 | 401 | Invalid signature | HMAC verification fails or signature header malformed | Check if API_KEY_HMAC_SECRET rotated without client update | Verify signature calculation and secret | `gateway_validation_errors_total{type=\"signature\"}`, `gateway_webhook_duration_seconds{status_class=\"4xx\"}`, log: `corr_id`, `client_ip`, `signature_len`, `expected_format` |
| GW-002 | 401 | Replay window exceeded | Request timestamp outside REPLAY_WINDOW_SEC or nonce reused | Check client clock skew, increase window if needed | Ensure timestamp is current and nonce is unique | `gateway_validation_errors_total{type=\"replay\"}`, `gateway_webhook_duration_seconds{status_class=\"4xx\"}`, log: `corr_id`, `timestamp_provided`, `window_sec`, `clock_skew_ms` |
| GW-003 | 422 | Payload schema invalid | JSON doesn't match expected schema or required fields missing | No operator action needed unless schema change | Fix payload structure per API_SPEC.md | `gateway_validation_errors_total{type=\"schema\"}`, `gateway_webhook_duration_seconds{status_class=\"4xx\"}`, log: `corr_id`, `validation_errors`, `payload_size`, `schema_version` |
| GW-004 | 429 | Rate limit exceeded | Client exceeds RATE_LIMIT_RPS threshold | Tune rate limits or add burst capacity | Implement exponential backoff, respect retry_after | `gateway_rate_limit_exceeded_total{source}`, `gateway_webhook_duration_seconds{status_class=\"4xx\"}`, headers: `Retry-After`, log: `corr_id`, `current_rate`, `limit`, `source` |
| GW-005 | 503 | NATS unavailable | Cannot publish to NATS stream or connection lost | Check NATS server status, restart if needed | Retry request after service recovery | `gateway_nats_errors_total{type=\"connection\"}`, `gateway_webhook_duration_seconds{status_class=\"5xx\"}`, log: `corr_id`, `nats_status`, `last_success`, `connection_attempts` |
| GW-006 | 409 | Idempotency conflict | Same idempotency key used for different payload | No action if legitimate duplicate, investigate if suspicious | Use unique keys or ensure payload matches original | `gateway_idempotency_conflicts_total`, `gateway_webhook_duration_seconds{status_class=\"4xx\"}`, log: `corr_id`, `idempotency_key`, `original_corr_id`, `payload_hash` |
| GW-007 | 400 | Source not allowed | Request source not in ALLOWED_SOURCES list | Add source to allowlist if legitimate | Use approved source identifier | `gateway_validation_errors_total{type=\"source\"}`, `gateway_webhook_duration_seconds{status_class=\"4xx\"}`, log: `corr_id`, `source_provided`, `allowed_sources` |
| GW-008 | 413 | Payload too large | Request body exceeds maximum size limit | Consider increasing limit if legitimate use case | Reduce payload size or compress data | `gateway_validation_errors_total{type=\"size\"}`, `gateway_webhook_duration_seconds{status_class=\"4xx\"}`, log: `corr_id`, `payload_size`, `max_size` |
| GW-009 | 500 | Normalization failed | Error during payload transformation to canonical format | Check normalization logic, may need schema update | Verify payload format matches expected structure | `gateway_normalization_errors_total{source}`, `gateway_webhook_duration_seconds{status_class=\"5xx\"}`, log: `corr_id`, `error_details`, `raw_payload`, `normalization_step` |
| GW-010 | 503 | Consumer lag critical | NATS consumer lag exceeds threshold, backpressure engaged | Check downstream consumer health, scale if needed | Reduce request rate temporarily | `gateway_backpressure_total`, `gateway_webhook_duration_seconds{status_class=\"5xx\"}`, log: `corr_id`, `consumer_lag`, `threshold`, `backpressure_duration` |
| GW-011 | 503 | Maintenance mode enabled | Service in maintenance mode, MAINTENANCE_MODE=true | Unset MAINTENANCE_MODE flag or schedule window end | Retry after maintenance window, respect Retry-After | `gateway_maintenance_mode_total`, `gateway_webhook_duration_seconds{status_class=\"5xx\"}`, headers: `Retry-After`, log: `corr_id`, `maintenance=true`, `window_end` |

## Latency Telemetry

All requests, including failures, must record processing duration in `gateway_webhook_duration_seconds` histogram with labels:
- `status_class`: "2xx", "4xx", or "5xx"
- `endpoint`: "/webhook/tradingview", "/webhook/generic", "/healthz"
- `source`: Request source identifier (if available)

Duration measurement starts at request ingress and ends at response transmission. Include authentication, validation, normalization, and NATS publishing time.

## Error Response Examples

### GW-001: Invalid Signature (401)
```json
{
  "error": "invalid_signature",
  "code": "GW-001",
  "message": "HMAC signature verification failed",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "signature_provided": "sha256=abc123...",
    "algorithm": "HMAC-SHA256",
    "expected_format": "sha256=<hex_digest>"
  }
}
```

### GW-004: Rate Limit Exceeded (429)
```json
{
  "error": "rate_limit_exceeded",
  "code": "GW-004",
  "message": "Request rate exceeded for source",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "current_rate": 105,
    "limit": 100,
    "source": "tradingview",
    "retry_after_seconds": 60
  }
}
```
**Headers**: `Retry-After: 60`

### GW-005: NATS Unavailable (503)
```json
{
  "error": "nats_unavailable",
  "code": "GW-005",
  "message": "Cannot publish to NATS stream",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "nats_status": "disconnected",
    "last_success": "2024-01-15T10:29:45Z",
    "connection_attempts": 3
  }
}
```

### GW-011: Maintenance Mode (503)
```json
{
  "error": "maintenance_mode",
  "code": "GW-011",
  "message": "Service temporarily unavailable for maintenance",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "maintenance": true,
    "maintenance_window": "2024-01-15T10:00:00Z to 2024-01-15T11:00:00Z",
    "retry_after_seconds": 1800
  }
}
```
**Headers**: `Retry-After: 1800`

## Client Retry Matrix

| Status Code | Error Codes | Retry Policy | Notes |
|-------------|-------------|--------------|-------|
| 401, 403 | GW-001, GW-002 | Do not retry | Fix authentication/authorization |
| 400, 422 | GW-003, GW-007 | Do not retry | Fix payload or configuration |
| 409 | GW-006 | Do not retry unless same payload | Idempotency conflict |
| 413 | GW-008 | Do not retry | Reduce payload size |
| 429 | GW-004 | Retry with backoff | Honor `Retry-After` header |
| 500 | GW-009 | Retry up to 3 times | Exponential backoff |
| 503 | GW-005, GW-010 | Retry up to 3 times | Service/infrastructure issue |
| 503 | GW-011 | Retry after maintenance window | Honor `Retry-After` header |

**Recommended backoff**: Start at 1s, double each retry, max 60s

## Client Error Handling

### Monitoring
Clients should monitor:
- Error rate by code and source
- Latency distribution (p95, p99)
- Retry success rates
- Authentication failure patterns
- Rate limit hit frequency

### Circuit Breaker
Implement circuit breaker pattern:
- Open circuit after 5 consecutive 5xx errors
- Half-open after 30s timeout
- Close circuit after 3 successful requests

## Operator Runbook References

For incident response procedures, see [RUNBOOK.md](RUNBOOK.md) sections:

- **GW-001, GW-002**: ["Invalid signature spikes"](RUNBOOK.md#invalid-signature-spikes)
- **GW-004**: ["High 429s (Rate Limiting)"](RUNBOOK.md#high-429s-rate-limiting)
- **GW-005**: ["503 to NATS"](RUNBOOK.md#503-to-nats)
- **GW-011**: ["Emergency Stop"](RUNBOOK.md#emergency-stop)

For complete API documentation, see [API_SPEC.md](API_SPEC.md).

## Error Response Format

All error responses follow this standard structure as defined in [API_SPEC.md](API_SPEC.md):

```json
{
  "error": "human_readable_title",
  "code": "GW-XXX",
  "message": "Detailed explanation",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "field_specific": "context"
  }
}
```
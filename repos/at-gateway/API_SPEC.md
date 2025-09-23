# Gateway API Specification

## Base URL

`http://localhost:8001` (development)

All requests must use `Content-Type: application/json; charset=utf-8`

For complete error code reference, see [ERROR_CATALOG.md](ERROR_CATALOG.md). For operational procedures, see [RUNBOOK.md](RUNBOOK.md).

## Authentication

All webhook endpoints require HMAC-SHA256 authentication with replay protection.

### Authentication Headers

All webhook requests must include the following headers:

| Header | Required | Description |
|--------|----------|-------------|
| `X-Signature` | Yes | HMAC-SHA256 signature of request body |
| `X-Timestamp` | Yes | Unix timestamp of request (for replay protection) |
| `X-Nonce` | Yes | Unique request identifier |
| `Idempotency-Key` | Yes | Duplicate request prevention key |
| `X-API-Version` | Yes | API version (e.g., "1.0.0") |
| `Content-Type` | Yes | Must be "application/json" |

**Signature Calculation:**
```
Signature = HMAC-SHA256(secret, timestamp + nonce + body)
```

**Request Size Limit:** 1MB maximum payload size.

### Validation Process
1. Verify `Content-Type` header is present and correct
2. Check request body size ≤ 1MB (413 if exceeded)
3. Parse `X-Timestamp` and verify within `REPLAY_WINDOW_SEC` ± 30s clock skew (401 GW-002 if outside window)
4. Check `X-Nonce` hasn't been used within replay window (401 GW-002 if duplicate)
5. Compute HMAC-SHA256 over raw request body bytes using `API_KEY_HMAC_SECRET`
6. Compare computed signature with `X-Signature` using constant-time comparison (401 GW-001 if mismatch)
7. Verify source is in `ALLOWED_SOURCES` (400 GW-007 if forbidden)

**Replay Window**: `REPLAY_WINDOW_SEC` (default: 300 seconds)
**Clock Skew Tolerance**: ±30 seconds from gateway server time

### Complete Authentication Example
```bash
# Generate signature for TradingView webhook
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
NONCE=$(uuidgen)
BODY='{"ticker":"EURUSD","action":"buy","price":1.0945,"time":"'$TIMESTAMP'"}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "your-256-bit-secret" | cut -d' ' -f2)

curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json; charset=utf-8" \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-Nonce: $NONCE" \
  -H "X-Signature: sha256=$SIGNATURE" \
  -d "$BODY"
```

## Idempotency

### Header
`Idempotency-Key`: UUID4 or unique string (optional)

### Behavior
- **Client-provided**: Use exact key from header
- **Auto-derived**: `hash(source + "|" + instrument + "|" + timestamp)` if header absent
- **Conflict detection**: Return 409 (GW-006) if same key used with different request body

### Expiration Policy
- **TTL**: `IDEMPOTENCY_TTL_SEC` (default: 3600 seconds)
- **Storage**: In-memory cache by default; persistent cache is planned enhancement
- **Cleanup**: Keys automatically expire after TTL

## Rate Limiting

**Global Limit**: `RATE_LIMIT_RPS` requests per second (default: 100)
**Enforcement**: Per-source tracking with sliding window

### 429 Response
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
    "source": "tradingview"
  }
}
```

**Headers**: `Retry-After: 60` (seconds until rate limit resets)

## Payload Limits

- **Maximum body size**: 1MB
- **Violation response**: 413 (GW-008)
- **Encoding**: UTF-8 JSON only

## Endpoints

### POST /webhook/tradingview

Accepts TradingView alerts in their native JSON format.

#### Request Schema
- `ticker` (string, required): Alphanumeric instrument identifier
- `action` (string, optional): One of ["buy", "sell", "close"]
- `price` (number, required): Positive decimal price
- `time` (string, required): ISO8601 timestamp
- `strategy` (string, optional): Strategy identifier
- `strength` (number, optional): Float 0.0-1.0 signal strength

#### Request Example
```json
{
  "ticker": "EURUSD",
  "action": "buy",
  "price": 1.0945,
  "time": "2024-01-15T10:30:00Z",
  "strategy": "momentum_v1",
  "strength": 0.75
}
```

#### Response 202
```json
{
  "status": "accepted",
  "corr_id": "req_abc123def456",
  "idempotency_key": "derived_or_provided_key",
  "timestamp": "2024-01-15T10:30:00.123Z"
}
```

**Events Emitted**:
1. `signals.raw` - Immediate raw webhook data
2. `signals.normalized` - Processed canonical format

### POST /webhook/generic

Accepts any JSON payload with required envelope fields.

#### Request Schema
- `source` (string, required): Must be in `ALLOWED_SOURCES`
- `instrument` (string, required): Instrument identifier
- `timestamp` (string, required): ISO8601 timestamp
- `payload` (object, required): Arbitrary JSON object

#### Request Example
```json
{
  "source": "custom_system",
  "instrument": "BTCUSD",
  "timestamp": "2024-01-15T10:30:00Z",
  "payload": {
    "price": 45000.0,
    "volume": 1.5,
    "signal_type": "momentum",
    "metadata": {
      "confidence": 0.8
    }
  }
}
```

#### Response 202
Same format as TradingView endpoint.

**Events Emitted**: Same as TradingView endpoint.

### GET /healthz

Service health check endpoint.

#### Response 200
```json
{
  "ok": true,
  "uptime_s": 3600,
  "nats": "connected",
  "version": "1.0.0"
}
```

#### Response Fields
- `ok` (boolean): Overall service health
- `uptime_s` (integer): Seconds since service start
- `nats` (string): Connection status - "connected", "degraded", or "disconnected"
- `version` (string): Service version

### GET /metrics

Prometheus metrics endpoint.

**Response**: Prometheus exposition format (text/plain)
**Authentication**: None required in development

## Normalization Rules

### TradingView → signals.normalized

| TradingView Field | Normalized Field | Transformation |
|-------------------|------------------|----------------|
| `ticker` | `instrument` | Direct mapping |
| `price` | `price` | Direct mapping |
| `action` | `side` | "buy"/"sell" → same; "close" → null |
| `strength` | `strength` | Direct mapping (optional) |
| `time` | `timestamp` | Parse to UTC ISO8601 |
| - | `source` | Set to "tradingview" |
| - | `normalized_at` | Current timestamp |

### Event Examples

#### Raw Event (signals.raw)
```json
{
  "corr_id": "req_abc123def456",
  "source": "tradingview",
  "received_at": "2024-01-15T10:30:00.123Z",
  "idempotency_key": "hash_abc123",
  "payload": {
    "ticker": "EURUSD",
    "action": "buy",
    "price": 1.0945,
    "time": "2024-01-15T10:30:00Z",
    "strategy": "momentum_v1"
  }
}
```

#### Normalized Event (signals.normalized)
```json
{
  "corr_id": "req_abc123def456",
  "source": "tradingview",
  "instrument": "EURUSD",
  "price": 1.0945,
  "side": "buy",
  "strength": null,
  "timestamp": "2024-01-15T10:30:00Z",
  "normalized_at": "2024-01-15T10:30:00.145Z",
  "strategy": "momentum_v1"
}
```

## Error Responses

### Standard Error Schema
```json
{
  "error": "human_readable_title",
  "code": "GW-XXX",
  "message": "Detailed explanation",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "context_specific": "fields"
  }
}
```

### Common Error Examples

#### 401 Invalid Signature (GW-001)
```json
{
  "error": "invalid_signature",
  "code": "GW-001",
  "message": "HMAC signature verification failed",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "signature_provided": "sha256=abc123...",
    "algorithm": "HMAC-SHA256"
  }
}
```
See [ERROR_CATALOG.md](ERROR_CATALOG.md) GW-001 for details.

#### 422 Schema Validation Failed (GW-003)
```json
{
  "error": "payload_schema_invalid",
  "code": "GW-003",
  "message": "Required field 'ticker' missing",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "validation_errors": [
      "Field 'ticker' is required",
      "Field 'price' must be positive number"
    ]
  }
}
```
See [ERROR_CATALOG.md](ERROR_CATALOG.md) GW-003 for details.

#### 429 Rate Limit Exceeded (GW-004)
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
    "source": "tradingview"
  }
}
```
**Headers**: `Retry-After: 60`
See [ERROR_CATALOG.md](ERROR_CATALOG.md) GW-004 for details.

#### 503 NATS Unavailable (GW-005)
```json
{
  "error": "nats_unavailable",
  "code": "GW-005",
  "message": "Cannot publish to NATS stream",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "nats_status": "disconnected",
    "last_success": "2024-01-15T10:29:45Z"
  }
}
```
See [ERROR_CATALOG.md](ERROR_CATALOG.md) GW-005 for details.

#### 503 Maintenance Mode (GW-011)
```json
{
  "error": "maintenance_mode",
  "code": "GW-011",
  "message": "Service temporarily unavailable for maintenance",
  "corr_id": "req_abc123def456",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "details": {
    "maintenance_window": "2024-01-15T10:00:00Z to 2024-01-15T11:00:00Z"
  }
}
```
*Note: GW-011 reserved for future ERROR_CATALOG.md expansion*

## Security Implementation

### HMAC Verification Steps
1. Extract raw request body as bytes (before any JSON parsing)
2. Compute HMAC-SHA256 using `API_KEY_HMAC_SECRET` over raw body bytes
3. Format as `sha256=<lowercase_hex_digest>`
4. Perform constant-time string comparison with `X-Signature` header
5. Reject request immediately if comparison fails

### Replay Defense Algorithm
1. Parse `X-Timestamp` and validate format
2. Check timestamp is within `REPLAY_WINDOW_SEC` ± 30s of current time
3. Extract `X-Nonce` and validate UUID4 format
4. Check nonce hasn't been seen within replay window
5. Store nonce in cache with TTL = `REPLAY_WINDOW_SEC`
6. Reject if any check fails

### Source Allowlist
- Check derived source ("tradingview" for `/webhook/tradingview`) or `source` field against `ALLOWED_SOURCES`
- Case-sensitive exact matching
- Return 400 (GW-007) if source not in allowlist

## API Versioning

### Version Header
`X-API-Version: 1.0` (optional, defaults to latest)

### Compatibility Policy
Follows [ADR-0002](../../DECISIONS/ADR-0002-event-contracts.md):
- **Minor versions**: Backward compatible (new optional fields only)
- **Major versions**: Breaking changes with 90-day deprecation notice
- **Dual-accept period**: During deprecation, gateway accepts both old and new versions
- **Client migration**: Clients should specify version explicitly for stability

## Observability

Follows [ADR-0003](../../DECISIONS/ADR-0003-observability.md) conventions.

### Metrics Emitted Per Request
- `gateway_webhooks_received_total{source, status}` - Counter of webhook requests
- `gateway_webhook_duration_seconds{source}` - Histogram of processing latency
- `gateway_nats_publish_total{subject, status}` - Counter of NATS publications
- `gateway_validation_errors_total{type}` - Counter of validation failures

### Log Fields
Structured JSON logs include:
- `corr_id` - Correlation ID for request tracing
- `client_ip` - Source IP address
- `source` - Request source identifier
- `instrument` - Trading instrument (if present)
- `status` - HTTP response status
- `latency_ms` - Request processing time
- `validation_status` - Authentication/validation result

### Correlation ID Propagation
- Generated at gateway ingress
- Included in all NATS event headers
- Propagated to downstream services
- Used for distributed tracing across system
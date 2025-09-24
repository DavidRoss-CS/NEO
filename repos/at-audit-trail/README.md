# Audit Trail Service

Immutable audit logging system for the agentic trading platform providing complete traceability of all trading decisions with cryptographic integrity.

## Features

- **Immutable Event Log**: Hash-chained events prevent tampering
- **Complete Traceability**: All trading decisions and rationale captured
- **Compliance Reporting**: Pre-built reports for regulatory requirements
- **Query API**: Flexible search and retrieval capabilities
- **Real-time Monitoring**: Automatic capture from NATS event stream

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   NATS      │───▶│ Audit Trail  │───▶│   SQLite    │
│ Event Stream│    │   Service    │    │ Database    │
└─────────────┘    └──────────────┘    └─────────────┘
       │                   │                   │
       │                   ▼                   │
       │           ┌─────────────┐             │
       │           │ Hash Chain  │             │
       │           │ Validation  │             │
       │           └─────────────┘             │
       │                                       │
       ▼                                       ▼
┌─────────────┐                       ┌─────────────┐
│ Compliance  │                       │ Immutable   │
│ Reports     │                       │ Storage     │
└─────────────┘                       └─────────────┘
```

## Hash Chain Integrity

Each audit event contains:
- **Event Hash**: SHA-256 of event content + previous hash
- **Previous Hash**: Creates tamper-evident chain
- **Timestamp**: Immutable ordering
- **Metadata**: Additional context and correlation

## API Endpoints

### Health & Monitoring

```bash
# Health check with chain validation
curl localhost:8009/healthz

# Prometheus metrics
curl localhost:8009/metrics

# Validate hash chain integrity
curl localhost:8009/audit/validate?limit=100
```

### Recording Events

```bash
# Manual event recording
curl -X POST localhost:8009/audit \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "manual_decision",
    "timestamp": "2025-09-23T10:00:00Z",
    "correlation_id": "test_123",
    "service": "manual",
    "data": {
      "decision": "BUY",
      "instrument": "AAPL",
      "rationale": "Strong momentum signals"
    }
  }'
```

### Querying Events

```bash
# Query by correlation ID
curl "localhost:8009/audit/query?correlation_id=req_12345678"

# Query by event type
curl "localhost:8009/audit/query?event_type=decisions.order_intent"

# Query by service
curl "localhost:8009/audit/query?service=gateway"

# Query by time range
curl "localhost:8009/audit/query?start_time=2025-09-23T00:00:00Z&end_time=2025-09-23T23:59:59Z"

# Combined filters
curl "localhost:8009/audit/query?event_type=signals.normalized&service=gateway&limit=50"
```

### Audit Flow Tracing

```bash
# Get complete flow for a correlation ID
curl localhost:8009/audit/flow/req_12345678
```

**Example Response:**
```json
{
  "correlation_id": "req_12345678",
  "event_count": 4,
  "start_time": "2025-09-23T10:00:00Z",
  "end_time": "2025-09-23T10:00:05Z",
  "services_involved": ["gateway", "agent", "exec"],
  "events": [
    {
      "event_id": "evt_abc123",
      "event_type": "signals.normalized",
      "service": "gateway",
      "timestamp": "2025-09-23T10:00:00Z",
      "data": {
        "instrument": "AAPL",
        "signal": "BUY",
        "strength": 0.75
      }
    },
    {
      "event_id": "evt_def456",
      "event_type": "decisions.order_intent",
      "service": "agent",
      "timestamp": "2025-09-23T10:00:02Z",
      "data": {
        "side": "buy",
        "quantity": 100,
        "confidence": 0.8,
        "reasoning": "Momentum strategy triggered"
      }
    }
  ]
}
```

### Compliance Reports

```bash
# Decision audit report
curl -X POST "localhost:8009/audit/compliance/report?report_type=decision_audit&start_date=2025-09-01T00:00:00Z&end_date=2025-09-30T23:59:59Z"

# Risk violations report
curl -X POST "localhost:8009/audit/compliance/report?report_type=risk_violations&start_date=2025-09-01T00:00:00Z&end_date=2025-09-30T23:59:59Z"
```

## Event Types Captured

The audit service automatically captures all events from the NATS stream:

| Event Type | Source | Description |
|------------|--------|-------------|
| `signals.normalized` | Gateway | Processed trading signals |
| `signals.raw` | Gateway | Raw incoming signals |
| `decisions.order_intent` | Agent | Trading decisions with rationale |
| `executions.fill` | Exec-Sim | Order execution results |
| `risk_violation` | Meta-Agent | Risk limit violations |
| `strategy_reload` | Strategy-Manager | Strategy updates |

## Database Schema

### audit_events Table

```sql
CREATE TABLE audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    correlation_id TEXT,
    service TEXT NOT NULL,
    data TEXT NOT NULL,          -- JSON
    metadata TEXT,               -- JSON
    previous_hash TEXT,
    event_hash TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE(event_hash)
);
```

### Indexes

- `idx_correlation_id`: Fast correlation ID lookups
- `idx_timestamp`: Time-based queries
- `idx_event_type`: Event type filtering
- `idx_service`: Service-based filtering

## Compliance Features

### Regulatory Requirements

- **MiFID II**: Transaction reporting and best execution
- **Dodd-Frank**: Swap data reporting
- **EMIR**: Trade reporting and risk mitigation
- **Custom**: Configurable compliance rules

### Report Types

1. **Decision Audit**: All trading decisions with rationale
2. **Risk Violations**: Risk limit breaches and actions
3. **Flow Integrity**: Complete signal-to-execution flows
4. **Performance Analytics**: Decision accuracy and timing

### Data Retention

- **Hot Storage**: 1 year in SQLite
- **Cold Storage**: Archive to external systems
- **Legal Hold**: Indefinite retention for investigations

## Monitoring & Alerting

### Prometheus Metrics

```promql
# Events recorded per second
rate(audit_events_recorded_total[5m])

# Hash validation status
audit_hash_validations_total

# Database size growth
audit_storage_size_bytes

# Query performance
histogram_quantile(0.95, rate(audit_query_duration_seconds_bucket[5m]))
```

### Grafana Dashboards

- **Audit Overview**: Event rates and storage metrics
- **Compliance Dashboard**: Violation tracking and reporting
- **Chain Integrity**: Hash validation status

### Alerts

```yaml
- alert: AuditChainCorruption
  expr: audit_hash_validations_total{status="failed"} > 0
  for: 0s
  labels:
    severity: critical
  annotations:
    summary: "Audit trail hash chain corruption detected"

- alert: AuditServiceDown
  expr: up{job="audit-trail"} == 0
  for: 30s
  labels:
    severity: critical
  annotations:
    summary: "Audit trail service is down"
```

## Security Considerations

### Immutability
- Hash chaining prevents retroactive modifications
- SQLite database with append-only operations
- Cryptographic integrity verification

### Access Control
- Read-only API for most operations
- Administrative functions require authentication
- Audit log for API access (self-auditing)

### Backup & Recovery
- Regular database backups to secure storage
- Point-in-time recovery capabilities
- Multi-region replication for disaster recovery

## Development & Testing

### Local Development

```bash
# Start audit service
docker compose up audit

# Check logs
docker compose logs audit

# Access API docs
open http://localhost:8009/docs
```

### Testing

```bash
# Unit tests
cd repos/at-audit-trail
python -m pytest tests/

# Integration tests
make test-audit-integration

# Load testing
make test-audit-load
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://nats:4222` | NATS server URL |
| `NATS_STREAM` | `trading-events` | NATS stream name |
| `AUDIT_STORAGE_PATH` | `/app/audit_logs` | Database storage path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `PORT` | `8009` | HTTP server port |

### Performance Tuning

- **Batch Size**: Adjust NATS consumer batch size
- **Database WAL**: Enable Write-Ahead Logging for performance
- **Index Optimization**: Add custom indexes for specific queries
- **Compression**: Enable database compression for storage efficiency
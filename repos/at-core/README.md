# at-core
Ports, prompts, and contract governance.

## Environment Variables

| Variable | Sample Value | Description |
|----------|--------------|-------------|
| `SERVICE_NAME` | `at-core` | Service identifier for logs/metrics |
| `NATS_URL` | `nats://localhost:4222` | NATS server connection |
| `NATS_STREAM` | `trading-events` | JetStream stream name |
| `NATS_DURABLE` | `core-consumer` | Durable consumer name |
| `NATS_SUBJECTS_PREFIX` | `signals,decisions,executions` | Subject namespace prefixes |
| `IDEMPOTENCY_TTL_SEC` | `3600` | Duplicate detection window |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENV` | `development` | Environment name |
# NATS Bootstrap Init Job

Automatic NATS JetStream initialization service that creates streams and consumers for the trading system.

## Purpose

This service runs as an init container in docker-compose to:
- Create the main `trading-events` stream with proper subjects
- Set up durable consumers for each service
- Ensure idempotent operations (safe to run multiple times)
- Provide proper error handling and retry logic

## Streams Created

### trading-events
- **Subjects**: `signals.*`, `decisions.*`, `executions.*`
- **Storage**: File-based
- **Retention**: 7 days, 1M messages max
- **Deduplication**: 2-minute window

## Consumers Created

| Consumer | Filter | Service | Purpose |
|----------|--------|---------|---------|
| `mcp-signals` | `signals.normalized` | at-agent-mcp | Process trading signals |
| `exec-intents` | `decisions.order_intent` | at-exec-sim | Execute order intents |
| `meta-decisions` | `decisions.*` | at-meta-agent | Coordinate multi-agent decisions |
| `audit-all` | `""` (all) | audit-service | Audit trail logging |

## Configuration

Environment variables:

- `NATS_URL`: NATS server URL (default: `nats://nats:4222`)
- `STREAM_NAME`: Stream name (default: `trading-events`)
- `MAX_RETRIES`: Connection retries (default: 30)
- `RETRY_DELAY`: Delay between retries in seconds (default: 2)

## Usage in Docker Compose

```yaml
services:
  nats-init:
    build: ./repos/at-nats-init
    depends_on:
      - nats
    environment:
      - NATS_URL=nats://nats:4222
    restart: "no"  # Run once
```

## Manual Execution

```bash
docker run --rm --network trading_default \
  -e NATS_URL=nats://nats:4222 \
  at-nats-init:latest
```
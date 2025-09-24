# AI Collaboration Guide

**Purpose**: Enable multiple AI assistants to work on this codebase concurrently without conflicts.

## Quick Start for AI Assistants

```bash
# 1. Read these first (in order)
SYSTEM_OVERVIEW.md     # Understand architecture
CONTRACT.md            # Learn event schemas
CURRENT_STATE.md       # Know what works/broken
TASK_ASSIGNMENTS.md    # See available tasks

# 2. Claim a task
# Update TASK_ASSIGNMENTS.md immediately

# 3. Create feature branch
git checkout -b feature/your-task

# 4. Test frequently
./quick_verify.sh      # After any changes
```

## Essential Context

### System Architecture
- **Event-driven**: NATS JetStream for all async communication
- **Pull-based consumers**: Explicit acknowledgment required
- **HMAC authentication**: All webhooks need signatures
- **Correlation IDs**: Required for tracing and idempotency

### Critical Files - DO NOT MODIFY
```yaml
Stable/Working - Do Not Touch:
  - repos/at-exec-sim/src/at_exec_sim/nats_client.py  # Resilient consumer
  - repos/at-gateway/at_gateway/app.py                # HMAC validation
  - docker-compose.dev.yml                             # Working config
  - All NATS consumer configurations                   # Verified working
```

### Known Issues to Avoid
1. **Consumer name mismatch**: Use configured `durable_name`, not hardcoded
2. **Schema validation**: Set `additionalProperties: true` for flexibility
3. **Async callbacks**: All NATS callbacks must be `async def`
4. **Print statements**: Use structured logging with `correlation_id`

## Task Coordination

### Before Starting Work
```python
# 1. Check task is available
# Read TASK_ASSIGNMENTS.md

# 2. Claim the task immediately
# Update TASK_ASSIGNMENTS.md with your ID

# 3. Commit the claim
git add TASK_ASSIGNMENTS.md
git commit -m "chore: claiming task - [task name]"
git push

# 4. Create feature branch
git checkout -b feature/your-task-name
```

### While Working
```python
# Required in all logs
logger.info("Processing event",
           corr_id=correlation_id,
           service="your-service")

# Required for all events
event = {
    "correlation_id": str(uuid.uuid4()),
    "timestamp": datetime.utcnow().isoformat(),
    # ... your fields
}

# Required for metrics
your_operation_total.labels(status="success").inc()
```

### Code Patterns to Follow

#### NATS Publishing
```python
# ALWAYS include correlation_id
await nats_client.js.publish(
    "trading-events.signals",
    json.dumps({
        "correlation_id": corr_id,
        "timestamp": datetime.utcnow().isoformat(),
        "signal": signal_data
    }).encode()
)
```

#### NATS Consuming
```python
# Use resilient consumer pattern from at_exec_sim/nats_client.py
async def message_handler(msg):
    try:
        data = json.loads(msg.data.decode())
        corr_id = data.get("correlation_id", "unknown")
        logger.info("Processing", corr_id=corr_id)

        # Process message
        await process(data)

        # MUST acknowledge
        await msg.ack()
    except Exception as e:
        logger.error("Failed", error=str(e))
        # Let NATS retry
```

#### Error Handling
```python
# NEVER use bare except
try:
    result = process_order(order)
except ValidationError as e:
    logger.error("Validation failed",
                error=str(e),
                corr_id=corr_id)
    raise  # Re-raise for proper handling
except Exception as e:
    logger.error("Unexpected error",
                error=str(e),
                corr_id=corr_id)
    raise
```

## Testing Requirements

### Before ANY Commit
```bash
# 1. Smoke test MUST pass
./test_smoke_ci.sh

# 2. Check for secrets
grep -r "password\|secret\|key" --include="*.py"

# 3. Verify metrics work
curl http://localhost:8001/metrics | grep your_metric

# 4. Check health endpoints
make health
```

### Golden Path Test
```bash
# Full end-to-end test
make golden

# Verify counters increment
make metrics
```

## Common Pitfalls

### 1. Breaking NATS Consumers
```python
# ❌ WRONG - Hardcoded consumer name
info = await js.consumer_info("trading-events", "my-consumer")

# ✅ CORRECT - Use configured name
info = await js.consumer_info("trading-events", self.durable_name)
```

### 2. Missing Correlation IDs
```python
# ❌ WRONG - No tracing
logger.info("Processing order")

# ✅ CORRECT - Always include correlation_id
logger.info("Processing order",
           corr_id=data.get("correlation_id"),
           order_id=order["id"])
```

### 3. Schema Too Strict
```python
# ❌ WRONG - Breaks on unknown fields
schema = {
    "type": "object",
    "additionalProperties": False  # Too strict!
}

# ✅ CORRECT - Forward compatible
schema = {
    "type": "object",
    "additionalProperties": True  # Allow extras
}
```

### 4. Synchronous in Async Context
```python
# ❌ WRONG - Blocks event loop
def fetch_data():
    response = requests.get(url)  # Blocking!
    return response.json()

# ✅ CORRECT - Fully async
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

## Environment Setup

### Required Environment Variables
```bash
# Core - MUST be set
API_KEY_HMAC_SECRET=test-secret
NATS_URL=nats://nats:4222
NATS_STREAM=trading-events
NATS_DURABLE=[your-service]-consumer

# Optional but recommended
LOG_LEVEL=INFO
REDIS_URL=redis://redis:6379
```

### Docker Commands
```bash
# Start everything
docker compose -f docker-compose.dev.yml up -d

# Watch logs (useful for debugging)
docker compose -f docker-compose.dev.yml logs -f [service]

# Restart a service after changes
docker compose -f docker-compose.dev.yml restart [service]

# Clean restart
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up -d
```

## Documentation Updates

When adding features, update:
1. **CONTRACT.md** - If adding new events/APIs
2. **CURRENT_STATE.md** - Mark features as working
3. **ERROR_CATALOG.md** - Document new error cases
4. **Service README** - Update service-specific docs

## Debugging Tips

### NATS Issues
```bash
# Check stream exists
docker run --rm -it --network agentic-trading-architecture-full_default \
  natsio/nats-box:latest \
  nats -s nats://nats:4222 stream info trading-events

# Check consumers
docker run --rm -it --network agentic-trading-architecture-full_default \
  natsio/nats-box:latest \
  nats -s nats://nats:4222 consumer ls trading-events
```

### Service Not Responding
```bash
# Check if running
docker ps | grep [service-name]

# Check logs
docker logs agentic-trading-architecture-full-[service]-1

# Check health
curl http://localhost:[port]/healthz
```

### Message Not Processing
```python
# Add debug logging
logger.debug("Received message",
            raw_data=msg.data.decode(),
            subject=msg.subject,
            corr_id=corr_id)

# Check acknowledgment
logger.info("Message acknowledged", corr_id=corr_id)
```

## Commit Standards

### Commit Messages
```bash
# Format: type(scope): description

feat(gateway): add retry logic for webhooks
fix(exec-sim): correct fill price calculation
docs: update CONTRACT.md with new event
test: add unit tests for agent decision logic
chore: update dependencies
```

### Pull Request Checklist
```markdown
- [ ] Claimed task in TASK_ASSIGNMENTS.md
- [ ] Smoke tests pass (./test_smoke_ci.sh)
- [ ] No hardcoded secrets
- [ ] Correlation IDs in all logs
- [ ] Metrics exposed for new operations
- [ ] Documentation updated
- [ ] Error handling with context
```

## Parallel Work Guidelines

### Safe to Work On Simultaneously
- Different services (one AI per service)
- Different broker adapters
- Documentation improvements
- Test additions
- Grafana dashboards

### Requires Coordination
- NATS stream/consumer changes
- Schema modifications
- Shared library updates (at-core)
- Docker compose changes
- Database schema changes

## Quick Reference

### Service Ports
```yaml
Gateway:    8001
Agent:      8002
Exec-Sim:   8004
Audit:      8005
Grafana:    3000
Prometheus: 9090
```

### NATS Subjects
```yaml
Signals:    trading-events.signals
Intents:    trading-events.intents
Orders:     trading-events.orders
Fills:      trading-events.fills
```

### Key Files
```yaml
Schemas:     CONTRACT.md
Architecture: SYSTEM_OVERVIEW.md
Tasks:       TASK_ASSIGNMENTS.md
Status:      CURRENT_STATE.md
Standards:   DEVELOPMENT_STANDARDS.md
```

## Getting Help

### From Documentation
1. Check ERROR_CATALOG.md for common errors
2. Review SYSTEM_OVERVIEW.md for architecture
3. See CONTRACT.md for schemas

### From Code
```bash
# Find examples of pattern
grep -r "pattern" repos/ --include="*.py"

# Find where something is used
grep -r "function_name" repos/
```

### From Git History
```bash
# See what changed recently
git log --oneline -20

# See who worked on file
git blame [file]

# See changes to file
git log -p [file]
```

## Performance Considerations

### Don't Block Event Loop
- Use `async`/`await` consistently
- Avoid synchronous I/O in async functions
- Use `asyncio.create_task()` for parallel work

### Batch Operations
- Process messages in batches when possible
- Use bulk database inserts
- Aggregate metrics before sending

### Resource Limits
- Keep Docker memory under 4GB total
- Limit concurrent connections
- Use connection pooling

## Security Reminders

### Never Commit
- API keys or secrets
- Passwords or tokens
- Private keys or certificates
- Production URLs with credentials

### Always Validate
- Input schemas
- HMAC signatures
- Content types
- Request sizes

### Use Environment Variables
```python
# ❌ WRONG
API_KEY = "sk_live_abc123"

# ✅ CORRECT
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise SystemExit("API_KEY required")
```

---

**Remember**:
- Clear communication prevents conflicts
- Test frequently to catch issues early
- Update documentation as you go
- Ask questions in comments/PRs if unsure

Good luck! 🚀
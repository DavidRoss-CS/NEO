# Error Catalog

## Common Errors and Solutions

### NATS Connection Errors

#### NAT-001: No Servers Available
```
Error: nats.aio.errors.NoServersError: No servers available
```
**Cause**: NATS server is not running or not reachable
**Solution**:
```bash
# Check if NATS is running
docker ps | grep nats

# If not running, start it
docker compose -f docker-compose.dev.yml up -d nats

# Verify connectivity
docker run --rm -it --network agentic-trading-architecture-full_default \
  natsio/nats-box:latest \
  nats -s nats://nats:4222 server check connection
```

#### NAT-002: Consumer Not Found
```
Error: nats: NotFoundError: code=404 err_code=10014 description='consumer not found'
```
**Cause**: JetStream consumer doesn't exist or name mismatch
**Solution**:
```bash
# Create consumers
docker compose -f docker-compose.dev.yml up nats-init

# Verify consumers exist
docker run --rm -it --network agentic-trading-architecture-full_default \
  natsio/nats-box:latest \
  nats -s nats://nats:4222 consumer ls trading-events

# Check environment variable
echo $NATS_DURABLE  # Should match consumer name
```

#### NAT-003: Stream Not Found
```
Error: nats: NotFoundError: stream not found
```
**Cause**: JetStream stream doesn't exist
**Solution**:
```bash
# Create stream
docker compose -f docker-compose.dev.yml up nats-init

# Verify stream
docker run --rm -it --network agentic-trading-architecture-full_default \
  natsio/nats-box:latest \
  nats -s nats://nats:4222 stream info trading-events
```

#### NAT-004: Connection Timeout
```
Error: nats: timeout waiting for connection
```
**Cause**: Network issue or wrong URL
**Solution**:
```bash
# Check NATS_URL
echo $NATS_URL  # Should be nats://nats:4222 for Docker

# Test from within network
docker run --rm -it --network agentic-trading-architecture-full_default \
  busybox ping -c 3 nats
```

### Authentication Errors

#### AUTH-001: Invalid Signature
```
Error: Invalid HMAC signature
```
**Cause**: Wrong secret or incorrect signature calculation
**Solution**:
```bash
# Set correct secret
export API_KEY_HMAC_SECRET="test-secret"

# Verify in docker-compose.dev.yml
grep API_KEY_HMAC_SECRET docker-compose.dev.yml

# Test with correct signature
./quick_verify.sh
```

#### AUTH-002: Missing Headers
```
Error: Missing required headers: X-Signature, X-Timestamp, X-Nonce
```
**Cause**: Request missing authentication headers
**Solution**:
```python
# Include all required headers
headers = {
    "X-Signature": signature,
    "X-Timestamp": str(timestamp),
    "X-Nonce": nonce,
    "Content-Type": "application/json"
}
```

#### AUTH-003: Replay Attack Detected
```
Error: Nonce already used
```
**Cause**: Same nonce used twice (replay protection)
**Solution**: Generate unique nonce for each request
```python
nonce = f"nonce-{uuid.uuid4()}"
```

### Schema Validation Errors

#### VAL-001: Additional Properties Not Allowed
```
Error: ValidationError: Additional properties are not allowed
```
**Cause**: Schema too strict with additionalProperties: false
**Solution**:
```python
# Update schema to be forward-compatible
schema = {
    "type": "object",
    "additionalProperties": True  # Allow unknown fields
}
```

#### VAL-002: Required Property Missing
```
Error: ValidationError: 'correlation_id' is a required property
```
**Cause**: Missing required field in event
**Solution**:
```python
# Include all required fields
event = {
    "correlation_id": str(uuid.uuid4()),
    "timestamp": datetime.utcnow().isoformat(),
    # ... other required fields
}
```

#### VAL-003: Type Mismatch
```
Error: ValidationError: 0.75 is not of type 'string'
```
**Cause**: Wrong data type for field
**Solution**: Check CONTRACT.md for correct types

### Service Startup Errors

#### SVC-001: Port Already in Use
```
Error: [Errno 98] Address already in use
```
**Cause**: Port conflict with running service
**Solution**:
```bash
# Find process using port
netstat -tulpn | grep 8001

# Kill process or use different port
kill -9 <PID>

# Or stop all services and restart
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up -d
```

#### SVC-002: Environment Variable Not Set
```
Error: FATAL: Missing required environment variables: ['NATS_URL', 'NATS_STREAM']
```
**Cause**: Required environment variables not configured
**Solution**:
```bash
# Set in .env file
cat >> .env << EOF
NATS_URL=nats://nats:4222
NATS_STREAM=trading-events
EOF

# Or export directly
export NATS_URL=nats://nats:4222
export NATS_STREAM=trading-events
```

#### SVC-003: Import Error
```
Error: ModuleNotFoundError: No module named 'nats'
```
**Cause**: Python dependencies not installed
**Solution**:
```bash
# Rebuild Docker image
docker compose -f docker-compose.dev.yml build

# Or install locally
pip install -r requirements.txt
```

### Database Errors

#### DB-001: SQLite Locked
```
Error: sqlite3.OperationalError: database is locked
```
**Cause**: Concurrent write attempts to SQLite
**Solution**: Migrate to PostgreSQL for production
```bash
# Set PostgreSQL URL
export DATABASE_URL="postgresql://postgres:password@postgres:5432/audit"
```

#### DB-002: Connection Pool Exhausted
```
Error: TimeoutError: Connection pool exhausted
```
**Cause**: Too many concurrent connections
**Solution**:
```python
# Increase pool size
engine = create_engine(url, pool_size=20, max_overflow=30)
```

### Message Processing Errors

#### MSG-001: JSON Decode Error
```
Error: json.JSONDecodeError: Expecting value
```
**Cause**: Invalid JSON in message
**Solution**:
```python
try:
    data = json.loads(msg.data.decode())
except json.JSONDecodeError as e:
    logger.error("Invalid JSON", error=str(e))
    await msg.ack()  # Acknowledge to avoid retry
    return
```

#### MSG-002: Callback Not Async
```
Error: nats: callbacks must be coroutine functions
```
**Cause**: Synchronous function used as NATS callback
**Solution**:
```python
# Change to async
async def message_handler(msg):  # Must be async
    # ... process message
    await msg.ack()
```

#### MSG-003: Message Not Acknowledged
```
Warning: Message redelivered
```
**Cause**: Message not acknowledged after processing
**Solution**:
```python
async def handler(msg):
    try:
        # Process message
        await process(msg.data)
        await msg.ack()  # Always acknowledge
    except Exception as e:
        logger.error("Processing failed", error=str(e))
        # Decide: ack anyway or let retry
```

### Docker/Container Errors

#### DOC-001: Container Exits Immediately
```
Error: Container exits with code 1
```
**Cause**: Startup error in application
**Solution**:
```bash
# Check logs
docker logs agentic-trading-architecture-full-gateway-1

# Common fixes:
# - Missing environment variables
# - Port conflicts
# - Import errors
```

#### DOC-002: Cannot Connect Between Containers
```
Error: Connection refused
```
**Cause**: Using localhost instead of service name
**Solution**:
```python
# Wrong
nats_url = "nats://localhost:4222"

# Correct (use service name)
nats_url = "nats://nats:4222"
```

#### DOC-003: Volume Permission Denied
```
Error: PermissionError: [Errno 13] Permission denied
```
**Cause**: Volume mount permission issue
**Solution**:
```bash
# Fix permissions
sudo chown -R $USER:$USER ./data

# Or run container as current user
docker run --user $(id -u):$(id -g) ...
```

### Performance Issues

#### PERF-001: High Memory Usage
```
Warning: Container using 2GB+ memory
```
**Cause**: Memory leak or large data structures
**Solution**:
- Profile with memory_profiler
- Use generators for large datasets
- Clear caches periodically

#### PERF-002: Slow Event Processing
```
Warning: Message processing took 5+ seconds
```
**Cause**: Synchronous I/O or inefficient algorithms
**Solution**:
- Use async I/O operations
- Add caching for repeated queries
- Process in batches

### Chaos Testing Errors

#### CHAOS-001: Service Doesn't Recover
```
Error: Service failed chaos test
```
**Cause**: Missing reconnection logic
**Solution**: Implement exponential backoff reconnection
```python
async def connect_with_retry():
    for attempt in range(max_retries):
        try:
            return await connect()
        except Exception:
            wait = min(2 ** attempt, 60)
            await asyncio.sleep(wait)
```

## Error Resolution Workflow

1. **Identify Error Category**
   - Check error code/message
   - Find in this catalog

2. **Gather Context**
   ```bash
   # Check logs
   docker compose logs [service] --tail=100

   # Check health
   curl http://localhost:[port]/healthz

   # Check metrics
   curl http://localhost:[port]/metrics
   ```

3. **Apply Solution**
   - Follow solution steps
   - Test with `./quick_verify.sh`

4. **Verify Fix**
   ```bash
   # Run smoke test
   ./test_smoke_ci.sh

   # Check golden path
   make golden
   ```

5. **Document New Errors**
   - Add to this catalog
   - Include reproduction steps
   - Document solution

## Prevention Best Practices

### Always Use Correlation IDs
```python
logger.info("Processing", corr_id=correlation_id)
```

### Handle All Exceptions
```python
try:
    result = process()
except SpecificError as e:
    logger.error("Known error", error=str(e))
except Exception as e:
    logger.error("Unexpected", error=str(e))
```

### Validate Early
```python
# Validate input immediately
if not validate_schema(data):
    raise ValidationError("Invalid input")
```

### Test Error Cases
```python
# Test error handling
@pytest.mark.asyncio
async def test_handles_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        await process_message(b"not json")
```

---

**Note**: Update this catalog when encountering new errors or finding better solutions.
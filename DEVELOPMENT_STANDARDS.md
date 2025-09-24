# Development Standards

**CRITICAL**: These are non-negotiable rules for maintaining code quality and security.

## 🔴 Security Rules (NEVER VIOLATE)

1. **NEVER commit secrets or API keys**
   ```python
   # ❌ WRONG
   API_KEY = "sk_live_abc123def456"

   # ✅ CORRECT
   API_KEY = os.getenv("API_KEY")
   ```

2. **NEVER log sensitive data**
   ```python
   # ❌ WRONG
   logger.info(f"Using API key: {api_key}")

   # ✅ CORRECT
   logger.info("API key configured", key_prefix=api_key[:8])
   ```

3. **NEVER skip authentication checks**
   ```python
   # ❌ WRONG
   if DEBUG:
       return True  # Skip auth in debug

   # ✅ CORRECT
   # Always validate, even in debug
   return validate_hmac(signature, payload)
   ```

4. **NEVER store credentials in code**
   ```yaml
   # ❌ WRONG in docker-compose.yml
   environment:
     - API_KEY=secret123

   # ✅ CORRECT
   environment:
     - API_KEY=${API_KEY}
   ```

## 🟡 Code Quality Standards

### Logging Standards

**ALWAYS use correlation IDs**
```python
# ❌ WRONG
logger.info("Processing order")

# ✅ CORRECT
logger.info("Processing order",
           corr_id=corr_id,
           instrument=order["instrument"])
```

**NEVER use print() statements**
```python
# ❌ WRONG
print(f"Order received: {order}")

# ✅ CORRECT
logger.info("Order received", order_id=order["id"])
```

### Error Handling

**ALWAYS handle specific exceptions**
```python
# ❌ WRONG
try:
    process_order(order)
except:
    pass

# ✅ CORRECT
try:
    process_order(order)
except ValidationError as e:
    logger.error("Order validation failed", error=str(e))
    raise
except Exception as e:
    logger.error("Unexpected error", error=str(e))
    raise
```

**ALWAYS include context in errors**
```python
# ❌ WRONG
raise ValueError("Invalid order")

# ✅ CORRECT
raise ValueError(f"Invalid order: instrument '{instrument}' not recognized")
```

### Metrics Standards

**ALWAYS add metrics for new operations**
```python
# ❌ WRONG
def process_order(order):
    # Just process without metrics
    return execute(order)

# ✅ CORRECT
def process_order(order):
    with processing_time.labels(operation="order").time():
        result = execute(order)
        orders_processed.labels(status=result.status).inc()
        return result
```

### Schema Validation

**NEVER skip schema validation**
```python
# ❌ WRONG
def handle_webhook(data):
    # Assume data is valid
    process(data)

# ✅ CORRECT
def handle_webhook(data):
    validation = validate_schema(data, WEBHOOK_SCHEMA)
    if not validation["valid"]:
        raise ValidationError(validation["error"])
    process(data)
```

## 🟢 Python Specific Standards

### Type Hints Required
```python
# ❌ WRONG
def process_order(order, validate=True):
    pass

# ✅ CORRECT
def process_order(
    order: Dict[str, Any],
    validate: bool = True
) -> Optional[Dict[str, Any]]:
    pass
```

### Async/Await Consistency
```python
# ❌ WRONG - Mixing sync and async
def fetch_data():
    response = requests.get(url)
    return response.json()

# ✅ CORRECT - Consistent async
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

### Configuration Management
```python
# ❌ WRONG - Hardcoded defaults
nats_url = "nats://localhost:4222"

# ✅ CORRECT - Environment with explicit failure
nats_url = os.getenv("NATS_URL")
if not nats_url:
    raise SystemExit("FATAL: NATS_URL environment variable required")
```

## 📋 AI-Specific Guidelines

### Before Making Changes

1. **READ the relevant documentation**
   - SYSTEM_OVERVIEW.md for architecture
   - CONTRACT.md for event schemas
   - Current service README

2. **CHECK for existing patterns**
   ```bash
   # Look for similar implementations
   grep -r "similar_function" repos/
   ```

3. **TEST your changes**
   ```bash
   # Always run smoke test after changes
   ./test_smoke_ci.sh
   ```

### Commit Standards

**Use conventional commits**
```bash
# ✅ CORRECT
git commit -m "feat(gateway): add retry logic for NATS publishing"
git commit -m "fix(exec-sim): correct slippage calculation"
git commit -m "docs: update API examples in CONTRACT.md"

# ❌ WRONG
git commit -m "fixed stuff"
git commit -m "updates"
```

### Documentation Requirements

**Update docs inline with code**
```python
# When adding a new event type:
1. Update CONTRACT.md with schema
2. Update consumer service README
3. Add example to SYSTEM_OVERVIEW.md
4. Update CURRENT_STATE.md if significant
```

## 🚫 Anti-Patterns to Avoid

### Don't Create Circular Dependencies
```python
# ❌ WRONG
# gateway imports from agent
# agent imports from gateway

# ✅ CORRECT
# Both import from shared at-core
```

### Don't Use Mutable Default Arguments
```python
# ❌ WRONG
def process(items=[]):
    items.append("processed")
    return items

# ✅ CORRECT
def process(items=None):
    if items is None:
        items = []
    items.append("processed")
    return items
```

### Don't Ignore Warnings
```python
# ❌ WRONG
import warnings
warnings.filterwarnings("ignore")

# ✅ CORRECT
# Fix the root cause of warnings
```

## 🔧 Development Workflow

### Before Starting Work
```bash
1. Pull latest changes
2. Check TASK_ASSIGNMENTS.md
3. Create feature branch
4. Update task assignment
```

### While Working
```bash
1. Commit frequently (every 30-60 min)
2. Run quick_verify.sh regularly
3. Update documentation as you go
4. Check metrics are exposed
```

### Before Committing
```bash
1. Run smoke tests: ./test_smoke_ci.sh
2. Check for secrets: grep -r "secret\|key\|password"
3. Update CURRENT_STATE.md if needed
4. Write clear commit message
```

## 📊 Quality Checklist

Before marking any task complete:

- [ ] Code follows these standards
- [ ] Correlation IDs in all logs
- [ ] Metrics added for new operations
- [ ] Schema validation implemented
- [ ] Error handling with context
- [ ] Documentation updated
- [ ] Smoke tests pass
- [ ] No hardcoded values
- [ ] No secrets in code
- [ ] Type hints added

## 🚨 Red Flags

If you see any of these, STOP and fix immediately:

- Hardcoded passwords or API keys
- Empty except blocks
- print() statements in production code
- Missing correlation IDs in logs
- Skipped schema validation
- Synchronous code in async context
- Mutable default arguments
- Global state modifications
- Direct database queries without parameterization

## 📚 Resources

- [PEP 8](https://www.python.org/dev/peps/pep-0008/) - Python Style Guide
- [12 Factor App](https://12factor.net/) - Configuration principles
- [OWASP](https://owasp.org/www-project-top-ten/) - Security best practices
- [Conventional Commits](https://www.conventionalcommits.org/) - Commit standards

---

**Remember**: Good code is code that another developer (human or AI) can understand and modify safely six months from now.
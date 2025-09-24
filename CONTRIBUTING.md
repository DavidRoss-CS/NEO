# Contributing to Agentic Trading Architecture

Thank you for your interest in contributing! This guide will help you get started.

## Code of Conduct

- Be respectful and professional
- Focus on technical merit
- Help others learn and grow
- Keep discussions constructive

## Development Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Git
- Basic understanding of async Python and event-driven architecture

### Getting Started
```bash
# Clone the repository
git clone https://github.com/your-org/agentic-trading-architecture.git
cd agentic-trading-architecture

# Start the development environment
docker compose -f docker-compose.dev.yml up -d

# Verify everything is working
./quick_verify.sh

# Run comprehensive tests
./test_smoke_ci.sh
```

### Local Development
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies for a specific service
cd repos/at-gateway
pip install -r requirements.txt

# Run service locally (ensure NATS is running in Docker)
export NATS_URL=nats://localhost:4222
export API_KEY_HMAC_SECRET=test-secret
python -m at_gateway.app
```

## Branch Strategy

We use Git Flow with the following branches:

```
main           → Production-ready code
develop        → Integration branch for features
feature/*      → New features (from develop)
bugfix/*       → Bug fixes (from develop)
hotfix/*       → Urgent production fixes (from main)
release/*      → Release preparation (from develop)
```

### Creating a Feature Branch
```bash
# Start from develop
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/add-stop-loss-orders

# Work on your feature
# ...

# Push to remote
git push -u origin feature/add-stop-loss-orders
```

## Commit Conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

### Examples
```bash
# Feature
git commit -m "feat(gateway): add support for stop-loss orders"

# Bug fix
git commit -m "fix(exec-sim): correct slippage calculation for partial fills"

# Documentation
git commit -m "docs: add API examples to CONTRACT.md"

# With body and footer
git commit -m "feat(agent): implement momentum strategy

- Add technical indicators calculation
- Implement entry/exit signals
- Add backtesting support

Closes #123"
```

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with these additions:

```python
# Use type hints
from typing import Dict, Any, Optional

async def process_order(
    order_data: Dict[str, Any],
    corr_id: str,
    validate: bool = True
) -> Optional[Dict[str, Any]]:
    """Process an order with optional validation.

    Args:
        order_data: Order information
        corr_id: Correlation ID for tracing
        validate: Whether to validate schema

    Returns:
        Fill event or None if validation fails
    """
    pass
```

### Key Principles

1. **Async First**
```python
# Good
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Bad
def fetch_data():
    return requests.get(url).json()
```

2. **Fail Fast**
```python
# Good
REQUIRED = ["NATS_URL", "NATS_STREAM"]
missing = [k for k in REQUIRED if not os.getenv(k)]
if missing:
    raise SystemExit(f"Missing: {missing}")

# Bad
nats_url = os.getenv("NATS_URL", "nats://localhost:4222")  # Silent default
```

3. **Structured Logging**
```python
# Good
logger.info("Processing order",
           corr_id=corr_id,
           instrument=order["instrument"],
           quantity=order["quantity"])

# Bad
print(f"Processing order {corr_id}")
```

4. **Metrics Everywhere**
```python
# Good
orders_processed = Counter('orders_processed_total', ['status'])
orders_processed.labels(status='success').inc()

# Bad
# No metrics tracking
```

### File Structure
```
repos/
├── at-service-name/
│   ├── at_service_name/      # Python package
│   │   ├── __init__.py
│   │   ├── app.py            # FastAPI application
│   │   ├── models.py         # Pydantic models
│   │   └── utils.py          # Helper functions
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
```

## Testing Requirements

### Test Coverage
- **Unit Tests**: Business logic, validators, utilities
- **Integration Tests**: Service interactions, NATS messaging
- **E2E Tests**: Full flow validation

### Writing Tests
```python
# tests/unit/test_validator.py
import pytest
from at_exec_sim.validator import validate_order

def test_valid_order():
    """Test that valid orders pass validation"""
    order = {
        "corr_id": "test_123",
        "instrument": "AAPL",
        "side": "buy",
        "quantity": 100,
        "order_type": "market",
        "timestamp": "2025-01-15T10:30:00Z"
    }
    assert validate_order(order) == True

def test_missing_required_field():
    """Test that missing fields cause validation failure"""
    order = {"instrument": "AAPL"}
    with pytest.raises(ValidationError):
        validate_order(order)
```

### Running Tests
```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=at_service_name tests/

# E2E smoke test
./test_smoke_ci.sh
```

## Pull Request Process

### Before Submitting
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Documentation updated if needed
- [ ] Commit messages follow conventions
- [ ] Branch is up to date with target

### PR Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E smoke test passes

## Checklist
- [ ] Code follows project style
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings
```

### Review Process
1. Create PR from feature branch to `develop`
2. Automated CI runs tests
3. Code review by maintainer
4. Address feedback
5. Merge when approved

## Good First Issues

Perfect for newcomers:

### Easy (1-2 hours)
- Add unit tests for schema validation
- Fix typos in documentation
- Add logging to uncovered code paths
- Improve error messages

### Medium (4-8 hours)
- Create OpenAPI documentation
- Add new Grafana dashboard
- Implement order cancellation
- Add Redis caching for idempotency

### Complex (1-2 days)
- Integrate new broker adapter
- Implement new trading strategy
- Add WebSocket streaming
- Create performance benchmarks

## Project Structure

```
agentic-trading-architecture/
├── docker-compose.dev.yml     # Development environment
├── docker-compose.test.yml    # Test environment
├── repos/                     # Service repositories
│   ├── at-gateway/           # API Gateway
│   ├── at-agent-mcp/         # Trading Agent
│   ├── at-exec-sim/          # Execution Simulator
│   ├── at-audit/             # Audit Service
│   └── at-observability/     # Monitoring Stack
├── scripts/                   # Utility scripts
├── docs/                      # Documentation
└── k8s/                       # Kubernetes manifests
```

## Common Tasks

### Adding a New Event Type
1. Define schema in `CONTRACT.md`
2. Add consumer in relevant service
3. Update tests
4. Document in changelog

### Adding a New Service
1. Create directory structure
2. Implement health/metrics endpoints
3. Add to docker-compose
4. Create tests
5. Update documentation

### Debugging Issues
```bash
# View service logs
docker logs -f agentic-trading-architecture-full-gateway-1

# Check NATS messages
docker run --rm -it --network agentic-trading-architecture-full_default \
  natsio/nats-box:latest \
  nats -s nats://nats:4222 sub ">"

# Inspect metrics
curl localhost:8001/metrics | grep webhook

# Check health
curl localhost:8001/healthz | jq .
```

## Release Process

1. **Version Bump**
```bash
# Update version in all services
# Update CHANGELOG.md
git commit -m "chore: bump version to 1.2.0"
```

2. **Create Release Branch**
```bash
git checkout -b release/1.2.0 develop
```

3. **Testing**
```bash
# Run full test suite
./scripts/run_all_tests.sh

# Deploy to staging
docker compose -f docker-compose.staging.yml up
```

4. **Merge to Main**
```bash
git checkout main
git merge --no-ff release/1.2.0
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin main --tags
```

## Getting Help

### Resources
- [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) - Architecture guide
- [CONTRACT.md](CONTRACT.md) - Event schemas
- [TESTING.md](TESTING.md) - Testing practices
- [ROADMAP.md](ROADMAP.md) - Future plans

### Communication
- **Issues**: GitHub Issues for bugs/features
- **Discussions**: GitHub Discussions for questions
- **Slack**: #trading-architecture channel

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Recognition

Contributors will be recognized in:
- CHANGELOG.md for their contributions
- README.md Contributors section
- Release notes

Thank you for contributing to make this project better! 🚀
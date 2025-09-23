# Onboarding Guide

Welcome to the Agentic Trading Architecture! This guide will get you up and running in 15 minutes.

## Prerequisites

### Required Software
- **Python 3.12+**: `python --version`
- **Docker**: `docker --version`
- **Make**: `make --version`
- **Git**: `git --version`

### Recommended Tools
- **NATS CLI**: `brew install nats-io/nats-tools/nats` (macOS) or [download](https://github.com/nats-io/natscli/releases)
- **jq**: `brew install jq` (macOS) or `apt install jq` (Ubuntu)
- **HTTPie**: `pip install httpie` or use `curl`

### Installation Commands

**macOS (Homebrew)**:
```bash
brew install python@3.12 docker make git jq
brew install nats-io/nats-tools/nats
pip3 install httpie
```

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv docker.io make git jq curl
# Install NATS CLI manually from GitHub releases
wget https://github.com/nats-io/natscli/releases/latest/download/nats-linux-amd64.tar.gz
tar -xzf nats-linux-amd64.tar.gz && sudo mv nats /usr/local/bin/
```

## 15-Minute Setup

### Step 1: Clone and Configure (2 minutes)
```bash
# Clone the repository
git clone <repository-url>
cd agentic-trading-architecture

# Set up environment
cp .env.example .env

# Edit .env with your preferences (optional for local development)
# The defaults in .env.example work for local setup
```

### Step 2: Start Infrastructure (3 minutes)
```bash
# Start NATS, Prometheus, and Grafana
docker compose -f docker-compose.dev.yml up -d nats prom grafana

# Verify services are running
docker compose -f docker-compose.dev.yml ps
```

**Expected output**:
```
NAME                SERVICE     STATUS      PORTS
trading-nats        nats        running     0.0.0.0:4222->4222/tcp
trading-prom        prom        running     0.0.0.0:9090->9090/tcp
trading-grafana     grafana     running     0.0.0.0:3000->3000/tcp
```

### Step 3: Set Up Python Environment (3 minutes)
```bash
# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies (if requirements.txt exists)
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# Install development dependencies
pip install fastapi uvicorn httpie pytest
```

### Step 4: Start Gateway Service (2 minutes)
```bash
# Navigate to gateway directory
cd repos/at-gateway

# Start the gateway service
python -m uvicorn at_gateway.app:app --port 8001 --reload
```

**Expected output**:
```
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
```

### Step 5: Verify Setup (5 minutes)

#### Test 1: Health Check
```bash
# Test gateway health
curl http://localhost:8001/healthz

# Expected response:
# {"ok":true,"nats":"connected","uptime_s":10,"version":"1.0.0"}
```

#### Test 2: Metrics Endpoint
```bash
# Check metrics are available
curl http://localhost:8001/metrics | head -10

# Should see Prometheus-format metrics
```

#### Test 3: Grafana Dashboard
1. Open http://localhost:3000
2. Login with `admin` / `admin`
3. Import gateway dashboard (if available) or create new dashboard
4. Verify metrics are flowing

#### Test 4: Send Test Webhook
```bash
# Generate test signature
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
NONCE=$(uuidgen)
BODY='{"ticker":"EURUSD","action":"buy","price":1.0945,"time":"'$TIMESTAMP'"}'
SECRET="change-me-32-bytes-minimum-for-security"  # From .env
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

# Send webhook
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-Nonce: $NONCE" \
  -H "X-Signature: sha256=$SIGNATURE" \
  -d "$BODY"

# Expected: 202 response with correlation ID
```

#### Test 5: Verify NATS Event
```bash
# Subscribe to NATS events (in a new terminal)
nats sub "signals.*"

# Send another webhook (from previous step)
# You should see events published to signals.raw and signals.normalized
```

## Common Pitfalls

### Missing Virtual Environment
**Symptom**: "Module not found" errors
**Fix**: Ensure you've activated the virtual environment:
```bash
source venv/bin/activate
```

### Wrong Port
**Symptom**: "Connection refused" on health check
**Fix**: Verify the gateway is running on port 8001:
```bash
lsof -i :8001
```

### NATS Not Started
**Symptom**: Health check shows `"nats":"disconnected"`
**Fix**: Start NATS container:
```bash
docker compose -f docker-compose.dev.yml up -d nats
```

### Bad Signature/Clock Skew
**Symptom**: 401 errors on webhook requests
**Fix**:
1. Check system clock is accurate
2. Verify HMAC secret matches `.env` file
3. Ensure timestamp is current (within 5 minutes)

### Docker Permission Issues
**Symptom**: "Permission denied" when running docker commands
**Fix**: Add user to docker group or use `sudo`:
```bash
sudo usermod -aG docker $USER
# Log out and back in, or use:
newgrp docker
```

### Port Conflicts
**Symptom**: "Port already in use" errors
**Fix**: Check what's using the ports:
```bash
# Check common ports
lsof -i :4222  # NATS
lsof -i :8001  # Gateway
lsof -i :9090  # Prometheus
lsof -i :3000  # Grafana
```

## Next Steps

### Essential Reading
1. **[MASTER_GUIDE.md](MASTER_GUIDE.md)**: System overview and architecture
2. **[CONTRIBUTING.md](CONTRIBUTING.md)**: Development workflow and standards
3. **[SECURITY.md](SECURITY.md)**: Security practices and requirements
4. **[repos/at-gateway/README.md](repos/at-gateway/README.md)**: Gateway service details

### Development Workflow
1. **Pick a ticket**: Check `workspace/tickets/` for available work
2. **Create branch**: `git checkout -b feature/your-feature-name`
3. **Make changes**: Follow the patterns in existing code
4. **Add tests**: Unit, contract, and integration tests
5. **Update docs**: README, API_SPEC, RUNBOOK as needed
6. **Submit PR**: Use the PR template and checklist

### Useful Commands

**Development**:
```bash
# Run tests (when implemented)
make test-unit
make test-integration

# Format code
black .
pylint at_gateway/

# Start services
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.dev.yml logs -f nats
journalctl -f -u at-gateway  # If running as systemd service
```

**Debugging**:
```bash
# Check NATS streams
nats stream ls
nats stream info trading-events

# Monitor NATS messages
nats sub "signals.*"
nats sub ">"

# Check metrics
curl -s http://localhost:8001/metrics | grep gateway_

# Check logs for errors
docker compose logs gateway | grep ERROR
```

**NATS Management**:
```bash
# Create stream (if needed)
nats stream add trading-events \
  --subjects="signals.*,decisions.*,executions.*" \
  --storage=file \
  --retention=limits \
  --max-age=168h

# Add consumer
nats consumer add trading-events gateway-consumer \
  --pull --deliver=all --max-inflight=10

# Check consumer status
nats consumer info trading-events gateway-consumer
```

## Getting Help

### Internal Resources
- **Documentation**: Start with [MASTER_GUIDE.md](MASTER_GUIDE.md)
- **Runbooks**: Check service-specific RUNBOOK.md files
- **ADRs**: See `DECISIONS/` for architectural decisions

### Support Channels
- **Questions**: [GitHub Discussions](../../discussions) or Slack #trading-platform
- **Bugs**: [GitHub Issues](../../issues) with full error details and correlation IDs
- **Security**: Email `security@example.com` for security-related questions

### Escalation
- **Urgent Issues**: Page on-call via PagerDuty
- **Platform Issues**: #trading-platform-alerts Slack channel
- **Architecture Questions**: Tag @architecture-team in discussions

## Troubleshooting

### Service Won't Start
1. Check Docker services: `docker compose ps`
2. Verify environment variables: `cat .env`
3. Check port availability: `lsof -i :8001`
4. Review logs: `docker compose logs`

### Authentication Failures
1. Verify HMAC secret in `.env`
2. Check system clock accuracy
3. Ensure request headers are correct
4. Test with known-good signature

### NATS Connection Issues
1. Verify NATS container is running
2. Check NATS logs: `docker compose logs nats`
3. Test NATS CLI: `nats server ping`
4. Verify network connectivity

### Performance Issues
1. Check resource usage: `docker stats`
2. Monitor metrics in Grafana
3. Review rate limiting configuration
4. Check for memory leaks

---

**Welcome to the team! 🚀**

If you run into any issues with this setup, please update this guide with the solution to help future contributors.
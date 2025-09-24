#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 Agentic Trading Architecture - Development Setup"
echo "=================================================="
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker from https://docker.com"
    exit 1
else
    echo -e "${GREEN}✅ Docker found${NC}"
fi

# Check Docker Compose
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
    echo -e "${GREEN}✅ Docker Compose (plugin) found${NC}"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
    echo -e "${GREEN}✅ Docker Compose (standalone) found${NC}"
else
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo "Please install Docker Compose"
    exit 1
fi

# Check for Python (optional but recommended)
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✅ Python3 found${NC}"
else
    echo -e "${YELLOW}⚠️  Python3 not found (optional, but needed for local development)${NC}"
fi

# Check for jq (optional but recommended)
if command -v jq &> /dev/null; then
    echo -e "${GREEN}✅ jq found${NC}"
else
    echo -e "${YELLOW}⚠️  jq not found (optional, but useful for JSON parsing)${NC}"
    echo "   Install with: apt-get install jq (Ubuntu) or brew install jq (Mac)"
fi

echo ""
echo "📁 Setting up environment..."

# Create .env from example if not exists
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Created .env from .env.example${NC}"
    else
        # Create minimal .env
        cat > .env << 'EOF'
# Auto-generated .env - Please review and update
API_KEY_HMAC_SECRET=test-secret
NATS_URL=nats://nats:4222
NATS_STREAM=trading-events
NATS_DURABLE=exec-sim-consumer

# Service URLs (for Docker)
GATEWAY_URL=http://gateway:8001
AGENT_URL=http://agent:8002
EXEC_URL=http://exec:8004
AUDIT_URL=http://audit:8005

# Logging
LOG_LEVEL=INFO

# Testing
TEST_MODE=false
EOF
        echo -e "${GREEN}✅ Created default .env${NC}"
    fi
    echo -e "${YELLOW}⚠️  Please review and update .env with your settings${NC}"
else
    echo -e "${GREEN}✅ .env already exists${NC}"
fi

# Create necessary directories
echo ""
echo "📂 Creating directories..."
mkdir -p logs data tmp
echo -e "${GREEN}✅ Directories created${NC}"

# Make scripts executable
echo ""
echo "🔧 Setting script permissions..."
chmod +x quick_verify.sh test_smoke_ci.sh setup_dev.sh 2>/dev/null || true
echo -e "${GREEN}✅ Scripts are executable${NC}"

# Build Docker images
echo ""
echo "🏗️  Building Docker images..."
echo "This may take a few minutes on first run..."
$DOCKER_COMPOSE -f docker-compose.dev.yml build
echo -e "${GREEN}✅ Docker images built${NC}"

# Start services
echo ""
echo "🚀 Starting services..."
$DOCKER_COMPOSE -f docker-compose.dev.yml up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo ""
echo "🏥 Checking service health..."

check_health() {
    local service=$1
    local port=$2
    if curl -s http://localhost:$port/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $service is healthy${NC}"
        return 0
    else
        echo -e "${RED}❌ $service is not responding${NC}"
        return 1
    fi
}

all_healthy=true
check_health "Gateway" 8001 || all_healthy=false
check_health "Agent" 8002 || all_healthy=false
check_health "Exec-Sim" 8004 || all_healthy=false
check_health "Audit" 8005 || all_healthy=false

if [ "$all_healthy" = true ]; then
    echo ""
    echo -e "${GREEN}🎉 All services are healthy!${NC}"
else
    echo ""
    echo -e "${YELLOW}⚠️  Some services are not healthy. Check logs with:${NC}"
    echo "   docker compose -f docker-compose.dev.yml logs"
fi

# Run quick verification
echo ""
echo "🧪 Running quick verification test..."
if bash quick_verify.sh > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Verification test passed${NC}"
else
    echo -e "${YELLOW}⚠️  Verification test failed. This is expected on first run.${NC}"
    echo "   Run './quick_verify.sh' manually to see details"
fi

# Display next steps
echo ""
echo "════════════════════════════════════════════════"
echo -e "${GREEN}✨ Setup Complete!${NC}"
echo "════════════════════════════════════════════════"
echo ""
echo "📚 Quick Start Commands:"
echo "   make help         - Show all available commands"
echo "   make status       - Check service status"
echo "   make logs         - View service logs"
echo "   make golden       - Run golden path test"
echo "   make metrics      - Show system metrics"
echo "   make down         - Stop all services"
echo ""
echo "🌐 Service URLs:"
echo "   Gateway:     http://localhost:8001"
echo "   Agent:       http://localhost:8002"
echo "   Exec-Sim:    http://localhost:8004"
echo "   Audit:       http://localhost:8005"
echo "   Grafana:     http://localhost:3000 (admin/admin)"
echo ""
echo "📖 Documentation:"
echo "   SYSTEM_OVERVIEW.md - Architecture and concepts"
echo "   CONTRACT.md        - API and event schemas"
echo "   CONTRIBUTING.md    - Development guidelines"
echo "   TASK_ASSIGNMENTS.md - Available tasks"
echo ""
echo "🔍 Troubleshooting:"
echo "   If services fail to start, check:"
echo "   1. Port conflicts: netstat -tulpn | grep 800"
echo "   2. Docker logs: docker compose -f docker-compose.dev.yml logs"
echo "   3. Environment vars: cat .env"
echo ""
echo "Happy coding! 🚀"
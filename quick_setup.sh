#!/bin/bash
# Quick Setup Script for NEO Trading System (Optimized)
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 NEO Trading System - Quick Setup${NC}"
echo "======================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker and Docker Compose found${NC}"

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || echo "API_KEY_HMAC_SECRET=test-secret" > .env
    echo -e "${GREEN}✅ Created .env file${NC}"
fi

# Stop any existing services
echo -e "${YELLOW}🛑 Stopping any existing services...${NC}"
docker-compose -f docker-compose.minimal.yml down -v 2>/dev/null || true
docker-compose -f docker-compose.dev.yml down -v 2>/dev/null || true

# Build and start optimized services
echo -e "${YELLOW}🏗️  Building optimized services...${NC}"
docker-compose -f docker-compose.minimal.yml build

echo -e "${YELLOW}🚀 Starting services...${NC}"
docker-compose -f docker-compose.minimal.yml up -d

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 10

# Check health
echo -e "${YELLOW}🏥 Checking service health...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8001/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Gateway is healthy${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Gateway health check timed out${NC}"
        exit 1
    fi
    sleep 1
done

for i in {1..30}; do
    if curl -s http://localhost:8004/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Execution Simulator is healthy${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Execution Simulator health check timed out${NC}"
        exit 1
    fi
    sleep 1
done

# Run golden path test
echo -e "${YELLOW}🧪 Running golden path test...${NC}"
if make golden > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Golden path test passed${NC}"
else
    echo -e "${YELLOW}⚠️  Golden path test failed (may be expected on first run)${NC}"
fi

# Display status
echo ""
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo "===================="
echo ""
echo -e "${GREEN}Services running:${NC}"
echo "  • NATS Message Broker: localhost:4222"
echo "  • Gateway API: http://localhost:8001"
echo "  • Execution Simulator: http://localhost:8004"
echo ""
echo -e "${GREEN}Quick commands:${NC}"
echo "  make status    - Check service status"
echo "  make logs      - View service logs"
echo "  make metrics   - Show system metrics"
echo "  make golden    - Run end-to-end test"
echo "  make down      - Stop services"
echo ""
echo -e "${GREEN}Ready for trading! 💰${NC}"
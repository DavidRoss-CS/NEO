#!/usr/bin/env python3
"""
Test suite for agent orchestrator service.
"""

import json
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
import sys
import os

# Add the at_agent_orchestrator module to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../at-core'))

from at_agent_orchestrator.app import app
from at_agent_orchestrator.agent_manager import AgentManager
from at_agent_orchestrator.context_store import ContextStore
from at_agent_orchestrator.mcp_client import MCPClient
from tests.fixtures.fake_nats import FakeNats


class TestAgentOrchestrator:
    """Test agent orchestrator service functionality"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_context_store(self):
        """Mock context store"""
        store = Mock(spec=ContextStore)
        store.initialize = AsyncMock()
        store.get_context = AsyncMock(return_value=[])
        store.store_context = AsyncMock()
        store.store_agent_session = AsyncMock()
        store.get_context_stats = AsyncMock(return_value={"total_contexts": 0})
        store.health_check = AsyncMock(return_value=True)
        store.cleanup = AsyncMock()
        return store

    @pytest.fixture
    def mock_mcp_client(self):
        """Mock MCP client"""
        client = Mock(spec=MCPClient)
        client.initialize = AsyncMock()
        client.available_agents = {
            "gpt_trend_analyzer": {
                "type": "openai",
                "model": "gpt-4",
                "description": "GPT-4 trend analysis"
            },
            "claude_strategy": {
                "type": "anthropic",
                "model": "claude-3-sonnet-20240229",
                "description": "Claude strategy agent"
            }
        }
        client.run_agent = AsyncMock(return_value={
            "analysis": "Test analysis result",
            "confidence": 0.85,
            "reasoning": "Test reasoning",
            "orders": [
                {
                    "type": "limit",
                    "side": "buy",
                    "symbol": "BTCUSD",
                    "quantity": 0.1,
                    "price": 45000.0
                }
            ]
        })
        client.cleanup = AsyncMock()
        return client

    @pytest.fixture
    def sample_signal_data(self):
        """Sample signal data for testing"""
        return {
            "schema_version": "1.0.0",
            "intent_id": "test-intent-123",
            "correlation_id": "test-corr-123",
            "source": "tradingview",
            "instrument": "BTCUSD",
            "type": "momentum",
            "strength": 0.85,
            "payload": {"price": 45000.0},
            "ts_iso": "2025-09-24T10:30:00Z"
        }

    def test_health_check_healthy(self, client):
        """Test health check when all components are healthy"""
        with patch('at_agent_orchestrator.app.nats_client') as mock_nats, \
             patch('at_agent_orchestrator.app.context_store') as mock_store, \
             patch('at_agent_orchestrator.app.mcp_client') as mock_mcp:

            mock_nats.is_connected = True
            mock_store.health_check = AsyncMock(return_value=True)
            mock_mcp.available_agents = {"test_agent": {}}

            response = client.get("/healthz")
            assert response.status_code == 200

            data = response.json()
            assert data["ok"] is True
            assert data["service"] == "at-agent-orchestrator"
            assert data["nats_connected"] is True

    def test_health_check_unhealthy_nats(self, client):
        """Test health check when NATS is disconnected"""
        with patch('at_agent_orchestrator.app.nats_client') as mock_nats, \
             patch('at_agent_orchestrator.app.context_store') as mock_store:

            mock_nats.is_connected = False
            mock_store.health_check = AsyncMock(return_value=True)

            response = client.get("/healthz")
            assert response.status_code == 503

            data = response.json()
            assert data["ok"] is False
            assert "NATS disconnected" in data["error"]

    def test_detailed_health_check(self, client):
        """Test detailed health check endpoint"""
        with patch('at_agent_orchestrator.app.nats_client') as mock_nats, \
             patch('at_agent_orchestrator.app.context_store') as mock_store, \
             patch('at_agent_orchestrator.app.mcp_client') as mock_mcp:

            mock_nats.is_connected = True
            mock_store.health_check = AsyncMock(return_value=True)
            mock_mcp.available_agents = {"gpt_trend_analyzer": {}}

            response = client.get("/healthz/detailed")
            assert response.status_code == 200

            data = response.json()
            assert "feature_flags" in data
            assert "configuration" in data
            assert "available_agents" in data

    def test_list_agents(self, client):
        """Test listing available agents"""
        with patch('at_agent_orchestrator.app.mcp_client') as mock_mcp:
            mock_mcp.available_agents = {
                "gpt_trend_analyzer": {},
                "claude_strategy": {}
            }

            response = client.get("/agents")
            assert response.status_code == 200

            data = response.json()
            assert len(data["agents"]) == 2
            assert "gpt_trend_analyzer" in data["agents"]
            assert "claude_strategy" in data["agents"]
            assert data["total_count"] == 2

    def test_run_agent_manual_success(self, client, sample_signal_data):
        """Test manual agent execution via REST API"""
        with patch('at_agent_orchestrator.app.FF_AGENT_GPT', True), \
             patch('at_agent_orchestrator.app.process_agent_request') as mock_process:

            expected_response = {
                "agent_id": "test-agent-123",
                "agent_type": "gpt_trend_analyzer",
                "correlation_id": "test-corr-123",
                "status": "completed",
                "analysis": "Test analysis",
                "confidence": 0.85,
                "orders": []
            }
            mock_process.return_value = type('MockResponse', (), expected_response)()

            request_data = {
                "agent_type": "gpt_trend_analyzer",
                "signal_data": sample_signal_data,
                "correlation_id": "test-corr-123"
            }

            response = client.post("/agent/run", json=request_data)
            assert response.status_code == 200

            data = response.json()
            assert data["agent_type"] == "gpt_trend_analyzer"
            assert data["status"] == "completed"

    def test_run_agent_manual_disabled(self, client, sample_signal_data):
        """Test manual agent execution when feature flag disabled"""
        with patch('at_agent_orchestrator.app.FF_AGENT_GPT', False):
            request_data = {
                "agent_type": "gpt_trend_analyzer",
                "signal_data": sample_signal_data
            }

            response = client.post("/agent/run", json=request_data)
            assert response.status_code == 503
            assert "disabled" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_agent_manager_execution(self, mock_context_store, mock_mcp_client):
        """Test agent manager execution flow"""
        agent_manager = AgentManager(
            context_store=mock_context_store,
            mcp_client=mock_mcp_client,
            timeout_sec=10
        )

        signal_data = {
            "instrument": "BTCUSD",
            "type": "momentum",
            "strength": 0.8
        }

        result = await agent_manager.run_agent(
            agent_type="gpt_trend_analyzer",
            signal_data=signal_data,
            context_key="test-context",
            correlation_id="test-corr"
        )

        assert result["analysis"] == "Test analysis result"
        assert result["confidence"] == 0.85
        assert len(result["orders"]) == 1

        # Verify context storage was called
        mock_context_store.store_context.assert_called()
        mock_context_store.store_agent_session.assert_called()

    @pytest.mark.asyncio
    async def test_agent_timeout(self, mock_context_store, mock_mcp_client):
        """Test agent execution timeout"""
        # Make MCP client take too long
        mock_mcp_client.run_agent = AsyncMock(
            side_effect=asyncio.sleep(5)  # Longer than timeout
        )

        agent_manager = AgentManager(
            context_store=mock_context_store,
            mcp_client=mock_mcp_client,
            timeout_sec=1  # Short timeout
        )

        result = await agent_manager.run_agent(
            agent_type="gpt_trend_analyzer",
            signal_data={"test": "data"},
            context_key="test-context",
            correlation_id="test-corr"
        )

        assert "timeout" in result["analysis"].lower()
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_context_store_operations(self):
        """Test context store basic operations"""
        with patch('redis.from_url') as mock_redis:
            # Mock Redis client
            mock_redis_client = Mock()
            mock_redis_client.ping.return_value = True
            mock_redis_client.lpush.return_value = 1
            mock_redis_client.ltrim.return_value = True
            mock_redis_client.expire.return_value = True
            mock_redis_client.lrange.return_value = ['{"role": "user", "content": "test"}']
            mock_redis.return_value = mock_redis_client

            context_store = ContextStore("redis://localhost:6379")
            await context_store.initialize()

            # Test storing context
            await context_store.store_context(
                "test-key",
                {"role": "user", "content": "test message"}
            )

            # Test retrieving context
            messages = await context_store.get_context("test-key")
            assert len(messages) == 1
            assert messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_mcp_client_agent_execution(self):
        """Test MCP client agent execution"""
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "analysis": "Test analysis",
                "confidence": 0.8,
                "reasoning": "Test reasoning",
                "orders": []
            })
            mock_response.usage.total_tokens = 150

            mock_openai_client = Mock()
            mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_openai_client

            mcp_client = MCPClient(openai_api_key="test-key")
            await mcp_client.initialize()

            result = await mcp_client.run_agent(
                "gpt_trend_analyzer",
                {"test": "signal"},
                correlation_id="test-corr"
            )

            assert result["analysis"] == "Test analysis"
            assert result["confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_nats_message_handling(self, mock_context_store, mock_mcp_client):
        """Test NATS message handling"""
        from at_agent_orchestrator.app import handle_agent_intent

        # Mock NATS message
        mock_msg = Mock()
        mock_msg.subject = "intents.agent_run.gpt_trend_analyzer"
        mock_msg.data = json.dumps({
            "intent_id": "test-intent",
            "source": "gateway",
            "instrument": "BTCUSD"
        }).encode()
        mock_msg.headers = {"Corr-ID": "test-corr"}
        mock_msg.ack = AsyncMock()

        with patch('at_agent_orchestrator.app.agent_manager', agent_manager), \
             patch('at_agent_orchestrator.app.js_client') as mock_js:

            agent_manager = Mock()
            agent_manager.run_agent = AsyncMock(return_value={
                "analysis": "Test result",
                "confidence": 0.7,
                "orders": []
            })

            mock_js.publish = AsyncMock()

            await handle_agent_intent(mock_msg)

            # Verify message was acknowledged
            mock_msg.ack.assert_called_once()

    def test_prometheus_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    @pytest.mark.parametrize("agent_type,expected_prompt", [
        ("gpt_trend_analyzer", "trend analysis specialist"),
        ("gpt_risk_monitor", "risk monitoring specialist"),
        ("claude_strategy", "strategy specialist"),
        ("claude_research", "research specialist"),
    ])
    def test_agent_system_prompts(self, agent_type, expected_prompt):
        """Test agent-specific system prompts"""
        mcp_client = MCPClient()

        system_prompt = mcp_client._get_agent_system_prompt(
            agent_type, {"type": "test"}
        )

        assert expected_prompt.lower() in system_prompt.lower()
        assert "json" in system_prompt.lower()
        assert "confidence" in system_prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
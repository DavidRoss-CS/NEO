#!/usr/bin/env python3
"""
Test suite for output manager service.
"""

import json
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
import sys
import os

# Add the at_output_manager module to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../at-core'))

from at_output_manager.app import app
from at_output_manager.slack_adapter import SlackAdapter
from at_output_manager.telegram_adapter import TelegramAdapter
from at_output_manager.paper_trader import PaperTrader
from at_output_manager.notification_formatter import NotificationFormatter
from tests.fixtures.fake_nats import FakeNats


class TestOutputManager:
    """Test output manager service functionality"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def sample_agent_output(self):
        """Sample agent output for testing"""
        return {
            "schema_version": "1.0.0",
            "agent_id": "gpt_trend_123",
            "correlation_id": "test-corr-123",
            "agent_type": "gpt_trend_analyzer",
            "analysis": "Strong bullish momentum detected in BTCUSD with RSI showing oversold conditions.",
            "confidence": 0.85,
            "reasoning": "Multiple technical indicators align: RSI oversold at 25, MACD bullish crossover, and price above key support.",
            "orders": [
                {
                    "type": "limit",
                    "side": "buy",
                    "symbol": "BTCUSD",
                    "quantity": 0.1,
                    "price": 45000.0,
                    "reasoning": "Entry at support level"
                }
            ],
            "metadata": {
                "processing_status": "completed",
                "timestamp": "2025-09-24T10:30:00Z"
            },
            "ts_iso": "2025-09-24T10:30:00Z"
        }

    @pytest.fixture
    def mock_slack_adapter(self):
        """Mock Slack adapter"""
        adapter = Mock(spec=SlackAdapter)
        adapter.initialize = AsyncMock()
        adapter.send_notification = AsyncMock(return_value="slack_123")
        adapter.health_check = AsyncMock(return_value={"initialized": True})
        adapter.cleanup = AsyncMock()
        return adapter

    @pytest.fixture
    def mock_telegram_adapter(self):
        """Mock Telegram adapter"""
        adapter = Mock(spec=TelegramAdapter)
        adapter.initialize = AsyncMock()
        adapter.send_notification = AsyncMock(return_value="telegram_456")
        adapter.health_check = AsyncMock(return_value={"initialized": True})
        adapter.cleanup = AsyncMock()
        return adapter

    @pytest.fixture
    def mock_paper_trader(self):
        """Mock paper trader"""
        trader = Mock(spec=PaperTrader)
        trader.initialize = AsyncMock()
        trader.execute_trade = AsyncMock(return_value={
            "trade_id": "paper_789",
            "success": True,
            "status": "filled",
            "symbol": "BTCUSD",
            "side": "buy",
            "quantity": 0.1,
            "fill_price": 45000.0,
            "fees": 45.0
        })
        trader.get_status = AsyncMock(return_value={
            "balance": 9500.0,
            "portfolio_value": 9500.0,
            "trades_count": 1
        })
        trader.get_stats = AsyncMock(return_value={
            "total_trades": 1,
            "total_volume": 4500.0,
            "win_rate": 100.0
        })
        trader.cleanup = AsyncMock()
        return trader

    def test_health_check_healthy(self, client):
        """Test health check when all components are healthy"""
        with patch('at_output_manager.app.nats_client') as mock_nats:
            mock_nats.is_connected = True

            response = client.get("/healthz")
            assert response.status_code == 200

            data = response.json()
            assert data["ok"] is True
            assert data["service"] == "at-output-manager"

    def test_health_check_unhealthy_nats(self, client):
        """Test health check when NATS is disconnected"""
        with patch('at_output_manager.app.nats_client') as mock_nats:
            mock_nats.is_connected = False

            response = client.get("/healthz")
            assert response.status_code == 503

            data = response.json()
            assert data["ok"] is False
            assert "NATS disconnected" in data["error"]

    def test_detailed_health_check(self, client):
        """Test detailed health check endpoint"""
        with patch('at_output_manager.app.nats_client') as mock_nats, \
             patch('at_output_manager.app.slack_adapter') as mock_slack, \
             patch('at_output_manager.app.telegram_adapter') as mock_telegram:

            mock_nats.is_connected = True
            mock_slack.health_check = AsyncMock(return_value={"initialized": True})
            mock_telegram.health_check = AsyncMock(return_value={"initialized": True})

            response = client.get("/healthz/detailed")
            assert response.status_code == 200

            data = response.json()
            assert "feature_flags" in data
            assert "configuration" in data
            assert "adapter_health" in data

    def test_manual_notification_slack(self, client, sample_agent_output):
        """Test manual notification sending to Slack"""
        with patch('at_output_manager.app.slack_adapter') as mock_adapter, \
             patch('at_output_manager.app.deliver_notification') as mock_deliver:

            mock_deliver.return_value = "slack_delivery_123"

            request_data = {
                "channel": "slack",
                "agent_output": sample_agent_output,
                "correlation_id": "test-manual-123"
            }

            response = client.post("/notify", json=request_data)
            assert response.status_code == 200

            data = response.json()
            assert data["channel"] == "slack"
            assert data["status"] == "delivered"

    def test_manual_notification_unavailable_adapter(self, client, sample_agent_output):
        """Test manual notification when adapter is unavailable"""
        with patch('at_output_manager.app.slack_adapter', None):
            request_data = {
                "channel": "slack",
                "agent_output": sample_agent_output
            }

            response = client.post("/notify", json=request_data)
            assert response.status_code == 503
            assert "not available" in response.json()["detail"]

    def test_delivery_stats(self, client):
        """Test delivery statistics endpoint"""
        with patch('at_output_manager.app.paper_trader') as mock_trader:
            mock_trader.get_stats = AsyncMock(return_value={
                "total_trades": 5,
                "total_volume": 22500.0,
                "current_balance": 9800.0
            })

            response = client.get("/stats")
            assert response.status_code == 200

            data = response.json()
            assert "service_uptime_seconds" in data
            assert "adapters_enabled" in data

    @pytest.mark.asyncio
    async def test_notification_formatter_slack(self, sample_agent_output):
        """Test Slack message formatting"""
        formatter = NotificationFormatter()

        slack_message = await formatter.format_for_slack(sample_agent_output)

        assert "text" in slack_message
        assert "attachments" in slack_message
        assert len(slack_message["attachments"]) == 1

        attachment = slack_message["attachments"][0]
        assert attachment["color"] in ["good", "warning", "#808080"]
        assert len(attachment["fields"]) >= 3

        # Check for required fields
        field_titles = [field["title"] for field in attachment["fields"]]
        assert "📊 Analysis" in field_titles
        assert "💪 Confidence" in field_titles

    @pytest.mark.asyncio
    async def test_notification_formatter_telegram(self, sample_agent_output):
        """Test Telegram message formatting"""
        formatter = NotificationFormatter()

        message_text, reply_markup = await formatter.format_for_telegram(sample_agent_output)

        assert "NEO Trading Alert" in message_text
        assert "GPT Trend Analyzer" in message_text
        assert "85.0%" in message_text
        assert reply_markup is not None
        assert len(reply_markup.inline_keyboard) >= 1

    @pytest.mark.asyncio
    async def test_paper_trader_execution(self):
        """Test paper trader order execution"""
        mock_js_client = Mock()
        paper_trader = PaperTrader(mock_js_client, initial_balance=10000.0)
        await paper_trader.initialize()

        order = {
            "symbol": "BTCUSD",
            "side": "buy",
            "type": "limit",
            "quantity": 0.1,
            "price": 45000.0
        }

        agent_output = {
            "agent_id": "test_agent",
            "agent_type": "test",
            "confidence": 0.8
        }

        result = await paper_trader.execute_trade(order, agent_output, "test-corr")

        assert result["success"] is True
        assert result["symbol"] == "BTCUSD"
        assert result["side"] == "buy"
        assert result["quantity"] == 0.1

        # Check portfolio update
        status = await paper_trader.get_status()
        assert status["balance"] < 10000.0  # Should be reduced by trade
        assert status["positions_count"] == 1

    @pytest.mark.asyncio
    async def test_paper_trader_insufficient_funds(self):
        """Test paper trader with insufficient funds"""
        mock_js_client = Mock()
        paper_trader = PaperTrader(mock_js_client, initial_balance=1000.0)  # Low balance
        await paper_trader.initialize()

        large_order = {
            "symbol": "BTCUSD",
            "side": "buy",
            "type": "limit",
            "quantity": 1.0,  # $45,000 worth - more than balance
            "price": 45000.0
        }

        agent_output = {"agent_id": "test", "agent_type": "test", "confidence": 0.8}

        result = await paper_trader.execute_trade(large_order, agent_output, "test-corr")

        assert result["success"] is False
        assert "Insufficient balance" in result["error"]

    @pytest.mark.asyncio
    async def test_slack_adapter_initialization(self):
        """Test Slack adapter initialization"""
        formatter = NotificationFormatter()

        with patch('httpx.AsyncClient') as mock_client:
            mock_http_client = Mock()
            mock_http_client.post = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_http_client.post.return_value = mock_response
            mock_client.return_value = mock_http_client

            slack_adapter = SlackAdapter("https://hooks.slack.com/test", formatter)
            await slack_adapter.initialize()

            # Verify HTTP client was created and test message sent
            mock_client.assert_called_once()
            mock_http_client.post.assert_called()

    @pytest.mark.asyncio
    async def test_telegram_adapter_initialization(self):
        """Test Telegram adapter initialization"""
        formatter = NotificationFormatter()

        with patch('telegram.Bot') as mock_bot_class:
            mock_bot = Mock()
            mock_bot.get_me = AsyncMock(return_value=Mock(id=123, username="testbot"))
            mock_bot.send_message = AsyncMock(return_value=Mock(message_id=456))
            mock_bot_class.return_value = mock_bot

            telegram_adapter = TelegramAdapter("test_token", "test_chat_id", formatter)
            await telegram_adapter.initialize()

            # Verify bot was created and test message sent
            mock_bot_class.assert_called_once_with(token="test_token")
            mock_bot.get_me.assert_called()
            mock_bot.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_handle_agent_decision_flow(self, mock_slack_adapter, sample_agent_output):
        """Test complete agent decision handling flow"""
        from at_output_manager.app import handle_agent_decision

        # Mock NATS message
        mock_msg = Mock()
        mock_msg.subject = "decisions.agent_output.gpt_trend_analyzer.info"
        mock_msg.data = json.dumps(sample_agent_output).encode()
        mock_msg.headers = {"Corr-ID": "test-corr"}
        mock_msg.ack = AsyncMock()

        with patch('at_output_manager.app.slack_adapter', mock_slack_adapter), \
             patch('at_output_manager.app.telegram_adapter', None), \
             patch('at_output_manager.app.paper_trader', None), \
             patch('at_output_manager.app.js_client') as mock_js:

            mock_js.publish = AsyncMock()

            await handle_agent_decision(mock_msg)

            # Verify message was acknowledged
            mock_msg.ack.assert_called_once()

    @pytest.mark.parametrize("confidence,expected_emoji", [
        (0.95, "🔥"),
        (0.85, "💪"),
        (0.75, "👍"),
        (0.65, "👌"),
        (0.55, "🤔"),
        (0.35, "⚠️"),
    ])
    def test_confidence_emoji_mapping(self, confidence, expected_emoji):
        """Test confidence level to emoji mapping"""
        formatter = NotificationFormatter()
        emoji = formatter._get_confidence_emoji(confidence)
        assert emoji == expected_emoji

    def test_agent_name_formatting(self):
        """Test agent name formatting"""
        formatter = NotificationFormatter()

        test_cases = [
            ("gpt_trend_analyzer", "GPT Trend Analyzer"),
            ("claude_strategy", "Claude Strategy Agent"),
            ("unknown_agent", "Unknown Agent"),
            ("momentum_scanner", "Momentum Scanner")
        ]

        for input_name, expected_output in test_cases:
            result = formatter._format_agent_name(input_name)
            assert result == expected_output

    def test_text_truncation(self):
        """Test text truncation functionality"""
        formatter = NotificationFormatter()

        # Test normal text
        short_text = "Short text"
        assert formatter._truncate_text(short_text, 100) == short_text

        # Test long text truncation
        long_text = "This is a very long text that should be truncated when it exceeds the maximum length"
        truncated = formatter._truncate_text(long_text, 30)
        assert len(truncated) == 30
        assert truncated.endswith("...")

        # Test None/empty text
        assert formatter._truncate_text(None, 100) == "N/A"
        assert formatter._truncate_text("", 100) == "N/A"

    def test_prometheus_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
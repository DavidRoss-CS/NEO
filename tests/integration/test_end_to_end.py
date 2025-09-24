"""
End-to-end integration tests for the trading system
"""

import asyncio
import json
import time
import uuid
import hmac
import hashlib
import httpx
import nats
import pytest
from typing import Dict, Any


class TestEndToEnd:
    """Test full signal flow from webhook to execution"""

    @pytest.fixture
    async def nats_client(self):
        """Create NATS client"""
        nc = await nats.connect("nats://nats:4222")
        js = nc.jetstream()
        yield js
        await nc.close()

    @pytest.fixture
    def gateway_client(self):
        """Create HTTP client for gateway"""
        return httpx.AsyncClient(base_url="http://gateway:8001")

    @pytest.fixture
    def agent_client(self):
        """Create HTTP client for agent"""
        return httpx.AsyncClient(base_url="http://agent:8002")

    @pytest.fixture
    def exec_client(self):
        """Create HTTP client for exec-sim"""
        return httpx.AsyncClient(base_url="http://exec:8004")

    def generate_hmac(self, body: str, timestamp: str, nonce: str) -> str:
        """Generate HMAC signature for gateway"""
        secret = "test-secret-key"
        message = f"{timestamp}.{nonce}.{body}"
        return hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    async def test_health_checks(self, gateway_client, agent_client, exec_client):
        """Test all services are healthy"""
        # Gateway health
        response = await gateway_client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["nats_connected"] is True

        # Agent health
        response = await agent_client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["nats_connected"] is True

        # Exec-sim health
        response = await exec_client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["nats_connected"] is True

    async def test_webhook_to_decision_flow(self, gateway_client, nats_client):
        """Test signal flow from webhook through agent to decision"""

        # Setup subscription to capture decision
        decisions = []

        async def decision_handler(msg):
            decisions.append(json.loads(msg.data.decode()))
            await msg.ack()

        # Subscribe to decisions
        sub = await nats_client.subscribe(
            "decisions.order_intent",
            cb=decision_handler,
            durable="test-consumer"
        )

        # Prepare webhook payload
        payload = {
            "instrument": "EURUSD",
            "price": 1.0895,
            "signal": "bullish_momentum",
            "strength": 0.85
        }
        body = json.dumps(payload)

        # Generate HMAC
        timestamp = str(time.time())
        nonce = str(uuid.uuid4())
        signature = self.generate_hmac(body, timestamp, nonce)

        # Send webhook
        response = await gateway_client.post(
            "/webhook/tradingview",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature,
                "X-Timestamp": timestamp,
                "X-Nonce": nonce,
                "X-Idempotency-Key": f"test_{uuid.uuid4()}"
            }
        )

        assert response.status_code == 200
        result = response.json()
        assert "corr_id" in result
        corr_id = result["corr_id"]

        # Wait for decision to be generated
        await asyncio.sleep(2)

        # Check decision was generated
        assert len(decisions) > 0
        decision = decisions[0]
        assert decision["corr_id"] == corr_id
        assert decision["instrument"] == "EURUSD"
        assert decision["side"] in ["buy", "sell"]
        assert decision["confidence"] >= 0.7

        # Cleanup
        await sub.unsubscribe()

    async def test_full_trading_flow(self, gateway_client, nats_client):
        """Test complete flow from signal to execution"""

        # Setup subscriptions
        fills = []

        async def fill_handler(msg):
            fills.append(json.loads(msg.data.decode()))
            await msg.ack()

        # Subscribe to fills
        sub = await nats_client.subscribe(
            "executions.fill",
            cb=fill_handler,
            durable="test-fill-consumer"
        )

        # Send strong buy signal
        payload = {
            "instrument": "BTCUSD",
            "price": 45000.0,
            "signal": "strong_buy",
            "strength": 0.95
        }
        body = json.dumps(payload)

        timestamp = str(time.time())
        nonce = str(uuid.uuid4())
        signature = self.generate_hmac(body, timestamp, nonce)

        response = await gateway_client.post(
            "/webhook/tradingview",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature,
                "X-Timestamp": timestamp,
                "X-Nonce": nonce
            }
        )

        assert response.status_code == 200

        # Wait for fill
        await asyncio.sleep(3)

        # Check fill was generated
        assert len(fills) > 0
        fill = fills[0]
        assert fill["instrument"] == "BTCUSD"
        assert fill["fill_status"] in ["full", "partial"]
        assert fill["execution_venue"] == "simulation"

        # Cleanup
        await sub.unsubscribe()

    async def test_rate_limiting(self, gateway_client):
        """Test gateway rate limiting"""
        # This would test rate limiting if implemented
        pass

    async def test_idempotency(self, gateway_client):
        """Test idempotency handling"""

        idempotency_key = f"test_{uuid.uuid4()}"
        payload = {
            "instrument": "GBPUSD",
            "price": 1.25,
            "signal": "neutral",
            "strength": 0.5
        }
        body = json.dumps(payload)

        timestamp = str(time.time())
        nonce = str(uuid.uuid4())
        signature = self.generate_hmac(body, timestamp, nonce)

        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Idempotency-Key": idempotency_key
        }

        # First request
        response1 = await gateway_client.post(
            "/webhook/tradingview",
            content=body,
            headers=headers
        )
        assert response1.status_code == 200
        result1 = response1.json()

        # Duplicate request with same idempotency key
        response2 = await gateway_client.post(
            "/webhook/tradingview",
            content=body,
            headers=headers
        )
        assert response2.status_code == 200
        result2 = response2.json()

        # Should return same response
        assert result1["corr_id"] == result2["corr_id"]

    async def test_invalid_signature(self, gateway_client):
        """Test HMAC validation"""

        payload = {"instrument": "USDJPY", "price": 110.5}
        body = json.dumps(payload)

        response = await gateway_client.post(
            "/webhook/tradingview",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": "invalid_signature",
                "X-Timestamp": str(time.time()),
                "X-Nonce": str(uuid.uuid4())
            }
        )

        # Should reject with 401
        assert response.status_code == 401

    async def test_metrics_endpoints(self, gateway_client, agent_client, exec_client):
        """Test metrics are exposed"""

        # Gateway metrics
        response = await gateway_client.get("/metrics")
        assert response.status_code == 200
        assert "gateway_webhooks_received_total" in response.text

        # Agent metrics
        response = await agent_client.get("/metrics")
        assert response.status_code == 200
        assert "mcp_signals_received_total" in response.text

        # Exec metrics
        response = await exec_client.get("/metrics")
        assert response.status_code == 200
        assert "exec_sim_orders_received_total" in response.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
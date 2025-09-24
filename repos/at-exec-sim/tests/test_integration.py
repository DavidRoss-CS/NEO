"""
Integration test stub for at-exec-sim service
Tests NATS event consumption and publishing
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

import pytest
import nats
from nats.js import JetStreamContext


@pytest.fixture
def nats_url():
    """NATS server URL for testing"""
    return os.getenv("NATS_URL_TEST", "nats://localhost:4222")


@pytest.fixture
def test_stream():
    """Test stream name"""
    return "trading-events-test"


@pytest.fixture
async def nats_client(nats_url, test_stream):
    """Setup NATS client for testing"""
    nc = await nats.connect(nats_url)
    js = nc.jetstream()

    # Ensure test stream exists
    try:
        await js.stream_info(test_stream)
    except nats.js.errors.NotFoundError:
        await js.add_stream(
            name=test_stream,
            subjects=["decisions.*", "executions.*"],
            max_age=60 * 60,  # 1 hour retention for tests
        )

    yield nc, js

    # Cleanup
    await nc.close()


@pytest.mark.asyncio
async def test_order_intent_to_fill_flow(nats_client):
    """Test complete flow from order intent to fill event"""
    nc, js = nats_client
    corr_id = f"test_{uuid.uuid4().hex[:8]}"

    # Create test order intent
    order_intent = {
        "corr_id": corr_id,
        "agent_id": "test_agent",
        "instrument": "EURUSD",
        "side": "buy",
        "quantity": 10000,
        "order_type": "market",
        "price_limit": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": "test_strategy",
        "risk_params": {
            "max_slippage_bps": 5,
            "time_in_force": "IOC"
        }
    }

    # Subscribe to fill events
    fill_received = asyncio.Event()
    fill_data = {}

    async def fill_handler(msg):
        nonlocal fill_data
        fill_data = json.loads(msg.data.decode())
        fill_received.set()

    fill_sub = await js.subscribe("executions.fill", cb=fill_handler)

    # Publish order intent
    await js.publish(
        subject="decisions.order_intent",
        payload=json.dumps(order_intent).encode(),
        headers={"corr_id": corr_id}
    )

    # Wait for fill event
    try:
        await asyncio.wait_for(fill_received.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail("Fill event not received within timeout")

    # Validate fill event
    assert fill_data.get("corr_id") == corr_id
    assert fill_data.get("instrument") == "EURUSD"
    assert fill_data.get("side") == "buy"
    assert "fill_id" in fill_data
    assert "quantity_filled" in fill_data
    assert "avg_fill_price" in fill_data
    assert fill_data.get("execution_venue") == "simulator"

    # Cleanup
    await fill_sub.unsubscribe()


@pytest.mark.asyncio
async def test_reconcile_event_generation(nats_client):
    """Test that reconcile events are generated for fills"""
    nc, js = nats_client
    corr_id = f"test_{uuid.uuid4().hex[:8]}"

    # Create test order intent
    order_intent = {
        "corr_id": corr_id,
        "agent_id": "test_agent",
        "instrument": "BTC/USD",
        "side": "sell",
        "quantity": 0.5,
        "order_type": "limit",
        "price_limit": 42000.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": "test_strategy"
    }

    # Subscribe to reconcile events
    reconcile_received = asyncio.Event()
    reconcile_data = {}

    async def reconcile_handler(msg):
        nonlocal reconcile_data
        reconcile_data = json.loads(msg.data.decode())
        reconcile_received.set()

    reconcile_sub = await js.subscribe("executions.reconcile", cb=reconcile_handler)

    # Publish order intent
    await js.publish(
        subject="decisions.order_intent",
        payload=json.dumps(order_intent).encode(),
        headers={"corr_id": corr_id}
    )

    # Wait for reconcile event
    try:
        await asyncio.wait_for(reconcile_received.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail("Reconcile event not received within timeout")

    # Validate reconcile event
    assert reconcile_data.get("corr_id") == corr_id
    assert reconcile_data.get("agent_id") == "test_agent"
    assert reconcile_data.get("instrument") == "BTC/USD"
    assert "reconcile_id" in reconcile_data
    assert "position_delta" in reconcile_data
    # Position delta should be negative for sell
    assert reconcile_data.get("position_delta") < 0

    # Cleanup
    await reconcile_sub.unsubscribe()


@pytest.mark.asyncio
async def test_invalid_order_rejection(nats_client):
    """Test that invalid orders are rejected and no fills generated"""
    nc, js = nats_client
    corr_id = f"test_{uuid.uuid4().hex[:8]}"

    # Create invalid order intent (missing required fields)
    invalid_order = {
        "corr_id": corr_id,
        "instrument": "INVALID",  # Invalid instrument format
        "side": "invalid_side",   # Invalid side
        "quantity": -100,          # Negative quantity
        # Missing required fields: agent_id, order_type, timestamp
    }

    # Subscribe to fill events
    fill_received = asyncio.Event()

    async def fill_handler(msg):
        fill_received.set()

    fill_sub = await js.subscribe("executions.fill", cb=fill_handler)

    # Publish invalid order intent
    await js.publish(
        subject="decisions.order_intent",
        payload=json.dumps(invalid_order).encode(),
        headers={"corr_id": corr_id}
    )

    # Wait to ensure no fill is generated
    try:
        await asyncio.wait_for(fill_received.wait(), timeout=3.0)
        pytest.fail("Fill event should not be generated for invalid order")
    except asyncio.TimeoutError:
        # Expected behavior - no fill for invalid order
        pass

    # Cleanup
    await fill_sub.unsubscribe()


@pytest.mark.asyncio
async def test_idempotency_handling(nats_client):
    """Test that duplicate orders are handled idempotently"""
    nc, js = nats_client
    corr_id = f"test_{uuid.uuid4().hex[:8]}"

    # Create test order intent
    order_intent = {
        "corr_id": corr_id,
        "agent_id": "test_agent",
        "instrument": "SPY",
        "side": "buy",
        "quantity": 100,
        "order_type": "market",
        "price_limit": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": "test_strategy"
    }

    # Subscribe to fill events
    fills_received = []

    async def fill_handler(msg):
        fills_received.append(json.loads(msg.data.decode()))

    fill_sub = await js.subscribe("executions.fill", cb=fill_handler)

    # Publish same order intent twice
    for _ in range(2):
        await js.publish(
            subject="decisions.order_intent",
            payload=json.dumps(order_intent).encode(),
            headers={"corr_id": corr_id}
        )

    # Wait for potential fills
    await asyncio.sleep(5)

    # Should only receive one fill event (idempotent)
    assert len(fills_received) == 1, "Duplicate order should not generate multiple fills"
    assert fills_received[0].get("corr_id") == corr_id

    # Cleanup
    await fill_sub.unsubscribe()


@pytest.mark.asyncio
async def test_partial_fill_simulation(nats_client):
    """Test that partial fills are sometimes simulated"""
    nc, js = nats_client

    # Run multiple orders to get statistical sample
    partial_fills = 0
    full_fills = 0
    total_orders = 20

    for i in range(total_orders):
        corr_id = f"test_partial_{i}"

        order_intent = {
            "corr_id": corr_id,
            "agent_id": "test_agent",
            "instrument": "EURUSD",
            "side": "buy" if i % 2 == 0 else "sell",
            "quantity": 10000,
            "order_type": "market",
            "price_limit": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "strategy": "test_strategy"
        }

        fill_received = asyncio.Event()
        fill_data = {}

        async def fill_handler(msg):
            nonlocal fill_data
            fill_data = json.loads(msg.data.decode())
            fill_received.set()

        fill_sub = await js.subscribe("executions.fill", cb=fill_handler)

        await js.publish(
            subject="decisions.order_intent",
            payload=json.dumps(order_intent).encode(),
            headers={"corr_id": corr_id}
        )

        # Wait for fill
        await asyncio.wait_for(fill_received.wait(), timeout=5.0)

        if fill_data.get("fill_status") == "partial":
            partial_fills += 1
        elif fill_data.get("fill_status") == "full":
            full_fills += 1

        await fill_sub.unsubscribe()

    # With 10% partial fill chance, expect some partial fills
    assert partial_fills > 0, "Should have some partial fills"
    assert full_fills > 0, "Should have some full fills"
    assert partial_fills + full_fills == total_orders


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
"""
Load Testing Chaos Component

Generates sustained load against trading system endpoints.
"""

import asyncio
import json
import time
import aiohttp
from typing import Dict, Any
import structlog
from prometheus_client import Counter, Histogram

logger = structlog.get_logger(__name__)

load_requests_sent = Counter('chaos_load_requests_total', 'Load test requests sent', ['endpoint', 'status'])
load_request_duration = Histogram('chaos_load_request_duration_seconds', 'Load test request duration')

class LoadTester:
    """Generates HTTP load against trading system endpoints"""

    def __init__(self):
        pass

    async def run_load_test(self, rps: int = 100, duration_s: int = 120, payload_size: int = 1024):
        """
        Run sustained load test

        Args:
            rps: Requests per second
            duration_s: Test duration
            payload_size: Size of request payload in bytes
        """
        logger.info("Starting load test", rps=rps, duration_s=duration_s, payload_size=payload_size)

        start_time = time.time()
        end_time = start_time + duration_s
        request_interval = 1.0 / rps

        # Create large payload
        large_payload = {
            "instrument": "AAPL",
            "price": 150.50,
            "signal": "BUY",
            "strength": 0.75,
            "timestamp": "2025-09-23T10:00:00Z",
            "metadata": {
                "padding": "x" * (payload_size - 200)  # Fill to desired size
            }
        }

        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                # Send request to gateway
                await self._send_load_request(session, "http://gateway:8001/webhook", large_payload)
                await asyncio.sleep(request_interval)

        duration = time.time() - start_time
        logger.info("Load test completed", duration=duration)

    async def _send_load_request(self, session: aiohttp.ClientSession, url: str, payload: Dict[str, Any]):
        """Send a single load test request"""
        try:
            start_time = time.time()
            async with session.post(url, json=payload) as response:
                duration = time.time() - start_time
                load_request_duration.observe(duration)
                load_requests_sent.labels(endpoint="webhook", status=str(response.status)).inc()

        except Exception as e:
            load_requests_sent.labels(endpoint="webhook", status="error").inc()
            logger.debug("Load request failed", error=str(e))
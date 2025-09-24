"""
Duplicate Message Generation Chaos Test

Tests system's ability to handle duplicate messages and idempotency.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import random

import nats
from nats.js import JetStreamContext
import structlog
from prometheus_client import Counter

logger = structlog.get_logger(__name__)

duplicates_generated = Counter('chaos_duplicate_messages_total', 'Duplicate messages generated', ['subject'])

class DuplicateMessageGenerator:
    """Generates duplicate messages to test idempotency handling"""

    def __init__(self, nats_url: str):
        self.nats_url = nats_url
        self.nc: Optional[nats.NATS] = None
        self.connected = False
        self.message_store: List[Dict[str, Any]] = []

    async def connect(self):
        """Connect to NATS server"""
        try:
            self.nc = await nats.connect(self.nats_url)
            self.connected = True
            logger.info("Duplicate message generator connected")
        except Exception as e:
            logger.error("Failed to connect duplicate message generator", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from NATS"""
        try:
            if self.nc:
                await self.nc.close()
            self.connected = False
            logger.info("Duplicate message generator disconnected")
        except Exception as e:
            logger.error("Error disconnecting duplicate message generator", error=str(e))

    async def generate_duplicates(self, duplicate_rate: float = 0.1, duration_s: int = 60):
        """
        Generate duplicate messages

        Args:
            duplicate_rate: Percentage of messages that are duplicates
            duration_s: Test duration
        """
        if not self.connected:
            raise RuntimeError("Duplicate message generator not connected")

        logger.info("Starting duplicate message generation",
                   duplicate_rate=duplicate_rate,
                   duration_s=duration_s)

        start_time = time.time()
        end_time = start_time + duration_s

        while time.time() < end_time:
            # Generate original message
            original_msg = self._create_test_message()
            self.message_store.append(original_msg)

            # Send original
            await self._send_message("signals.normalized", original_msg)

            # Maybe send duplicate
            if random.random() < duplicate_rate and len(self.message_store) > 5:
                # Pick random previous message
                duplicate_msg = random.choice(self.message_store[-10:])
                await self._send_message("signals.normalized", duplicate_msg)
                duplicates_generated.labels(subject="signals.normalized").inc()

            # Keep message store size manageable
            if len(self.message_store) > 100:
                self.message_store = self.message_store[-50:]

            await asyncio.sleep(0.5)  # 2 messages/second

        duration = time.time() - start_time
        logger.info("Duplicate message generation completed", duration=duration)

    def _create_test_message(self) -> Dict[str, Any]:
        """Create a test message with unique ID"""
        return {
            "correlation_id": f"chaos_dup_{uuid.uuid4().hex[:8]}",
            "instrument": "AAPL",
            "price": round(150 + random.uniform(-10, 10), 2),
            "signal": random.choice(["BUY", "SELL"]),
            "strength": random.random(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "source": "chaos_duplicate_test",
                "_chaos_duplicate_test": True
            }
        }

    async def _send_message(self, subject: str, message: Dict[str, Any]):
        """Send message to NATS"""
        try:
            await self.nc.publish(subject, json.dumps(message).encode())
        except Exception as e:
            logger.error("Error sending duplicate message", error=str(e))
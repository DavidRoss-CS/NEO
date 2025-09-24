"""
Backpressure Generation Chaos Test

Generates high-volume message traffic to test system backpressure handling.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional
import random

import nats
from nats.js import JetStreamContext
import structlog
from prometheus_client import Counter, Histogram, Gauge

logger = structlog.get_logger(__name__)

# Metrics
messages_generated = Counter('chaos_backpressure_messages_total', 'Total backpressure messages generated', ['subject'])
message_generation_rate = Gauge('chaos_backpressure_rate_per_second', 'Current message generation rate')
generation_errors = Counter('chaos_backpressure_errors_total', 'Backpressure generation errors', ['error_type'])

class BackpressureGenerator:
    """Generates high-volume message traffic to create backpressure"""

    def __init__(self, nats_url: str):
        self.nats_url = nats_url
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.connected = False
        self.active = False

    async def connect(self):
        """Connect to NATS server"""
        try:
            self.nc = await nats.connect(self.nats_url)
            self.js = self.nc.jetstream()
            self.connected = True
            logger.info("Backpressure generator connected", nats_url=self.nats_url)
        except Exception as e:
            logger.error("Failed to connect backpressure generator", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from NATS"""
        try:
            self.active = False
            if self.nc:
                await self.nc.close()
            self.connected = False
            logger.info("Backpressure generator disconnected")
        except Exception as e:
            logger.error("Error disconnecting backpressure generator", error=str(e))

    async def generate_backpressure(self, rate_multiplier: int = 10, duration_s: int = 60):
        """
        Generate backpressure by sending high-volume messages

        Args:
            rate_multiplier: Multiple of normal message rate
            duration_s: How long to generate backpressure
        """
        if not self.connected:
            raise RuntimeError("Backpressure generator not connected")

        self.active = True
        start_time = time.time()
        end_time = start_time + duration_s

        # Calculate target rate (normal rate is ~1 message/second, multiply by rate_multiplier)
        target_rps = rate_multiplier
        message_interval = 1.0 / target_rps

        logger.info("Starting backpressure generation",
                   rate_multiplier=rate_multiplier,
                   target_rps=target_rps,
                   duration_s=duration_s)

        message_count = 0
        last_rate_update = time.time()

        try:
            while self.active and time.time() < end_time:
                current_time = time.time()

                # Generate multiple message types
                tasks = [
                    self._generate_signal_burst(target_rps // 3),
                    self._generate_decision_burst(target_rps // 3),
                    self._generate_execution_burst(target_rps // 3)
                ]

                # Run message generation tasks concurrently
                await asyncio.gather(*tasks, return_exceptions=True)

                message_count += target_rps

                # Update rate metric every second
                if current_time - last_rate_update >= 1.0:
                    current_rate = message_count / (current_time - start_time)
                    message_generation_rate.set(current_rate)
                    last_rate_update = current_time

                # Sleep to maintain target rate
                await asyncio.sleep(message_interval)

        except Exception as e:
            logger.error("Error during backpressure generation", error=str(e))
            generation_errors.labels(error_type="generation_failed").inc()
            raise
        finally:
            self.active = False
            message_generation_rate.set(0)

            duration = time.time() - start_time
            final_rate = message_count / duration if duration > 0 else 0

            logger.info("Backpressure generation completed",
                       duration=duration,
                       total_messages=message_count,
                       average_rate=final_rate)

    async def _generate_signal_burst(self, count: int):
        """Generate a burst of signal messages"""
        try:
            tasks = []
            for i in range(count):
                signal_msg = {
                    "instrument": random.choice(["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]),
                    "price": round(100 + random.random() * 900, 2),
                    "signal": random.choice(["BUY", "SELL", "HOLD"]),
                    "strength": random.random(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "correlation_id": f"chaos_backpressure_{uuid.uuid4().hex[:8]}",
                        "source": "chaos_test",
                        "_chaos_backpressure": True
                    }
                }

                # Publish with different subjects to spread load
                subject = f"signals.{'normalized' if i % 2 == 0 else 'raw'}"
                tasks.append(self._publish_message(subject, signal_msg))

            await asyncio.gather(*tasks, return_exceptions=True)
            messages_generated.labels(subject="signals").inc(count)

        except Exception as e:
            logger.error("Error generating signal burst", error=str(e))
            generation_errors.labels(error_type="signal_burst").inc()

    async def _generate_decision_burst(self, count: int):
        """Generate a burst of decision messages"""
        try:
            tasks = []
            for i in range(count):
                decision_msg = {
                    "corr_id": f"chaos_decision_{uuid.uuid4().hex[:8]}",
                    "agent_id": f"chaos_agent_{i % 5}",
                    "strategy_id": random.choice(["momentum_v1", "mean_reversion_v1", "chaos_strategy"]),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "instrument": random.choice(["AAPL", "GOOGL", "MSFT"]),
                    "side": random.choice(["buy", "sell"]),
                    "order_type": "market",
                    "quantity": round(random.uniform(100, 2000), 0),
                    "confidence": random.random(),
                    "_chaos_backpressure": True
                }

                tasks.append(self._publish_message("decisions.order_intent", decision_msg))

            await asyncio.gather(*tasks, return_exceptions=True)
            messages_generated.labels(subject="decisions").inc(count)

        except Exception as e:
            logger.error("Error generating decision burst", error=str(e))
            generation_errors.labels(error_type="decision_burst").inc()

    async def _generate_execution_burst(self, count: int):
        """Generate a burst of execution messages"""
        try:
            tasks = []
            for i in range(count):
                execution_msg = {
                    "fill_id": f"chaos_fill_{uuid.uuid4().hex[:8]}",
                    "order_id": f"chaos_order_{i}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "instrument": random.choice(["AAPL", "GOOGL", "MSFT"]),
                    "side": random.choice(["buy", "sell"]),
                    "quantity": round(random.uniform(100, 1000), 0),
                    "price": round(100 + random.random() * 900, 2),
                    "fill_type": random.choice(["full", "partial"]),
                    "_chaos_backpressure": True
                }

                tasks.append(self._publish_message("executions.fill", execution_msg))

            await asyncio.gather(*tasks, return_exceptions=True)
            messages_generated.labels(subject="executions").inc(count)

        except Exception as e:
            logger.error("Error generating execution burst", error=str(e))
            generation_errors.labels(error_type="execution_burst").inc()

    async def _publish_message(self, subject: str, message: dict):
        """Publish a single message"""
        try:
            await self.nc.publish(subject, json.dumps(message).encode())
        except Exception as e:
            logger.error("Error publishing message",
                        subject=subject,
                        error=str(e))
            generation_errors.labels(error_type="publish_failed").inc()

    async def generate_consumer_crash_scenario(self, duration_s: int = 120):
        """
        Generate a scenario where consumers can't keep up and crash

        This creates a sustained high load that may cause consumer failures.
        """
        if not self.connected:
            raise RuntimeError("Backpressure generator not connected")

        logger.info("Starting consumer crash scenario", duration_s=duration_s)

        # Generate very high initial burst
        await self.generate_backpressure(rate_multiplier=50, duration_s=duration_s // 4)

        # Brief pause
        await asyncio.sleep(5)

        # Sustained moderate load
        await self.generate_backpressure(rate_multiplier=20, duration_s=duration_s // 2)

        # Final burst
        await self.generate_backpressure(rate_multiplier=100, duration_s=duration_s // 4)

        logger.info("Consumer crash scenario completed")

    async def generate_duplicate_storm(self, duplicate_rate: float = 0.5, duration_s: int = 60):
        """
        Generate high-volume duplicate messages

        Args:
            duplicate_rate: Percentage of messages that are duplicates (0.5 = 50%)
            duration_s: Test duration
        """
        if not self.connected:
            raise RuntimeError("Backpressure generator not connected")

        self.active = True
        start_time = time.time()
        end_time = start_time + duration_s

        logger.info("Starting duplicate message storm",
                   duplicate_rate=duplicate_rate,
                   duration_s=duration_s)

        # Store messages for duplication
        original_messages = []
        duplicate_count = 0

        try:
            while self.active and time.time() < end_time:
                # Generate original message
                original_msg = {
                    "correlation_id": f"chaos_dup_{uuid.uuid4().hex[:8]}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "instrument": "AAPL",
                    "price": 150.0,
                    "signal": "BUY",
                    "strength": 0.8,
                    "_chaos_duplicate_test": True
                }

                # Store for potential duplication
                original_messages.append(original_msg)

                # Publish original
                await self._publish_message("signals.normalized", original_msg)

                # Maybe send duplicates
                if random.random() < duplicate_rate and original_messages:
                    # Pick a random previous message to duplicate
                    dup_msg = random.choice(original_messages[-10:])  # From last 10 messages
                    await self._publish_message("signals.normalized", dup_msg)
                    duplicate_count += 1

                await asyncio.sleep(0.1)  # 10 messages/second

        except Exception as e:
            logger.error("Error during duplicate storm", error=str(e))
            raise
        finally:
            self.active = False
            duration = time.time() - start_time
            logger.info("Duplicate message storm completed",
                       duration=duration,
                       duplicates_sent=duplicate_count)
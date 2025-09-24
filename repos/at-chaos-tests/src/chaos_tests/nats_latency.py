"""
NATS Latency Injection Chaos Test

Simulates network latency by intercepting NATS messages and adding delays.
"""

import asyncio
import json
import time
from typing import Optional
import random

import nats
from nats.js import JetStreamContext
import structlog
from prometheus_client import Counter, Histogram

logger = structlog.get_logger(__name__)

# Metrics
latency_injections = Counter('chaos_nats_latency_injections_total', 'Total latency injections', ['delay_range'])
message_delays = Histogram('chaos_nats_message_delay_seconds', 'Injected message delays')

class NATSLatencyInjector:
    """Injects artificial latency into NATS message flow"""

    def __init__(self, nats_url: str):
        self.nats_url = nats_url
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.connected = False
        self.active = False
        self.proxy_subscriptions = {}

    async def connect(self):
        """Connect to NATS server"""
        try:
            self.nc = await nats.connect(self.nats_url)
            self.js = self.nc.jetstream()
            self.connected = True
            logger.info("NATS latency injector connected", nats_url=self.nats_url)
        except Exception as e:
            logger.error("Failed to connect NATS latency injector", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from NATS"""
        try:
            self.active = False

            # Clean up proxy subscriptions
            for sub in self.proxy_subscriptions.values():
                await sub.unsubscribe()
            self.proxy_subscriptions.clear()

            if self.nc:
                await self.nc.close()

            self.connected = False
            logger.info("NATS latency injector disconnected")
        except Exception as e:
            logger.error("Error disconnecting NATS latency injector", error=str(e))

    async def inject_latency(self, delay_ms: int = 100, duration_s: int = 60, jitter_pct: float = 0.2):
        """
        Inject latency into NATS message flow

        Args:
            delay_ms: Base delay in milliseconds
            duration_s: How long to inject latency
            jitter_pct: Random jitter percentage (0.2 = ±20%)
        """
        if not self.connected:
            raise RuntimeError("NATS latency injector not connected")

        self.active = True
        start_time = time.time()
        end_time = start_time + duration_s

        logger.info("Starting NATS latency injection",
                   delay_ms=delay_ms,
                   duration_s=duration_s,
                   jitter_pct=jitter_pct)

        try:
            # Subscribe to all trading subjects to intercept messages
            subjects = ["signals.*", "decisions.*", "executions.*"]

            for subject in subjects:
                # Create proxy subscription that adds delay before republishing
                subscription = await self.nc.subscribe(
                    subject,
                    cb=lambda msg, delay=delay_ms, jitter=jitter_pct:
                        asyncio.create_task(self._delay_and_republish(msg, delay, jitter))
                )
                self.proxy_subscriptions[subject] = subscription

                logger.info("Created latency proxy subscription", subject=subject)

            # Wait for duration or until stopped
            while self.active and time.time() < end_time:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error("Error during latency injection", error=str(e))
            raise
        finally:
            # Clean up subscriptions
            for subject, sub in self.proxy_subscriptions.items():
                await sub.unsubscribe()
                logger.info("Removed latency proxy subscription", subject=subject)

            self.proxy_subscriptions.clear()
            self.active = False

            duration = time.time() - start_time
            logger.info("NATS latency injection completed", duration=duration)

    async def _delay_and_republish(self, msg, base_delay_ms: int, jitter_pct: float):
        """Add delay and republish message"""
        try:
            # Calculate actual delay with jitter
            jitter_range = base_delay_ms * jitter_pct
            jitter = random.uniform(-jitter_range, jitter_range)
            actual_delay_ms = base_delay_ms + jitter
            actual_delay_s = actual_delay_ms / 1000.0

            # Record metrics
            delay_range = f"{base_delay_ms-int(jitter_range)}-{base_delay_ms+int(jitter_range)}ms"
            latency_injections.labels(delay_range=delay_range).inc()
            message_delays.observe(actual_delay_s)

            # Add delay
            await asyncio.sleep(actual_delay_s)

            # Republish with latency marker
            original_data = json.loads(msg.data.decode())
            original_data['_chaos_latency_injected_ms'] = actual_delay_ms

            # Republish to the same subject with modified data
            await self.nc.publish(
                msg.subject + ".delayed",
                json.dumps(original_data).encode(),
                headers=msg.headers
            )

            logger.debug("Message delayed and republished",
                        subject=msg.subject,
                        delay_ms=actual_delay_ms)

        except Exception as e:
            logger.error("Error in delay_and_republish",
                        subject=msg.subject,
                        error=str(e))

    async def inject_intermittent_latency(self,
                                        delay_ms: int = 100,
                                        duration_s: int = 60,
                                        spike_probability: float = 0.1,
                                        spike_multiplier: float = 10):
        """
        Inject intermittent latency spikes

        Args:
            delay_ms: Base delay
            duration_s: Test duration
            spike_probability: Probability of a latency spike (0.1 = 10%)
            spike_multiplier: Multiplier for spike delay
        """
        if not self.connected:
            raise RuntimeError("NATS latency injector not connected")

        self.active = True
        start_time = time.time()
        end_time = start_time + duration_s

        logger.info("Starting intermittent NATS latency injection",
                   delay_ms=delay_ms,
                   spike_probability=spike_probability,
                   spike_multiplier=spike_multiplier)

        try:
            # Monitor message flow and inject random spikes
            subscription = await self.nc.subscribe(
                "signals.*",
                cb=lambda msg: asyncio.create_task(
                    self._maybe_inject_spike(msg, delay_ms, spike_probability, spike_multiplier)
                )
            )

            while self.active and time.time() < end_time:
                await asyncio.sleep(0.1)

            await subscription.unsubscribe()

        except Exception as e:
            logger.error("Error during intermittent latency injection", error=str(e))
            raise
        finally:
            self.active = False
            duration = time.time() - start_time
            logger.info("Intermittent latency injection completed", duration=duration)

    async def _maybe_inject_spike(self, msg, base_delay: int, spike_prob: float, spike_mult: float):
        """Maybe inject a latency spike"""
        try:
            if random.random() < spike_prob:
                # Inject spike
                spike_delay = base_delay * spike_mult
                await asyncio.sleep(spike_delay / 1000.0)

                latency_injections.labels(delay_range=f"spike_{spike_delay}ms").inc()
                message_delays.observe(spike_delay / 1000.0)

                logger.info("Latency spike injected",
                           subject=msg.subject,
                           delay_ms=spike_delay)

        except Exception as e:
            logger.error("Error injecting latency spike", error=str(e))
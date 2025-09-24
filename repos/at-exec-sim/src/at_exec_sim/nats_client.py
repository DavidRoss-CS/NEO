import asyncio
import json
import os
import time
from collections import deque
from typing import Dict, Any, Optional, Callable
import uuid

import nats
from nats.js import JetStreamContext
import structlog

logger = structlog.get_logger(__name__)

class NATSClient:
    def __init__(self):
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.subscription = None
        self.event_buffer = deque(maxlen=1000)
        self.status = "disconnected"

        # Rate limiting for fetch logging
        self._last_fetch_log = 0
        self._fetch_log_interval = 5.0  # Log fetch stats every 5 seconds
        self._fetch_count = 0
        self._message_count = 0
        self._ack_count = 0
        self._nak_count = 0

        # Configuration from environment with validation
        REQUIRED_CONFIGS = [
            "NATS_URL", "NATS_STREAM", "NATS_DURABLE",
            "NATS_SUBJECT_ORDER_INTENT", "NATS_SUBJECT_FILL"
        ]

        missing_configs = [key for key in REQUIRED_CONFIGS if not os.getenv(key)]
        if missing_configs:
            raise SystemExit(f"FATAL: Missing required environment variables: {missing_configs}")

        self.nats_url = os.getenv("NATS_URL")
        self.stream_name = os.getenv("NATS_STREAM")
        self.durable_name = os.getenv("NATS_DURABLE")
        self.subject_order_intent = os.getenv("NATS_SUBJECT_ORDER_INTENT")
        self.subject_fill = os.getenv("NATS_SUBJECT_FILL")
        self.subject_reconcile = os.getenv("NATS_SUBJECT_RECONCILE", "executions.reconcile")

        # Retry configuration
        self.max_retries = int(os.getenv("NATS_MAX_RETRIES", "30"))
        self.initial_retry_delay = float(os.getenv("NATS_INITIAL_RETRY_DELAY", "1.0"))
        self.max_retry_delay = float(os.getenv("NATS_MAX_RETRY_DELAY", "30.0"))
        self.retry_backoff_factor = float(os.getenv("NATS_RETRY_BACKOFF_FACTOR", "2.0"))

    async def connect(self):
        """Connect to NATS server and setup JetStream with retry logic"""
        retry_delay = self.initial_retry_delay
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info("Attempting NATS connection",
                          attempt=attempt + 1,
                          max_retries=self.max_retries,
                          nats_url=self.nats_url)

                # Robust connection settings
                self.nc = await nats.connect(
                    servers=[self.nats_url],
                    reconnect_time_wait=2,
                    max_reconnect_attempts=-1,  # infinite reconnect
                    ping_interval=10,
                    allow_reconnect=True,
                    connect_timeout=3,
                    disconnected_cb=self._on_disconnected,
                    reconnected_cb=self._on_reconnected,
                    error_cb=self._on_error,
                    closed_cb=self._on_closed,
                )
                self.js = self.nc.jetstream()
                self.status = "connected"

                logger.info("Connected to NATS",
                           nats_url=self.nats_url,
                           stream=self.stream_name,
                           attempt=attempt + 1)

                # Ensure stream exists with retry
                await self._ensure_stream_with_retry()

                # Validate consumer configuration matches expectations
                await self._validate_consumer_config()
                return  # Success!

            except Exception as e:
                last_error = e
                self.status = "disconnected"

                if attempt < self.max_retries:
                    logger.warning("NATS connection failed, retrying",
                                 error=str(e),
                                 attempt=attempt + 1,
                                 max_retries=self.max_retries,
                                 retry_delay=retry_delay)

                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * self.retry_backoff_factor, self.max_retry_delay)
                else:
                    logger.error("Failed to connect to NATS after all retries",
                               error=str(e),
                               attempts=attempt + 1,
                               nats_url=self.nats_url)

        # If we get here, all retries failed
        self.status = "failed"
        raise ConnectionError(f"Failed to connect to NATS after {self.max_retries} retries: {last_error}")

    async def _on_disconnected(self):
        """Callback for NATS disconnection"""
        logger.warning("NATS disconnected")
        self.status = "disconnected"

    async def _on_reconnected(self):
        """Callback for NATS reconnection"""
        logger.info("NATS reconnected")
        self.status = "connected"

    async def _on_error(self, e):
        """Callback for NATS errors"""
        logger.error("NATS error", error=str(e))

    async def _on_closed(self):
        """Callback for NATS connection closed"""
        logger.error("NATS connection closed")
        self.status = "closed"

    async def disconnect(self):
        """Disconnect from NATS"""
        try:
            if self.subscription:
                await self.subscription.unsubscribe()

            if self.nc:
                await self.nc.close()

            self.status = "disconnected"
            logger.info("Disconnected from NATS")

        except Exception as e:
            logger.error("Error during NATS disconnect", error=str(e))

    async def _ensure_stream_with_retry(self):
        """Ensure the trading-events stream exists with retry logic"""
        retry_delay = 1.0
        max_stream_retries = 10

        for attempt in range(max_stream_retries):
            try:
                await self.js.stream_info(self.stream_name)
                logger.info("Stream verified", stream=self.stream_name, attempt=attempt + 1)
                return
            except nats.js.errors.NotFoundError:
                if attempt < max_stream_retries - 1:
                    logger.warning("Stream not found, waiting for bootstrap",
                                 stream=self.stream_name,
                                 attempt=attempt + 1,
                                 retry_delay=retry_delay)
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 10.0)
                else:
                    logger.error("Stream not found after all retries", stream=self.stream_name)
                    raise

    async def _validate_consumer_config(self):
        """Validate consumer configuration matches expected values"""
        try:
            info = await self.js.consumer_info(self.stream_name, self.durable_name)
            config = info.config

            # Validate filter subject matches
            if config.filter_subject != self.subject_order_intent:
                raise ValueError(
                    f"Consumer filter subject mismatch: expected {self.subject_order_intent}, "
                    f"got {config.filter_subject}"
                )

            # Validate durable name matches
            if config.durable_name != self.durable_name:
                raise ValueError(
                    f"Consumer durable name mismatch: expected {self.durable_name}, "
                    f"got {config.durable_name}"
                )

            logger.info("Consumer configuration validated",
                       durable_name=config.durable_name,
                       filter_subject=config.filter_subject,
                       deliver_policy=str(config.deliver_policy),
                       ack_policy=str(config.ack_policy))

        except nats.js.errors.NotFoundError:
            raise ValueError(f"Consumer {self.durable_name} not found in stream {self.stream_name}")
        except Exception as e:
            logger.error("Failed to validate consumer configuration", error=str(e))
            raise

    async def _ensure_stream(self):
        """Ensure the trading-events stream exists (fallback method)"""
        try:
            await self.js.stream_info(self.stream_name)
        except nats.js.errors.NotFoundError:
            # Stream doesn't exist, create it
            await self.js.add_stream(
                name=self.stream_name,
                subjects=["decisions.*", "executions.*", "signals.*"],
                max_age=24 * 60 * 60,  # 24 hours retention
                storage="file"
            )
            logger.info("Created NATS stream", stream=self.stream_name)

    async def start_consumer(self, simulator):
        """Start consuming order intent events"""
        try:
            self.subscription = await self.js.pull_subscribe(
                subject=self.subject_order_intent,
                durable=self.durable_name,
                stream=self.stream_name  # Explicitly specify the stream
            )

            logger.info("Started NATS consumer",
                       subject=self.subject_order_intent,
                       durable=self.durable_name)

            # Start background task to process messages
            asyncio.create_task(self._consume_messages(simulator))

        except Exception as e:
            logger.error("Failed to start NATS consumer", error=str(e))
            raise

    async def _consume_messages(self, simulator):
        """Resilient background task to consume and process messages"""
        batch_size = int(os.getenv("NATS_BATCH_SIZE", "1"))  # Start with 1 for debugging
        fetch_timeout = float(os.getenv("NATS_FETCH_TIMEOUT", "2.5"))  # Longer timeout

        logger.info("Starting message consumer loop",
                   batch_size=batch_size,
                   fetch_timeout=fetch_timeout)

        while True:
            try:
                if not self.subscription:
                    await asyncio.sleep(1)
                    continue

                # Fetch messages with timeout handling
                try:
                    # Increment fetch attempts counter
                    self._fetch_count += 1
                    if hasattr(simulator, 'fetch_calls'):
                        simulator.fetch_calls.inc()

                    messages = await self.subscription.fetch(batch=batch_size, timeout=fetch_timeout)

                    if not messages:
                        if hasattr(simulator, 'fetch_empty'):
                            simulator.fetch_empty.inc()
                        self._log_fetch_stats()
                        await asyncio.sleep(0.05)
                        continue

                    self._message_count += len(messages)
                    self._log_fetch_stats()

                except asyncio.TimeoutError:
                    logger.debug("Fetch timeout (normal)")
                    await asyncio.sleep(0.05)
                    continue
                except (nats.errors.ConnectionClosedError, nats.errors.NoRespondersError) as e:
                    # Connection issues - log and backoff
                    logger.warning("Pull fetch error, backing off", error=str(e))
                    await asyncio.sleep(1.0)
                    continue

                for msg in messages:
                    corr_id = "unknown"
                    try:
                        # Decode message
                        data = json.loads(msg.data.decode())
                        headers = dict(msg.headers) if msg.headers else {}

                        # Extract correlation ID
                        corr_id = data.get("corr_id") or headers.get("corr_id") or self._generate_corr_id()

                        logger.info("Processing order intent",
                                   corr_id=corr_id,
                                   instrument=data.get("instrument"),
                                   side=data.get("side"))

                        # Process with simulator
                        await simulator.process_order_intent(data, corr_id, self)

                        # Acknowledge message on success
                        await msg.ack()
                        self._ack_count += 1

                    except Exception as e:
                        logger.error("Error processing message",
                                   error=str(e),
                                   corr_id=corr_id)

                        # Negative acknowledge (will retry)
                        try:
                            await msg.nak()
                            self._nak_count += 1
                        except Exception as nak_error:
                            logger.error("Failed to NAK message", error=str(nak_error))

            except Exception as e:
                logger.error("Unexpected error in message consumer", error=str(e))
                await asyncio.sleep(5.0)  # Longer backoff on unexpected errors

    async def publish_fill(self, fill_event: Dict[str, Any], corr_id: str):
        """Publish execution fill event"""
        try:
            if not self.js:
                # Buffer event if NATS unavailable
                self.event_buffer.append(("fill", fill_event, corr_id))
                raise Exception("NATS not connected")

            # Add headers
            headers = {
                "corr_id": corr_id,
                "event_type": "execution_fill",
                "timestamp": fill_event.get("fill_timestamp")
            }

            await self.js.publish(
                subject=self.subject_fill,
                payload=json.dumps(fill_event).encode(),
                headers=headers
            )

            logger.info("Published fill event",
                       corr_id=corr_id,
                       fill_id=fill_event.get("fill_id"),
                       instrument=fill_event.get("instrument"))

        except Exception as e:
            logger.error("Failed to publish fill event",
                        corr_id=corr_id,
                        error=str(e))
            raise

    async def publish_reconcile(self, reconcile_event: Dict[str, Any], corr_id: str):
        """Publish reconciliation event"""
        try:
            if not self.js:
                # Buffer event if NATS unavailable
                self.event_buffer.append(("reconcile", reconcile_event, corr_id))
                raise Exception("NATS not connected")

            # Add headers
            headers = {
                "corr_id": corr_id,
                "event_type": "execution_reconcile",
                "timestamp": reconcile_event.get("reconcile_timestamp")
            }

            await self.js.publish(
                subject=self.subject_reconcile,
                payload=json.dumps(reconcile_event).encode(),
                headers=headers
            )

            logger.info("Published reconcile event",
                       corr_id=corr_id,
                       reconcile_id=reconcile_event.get("reconcile_id"),
                       instrument=reconcile_event.get("instrument"))

        except Exception as e:
            logger.error("Failed to publish reconcile event",
                        corr_id=corr_id,
                        error=str(e))
            raise

    async def get_status(self) -> str:
        """Get current NATS connection status"""
        if not self.nc or not self.nc.is_connected:
            return "disconnected"

        try:
            # Test connection with ping
            await self.nc.flush(timeout=1.0)
            return "connected"
        except Exception:
            return "degraded"

    async def get_pending_count(self) -> int:
        """Get number of buffered events"""
        return len(self.event_buffer)

    async def check_consumer_health(self) -> Dict[str, Any]:
        """Check consumer configuration health"""
        try:
            if not self.js:
                return {"status": "disconnected", "error": "JetStream not connected"}

            info = await self.js.consumer_info(self.stream_name, self.durable_name)
            config = info.config

            # Check for configuration drift
            drift_issues = []
            if config.filter_subject != self.subject_order_intent:
                drift_issues.append(f"filter_subject: expected {self.subject_order_intent}, got {config.filter_subject}")
            if config.durable_name != self.durable_name:
                drift_issues.append(f"durable_name: expected {self.durable_name}, got {config.durable_name}")

            if drift_issues:
                return {
                    "status": "degraded",
                    "error": "Consumer configuration drift detected",
                    "drift_issues": drift_issues
                }

            return {
                "status": "healthy",
                "durable_name": config.durable_name,
                "filter_subject": config.filter_subject,
                "num_pending": info.num_pending,
                "num_ack_pending": info.num_ack_pending,
                "num_waiting": info.num_waiting
            }

        except nats.js.errors.NotFoundError:
            return {
                "status": "degraded",
                "error": f"Consumer {self.durable_name} not found"
            }
        except Exception as e:
            return {
                "status": "degraded",
                "error": f"Consumer health check failed: {str(e)}"
            }

    def _log_fetch_stats(self):
        """Log fetch statistics with rate limiting"""
        current_time = time.time()
        if current_time - self._last_fetch_log >= self._fetch_log_interval:
            logger.info("NATS fetch statistics",
                       fetch_calls_total=self._fetch_count,
                       messages_received=self._message_count,
                       acks_sent=self._ack_count,
                       naks_sent=self._nak_count,
                       success_rate=round(self._ack_count / max(self._message_count, 1), 3),
                       period_seconds=round(current_time - self._last_fetch_log, 1))
            self._last_fetch_log = current_time

    def _generate_corr_id(self) -> str:
        """Generate synthetic correlation ID"""
        return f"synthetic_{uuid.uuid4().hex[:8]}"

    async def retry_buffered_events(self):
        """Retry publishing buffered events when connection restored"""
        retry_count = 0
        while self.event_buffer and retry_count < len(self.event_buffer):
            try:
                event_type, event_data, corr_id = self.event_buffer.popleft()

                if event_type == "fill":
                    await self.publish_fill(event_data, corr_id)
                elif event_type == "reconcile":
                    await self.publish_reconcile(event_data, corr_id)

                logger.info("Retried buffered event",
                           event_type=event_type,
                           corr_id=corr_id)

            except Exception as e:
                # Put event back and stop retrying
                self.event_buffer.appendleft((event_type, event_data, corr_id))
                logger.error("Failed to retry buffered event",
                           event_type=event_type,
                           corr_id=corr_id,
                           error=str(e))
                break

            retry_count += 1
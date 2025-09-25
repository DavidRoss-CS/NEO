import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import nats
from nats.errors import ConnectionClosedError, TimeoutError as NatsTimeoutError

# NEO schema registry integration
from at_core.validators import validate_agent_output, ValidationError
from at_core.schemas import load_schema

# Local modules
from .slack_adapter import SlackAdapter
from .telegram_adapter import TelegramAdapter
from .paper_trader import PaperTrader
from .notification_formatter import NotificationFormatter

# Configure structured logging
logger = structlog.get_logger()

# Environment variables
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
NATS_STREAM = os.getenv("NATS_STREAM", "trading-events")
SERVICE_NAME = os.getenv("SERVICE_NAME", "at-output-manager")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# External service configuration
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Feature flags
FF_OUTPUT_SLACK = os.getenv("FF_OUTPUT_SLACK", "false").lower() == "true"
FF_OUTPUT_TELEGRAM = os.getenv("FF_OUTPUT_TELEGRAM", "false").lower() == "true"
FF_EXEC_PAPER = os.getenv("FF_EXEC_PAPER", "true").lower() == "true"
FF_ENHANCED_LOGGING = os.getenv("FF_ENHANCED_LOGGING", "false").lower() == "true"

# Delivery configuration
DELIVERY_TIMEOUT_SEC = int(os.getenv("DELIVERY_TIMEOUT_SEC", "10"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_DELAY_SEC = int(os.getenv("RETRY_DELAY_SEC", "2"))

# Prometheus metrics
notifications_sent = Counter('output_notifications_sent_total', 'Total notifications sent', ['channel', 'status'])
notification_duration = Histogram('output_notification_duration_seconds', 'Notification delivery duration', ['channel'])
paper_trades_executed = Counter('output_paper_trades_total', 'Paper trades executed', ['side', 'status'])
delivery_errors = Counter('output_delivery_errors_total', 'Delivery errors', ['channel', 'error_type'])
feature_flag_evaluations = Counter('output_feature_flag_evaluations_total', 'Feature flag evaluations', ['flag', 'result'])
agent_decisions_processed = Counter('output_agent_decisions_total', 'Agent decisions processed', ['agent_type', 'severity'])

app = FastAPI(
    title="at-output-manager",
    description="Multi-channel Output Delivery Service for Trading Notifications",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=3600,
)

# Global state
nats_client: Optional[nats.NATS] = None
js_client = None
slack_adapter: Optional[SlackAdapter] = None
telegram_adapter: Optional[TelegramAdapter] = None
paper_trader: Optional[PaperTrader] = None
notification_formatter: Optional[NotificationFormatter] = None
start_time = time.time()

class NotificationRequest(BaseModel):
    """Manual notification request via REST API"""
    channel: str = Field(..., description="Delivery channel (slack, telegram)")
    agent_output: Dict[str, Any] = Field(..., description="Agent output data")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracking")

class DeliveryStatus(BaseModel):
    """Delivery status response"""
    delivery_id: str
    channel: str
    status: str
    timestamp: str
    correlation_id: Optional[str] = None
    error: Optional[str] = None

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Request processing middleware"""
    # Add correlation ID if not present
    corr_id = request.headers.get("X-Correlation-ID", f"req_{uuid.uuid4().hex[:12]}")
    request.state.corr_id = corr_id

    # Process request
    start = time.time()
    response = await call_next(request)

    # Add response headers
    response.headers["X-Correlation-ID"] = corr_id
    response.headers["X-Service-Name"] = SERVICE_NAME

    # Record metrics
    duration = time.time() - start
    logger.info(
        "Request processed",
        corr_id=corr_id,
        method=request.method,
        path=request.url.path,
        duration_ms=duration * 1000,
        status_code=response.status_code
    )

    return response

@app.on_event("startup")
async def startup_event():
    """Initialize service components"""
    global nats_client, js_client, slack_adapter, telegram_adapter, paper_trader, notification_formatter

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    try:
        # Initialize NATS connection
        nats_client = await nats.connect(NATS_URL)
        js_client = nats_client.jetstream()

        # Initialize notification formatter
        notification_formatter = NotificationFormatter()

        # Initialize Slack adapter if enabled
        if FF_OUTPUT_SLACK and SLACK_WEBHOOK_URL:
            slack_adapter = SlackAdapter(
                webhook_url=SLACK_WEBHOOK_URL,
                formatter=notification_formatter
            )
            await slack_adapter.initialize()
            feature_flag_evaluations.labels(flag='FF_OUTPUT_SLACK', result='enabled').inc()
        else:
            feature_flag_evaluations.labels(flag='FF_OUTPUT_SLACK', result='disabled').inc()

        # Initialize Telegram adapter if enabled
        if FF_OUTPUT_TELEGRAM and TELEGRAM_BOT_TOKEN:
            telegram_adapter = TelegramAdapter(
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=TELEGRAM_CHAT_ID,
                formatter=notification_formatter
            )
            await telegram_adapter.initialize()
            feature_flag_evaluations.labels(flag='FF_OUTPUT_TELEGRAM', result='enabled').inc()
        else:
            feature_flag_evaluations.labels(flag='FF_OUTPUT_TELEGRAM', result='disabled').inc()

        # Initialize paper trader if enabled
        if FF_EXEC_PAPER:
            paper_trader = PaperTrader(
                js_client=js_client,
                initial_balance=10000.0  # Start with $10k paper money
            )
            await paper_trader.initialize()
            feature_flag_evaluations.labels(flag='FF_EXEC_PAPER', result='enabled').inc()
        else:
            feature_flag_evaluations.labels(flag='FF_EXEC_PAPER', result='disabled').inc()

        # Subscribe to agent decision events
        await setup_nats_subscriptions()

        logger.info(
            "Output manager service started",
            nats_url=NATS_URL,
            port=8008,
            service_name=SERVICE_NAME,
            ff_output_slack=FF_OUTPUT_SLACK,
            ff_output_telegram=FF_OUTPUT_TELEGRAM,
            ff_exec_paper=FF_EXEC_PAPER,
            slack_enabled=slack_adapter is not None,
            telegram_enabled=telegram_adapter is not None,
            paper_trader_enabled=paper_trader is not None
        )

    except Exception as e:
        logger.error(f"Failed to start output manager: {e}")
        raise

async def setup_nats_subscriptions():
    """Set up NATS subscriptions for agent decisions"""
    try:
        # Subscribe to agent decision events
        await js_client.subscribe(
            "decisions.agent_output.*",
            cb=handle_agent_decision,
            durable="output-manager-decisions",
            manual_ack=True
        )

        logger.info("NATS subscriptions established", subjects=["decisions.agent_output.*"])

    except Exception as e:
        logger.error(f"Failed to setup NATS subscriptions: {e}")
        raise

async def handle_agent_decision(msg):
    """Handle incoming agent decision events from NATS"""
    corr_id = msg.headers.get('Corr-ID', f"nats_{uuid.uuid4().hex[:8]}")

    try:
        # Parse message
        agent_output = json.loads(msg.data.decode())

        if FF_ENHANCED_LOGGING:
            logger.debug(
                "Agent decision received",
                corr_id=corr_id,
                subject=msg.subject,
                agent_id=agent_output.get('agent_id'),
                agent_type=agent_output.get('agent_type'),
                confidence=agent_output.get('confidence')
            )

        # Extract severity from subject
        subject_parts = msg.subject.split('.')
        severity = subject_parts[-1] if len(subject_parts) >= 4 else "info"
        agent_type = agent_output.get('agent_type', 'unknown')

        # Track metrics
        agent_decisions_processed.labels(agent_type=agent_type, severity=severity).inc()

        # Process deliveries concurrently
        delivery_tasks = []

        # Slack notification
        if slack_adapter and should_deliver_to_channel("slack", severity):
            delivery_tasks.append(
                deliver_notification(slack_adapter, "slack", agent_output, corr_id)
            )

        # Telegram notification
        if telegram_adapter and should_deliver_to_channel("telegram", severity):
            delivery_tasks.append(
                deliver_notification(telegram_adapter, "telegram", agent_output, corr_id)
            )

        # Paper trading execution
        if paper_trader and agent_output.get('orders') and FF_EXEC_PAPER:
            delivery_tasks.append(
                execute_paper_trades(agent_output, corr_id)
            )

        # Execute all deliveries concurrently
        if delivery_tasks:
            await asyncio.gather(*delivery_tasks, return_exceptions=True)

        # Acknowledge message
        await msg.ack()

        # Publish delivery audit event
        await publish_audit_event(agent_output, corr_id, "agent_decision_processed")

    except Exception as e:
        logger.error(
            "Failed to process agent decision",
            corr_id=corr_id,
            error=str(e),
            subject=msg.subject
        )

        # Send to DLQ
        try:
            dlq_payload = {
                "original_subject": msg.subject,
                "error": str(e),
                "corr_id": corr_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            await js_client.publish(
                f"dlq.{msg.subject}",
                json.dumps(dlq_payload).encode(),
                headers={"Corr-ID": corr_id, "Error-Type": "delivery_processing"}
            )
        except Exception as dlq_error:
            logger.error(f"Failed to send to DLQ: {dlq_error}", corr_id=corr_id)

        await msg.ack()  # Ack to prevent redelivery

def should_deliver_to_channel(channel: str, severity: str) -> bool:
    """Determine if notification should be delivered to channel based on severity"""
    # Critical severity goes to all enabled channels
    if severity == "critical":
        return True

    # Warning severity goes to primary channels
    if severity == "warn":
        return channel in ["slack", "telegram"]

    # Info severity only to configured channels (could be filtered)
    return True  # For now, deliver all to enabled channels

async def deliver_notification(adapter, channel: str, agent_output: Dict[str, Any], corr_id: str):
    """Deliver notification to specific channel"""
    delivery_start = time.time()

    try:
        # Deliver with retry logic
        for attempt in range(RETRY_ATTEMPTS):
            try:
                delivery_id = await adapter.send_notification(agent_output, corr_id)

                # Record success metrics
                duration = time.time() - delivery_start
                notification_duration.labels(channel=channel).observe(duration)
                notifications_sent.labels(channel=channel, status='success').inc()

                # Publish delivery confirmation
                await publish_delivery_confirmation(channel, delivery_id, agent_output, corr_id)

                logger.info(
                    "Notification delivered successfully",
                    corr_id=corr_id,
                    channel=channel,
                    delivery_id=delivery_id,
                    attempt=attempt + 1,
                    duration_ms=duration * 1000
                )

                return delivery_id

            except Exception as e:
                if attempt == RETRY_ATTEMPTS - 1:
                    # Final attempt failed
                    notifications_sent.labels(channel=channel, status='error').inc()
                    delivery_errors.labels(channel=channel, error_type=type(e).__name__).inc()

                    logger.error(
                        "Notification delivery failed after retries",
                        corr_id=corr_id,
                        channel=channel,
                        attempts=RETRY_ATTEMPTS,
                        error=str(e)
                    )
                    raise
                else:
                    # Retry after delay
                    logger.warning(
                        "Notification delivery failed, retrying",
                        corr_id=corr_id,
                        channel=channel,
                        attempt=attempt + 1,
                        error=str(e)
                    )
                    await asyncio.sleep(RETRY_DELAY_SEC * (attempt + 1))

    except Exception as e:
        # Log final failure
        logger.error(
            "Notification delivery completely failed",
            corr_id=corr_id,
            channel=channel,
            error=str(e)
        )
        # Don't re-raise to avoid breaking other deliveries

async def execute_paper_trades(agent_output: Dict[str, Any], corr_id: str):
    """Execute paper trades based on agent orders"""
    orders = agent_output.get('orders', [])
    if not orders:
        return

    try:
        for order in orders:
            trade_result = await paper_trader.execute_trade(order, agent_output, corr_id)

            # Record metrics
            side = order.get('side', 'unknown')
            status = 'success' if trade_result.get('success') else 'error'
            paper_trades_executed.labels(side=side, status=status).inc()

            # Publish execution event
            await js_client.publish(
                "outputs.execution.paper",
                json.dumps({
                    "trade_result": trade_result,
                    "agent_output": agent_output,
                    "correlation_id": corr_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }).encode(),
                headers={"Corr-ID": corr_id, "Trade-ID": trade_result.get('trade_id', '')}
            )

        logger.info(
            "Paper trades executed",
            corr_id=corr_id,
            orders_count=len(orders),
            agent_type=agent_output.get('agent_type')
        )

    except Exception as e:
        logger.error(
            "Paper trade execution failed",
            corr_id=corr_id,
            error=str(e),
            orders_count=len(orders)
        )

async def publish_delivery_confirmation(channel: str, delivery_id: str, agent_output: Dict[str, Any], corr_id: str):
    """Publish delivery confirmation to NATS"""
    try:
        confirmation = {
            "delivery_id": delivery_id,
            "channel": channel,
            "agent_output": {
                "agent_id": agent_output.get('agent_id'),
                "agent_type": agent_output.get('agent_type'),
                "correlation_id": agent_output.get('correlation_id')
            },
            "delivered_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": corr_id
        }

        await js_client.publish(
            f"outputs.notification.{channel}",
            json.dumps(confirmation).encode(),
            headers={"Corr-ID": corr_id, "Delivery-ID": delivery_id}
        )

    except Exception as e:
        logger.warning(f"Failed to publish delivery confirmation: {e}", corr_id=corr_id)

async def publish_audit_event(agent_output: Dict[str, Any], corr_id: str, event_type: str):
    """Publish audit event to NATS"""
    try:
        audit_event = {
            "event_type": event_type,
            "agent_type": agent_output.get('agent_type'),
            "correlation_id": corr_id,
            "confidence": agent_output.get('confidence'),
            "orders_count": len(agent_output.get('orders', [])),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await js_client.publish(
            "audit.events",
            json.dumps(audit_event).encode(),
            headers={"Corr-ID": corr_id, "Event-Type": event_type}
        )

    except Exception as e:
        logger.warning(f"Failed to publish audit event: {e}", corr_id=corr_id)

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "ok": True,
        "service": SERVICE_NAME,
        "version": "1.0.0",
        "uptime_seconds": int(time.time() - start_time),
        "nats_connected": nats_client is not None and nats_client.is_connected,
        "adapters": {
            "slack_enabled": slack_adapter is not None,
            "telegram_enabled": telegram_adapter is not None,
            "paper_trader_enabled": paper_trader is not None
        }
    }

    if not health_status["nats_connected"]:
        health_status["ok"] = False
        health_status["error"] = "NATS disconnected"
        return JSONResponse(status_code=503, content=health_status)

    return health_status

@app.get("/healthz/detailed")
async def detailed_health_check():
    """Detailed health check with adapter status"""
    health_status = await health_check()

    if isinstance(health_status, JSONResponse):
        return health_status

    health_status.update({
        "feature_flags": {
            "FF_OUTPUT_SLACK": FF_OUTPUT_SLACK,
            "FF_OUTPUT_TELEGRAM": FF_OUTPUT_TELEGRAM,
            "FF_EXEC_PAPER": FF_EXEC_PAPER,
            "FF_ENHANCED_LOGGING": FF_ENHANCED_LOGGING
        },
        "configuration": {
            "delivery_timeout_sec": DELIVERY_TIMEOUT_SEC,
            "retry_attempts": RETRY_ATTEMPTS,
            "retry_delay_sec": RETRY_DELAY_SEC
        },
        "adapter_health": {}
    })

    # Check adapter health
    if slack_adapter:
        health_status["adapter_health"]["slack"] = await slack_adapter.health_check()
    if telegram_adapter:
        health_status["adapter_health"]["telegram"] = await telegram_adapter.health_check()
    if paper_trader:
        health_status["adapter_health"]["paper_trader"] = await paper_trader.get_status()

    return health_status

@app.post("/notify")
async def send_manual_notification(request: Request, notification_request: NotificationRequest):
    """Manual notification sending via REST API"""
    corr_id = request.state.corr_id
    correlation_id = notification_request.correlation_id or corr_id

    channel = notification_request.channel.lower()

    if channel == "slack" and not slack_adapter:
        raise HTTPException(status_code=503, detail="Slack adapter not available")

    if channel == "telegram" and not telegram_adapter:
        raise HTTPException(status_code=503, detail="Telegram adapter not available")

    try:
        adapter = slack_adapter if channel == "slack" else telegram_adapter
        delivery_id = await deliver_notification(
            adapter, channel, notification_request.agent_output, correlation_id
        )

        return DeliveryStatus(
            delivery_id=delivery_id,
            channel=channel,
            status="delivered",
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id
        ).dict()

    except Exception as e:
        logger.error(f"Manual notification failed: {e}", corr_id=corr_id)
        raise HTTPException(status_code=500, detail=f"Notification delivery failed: {str(e)}")

@app.get("/stats")
async def get_delivery_stats():
    """Get delivery statistics"""
    stats = {
        "service_uptime_seconds": int(time.time() - start_time),
        "adapters_enabled": {
            "slack": slack_adapter is not None,
            "telegram": telegram_adapter is not None,
            "paper_trader": paper_trader is not None
        }
    }

    if paper_trader:
        stats["paper_trading"] = await paper_trader.get_stats()

    return stats

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    global nats_client, slack_adapter, telegram_adapter, paper_trader

    if slack_adapter:
        await slack_adapter.cleanup()

    if telegram_adapter:
        await telegram_adapter.cleanup()

    if paper_trader:
        await paper_trader.cleanup()

    if nats_client:
        await nats_client.close()

    logger.info("Output manager service stopped")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8008))
    uvicorn.run(app, host="0.0.0.0", port=port)
import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Set

from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import nats
from nats.errors import ConnectionClosedError, TimeoutError as NatsTimeoutError

# NEO schema registry integration
from at_core.validators import validate_signal_event, ValidationError
from at_core.schemas import load_schema

# Configure structured logging
logger = structlog.get_logger()

# Environment variables
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
NATS_STREAM = os.getenv("NATS_STREAM", "trading-events")
API_KEY_HMAC_SECRET = os.getenv("API_KEY_HMAC_SECRET", "")
REPLAY_WINDOW_SEC = int(os.getenv("REPLAY_WINDOW_SEC", "300"))  # 5 minutes
RATE_LIMIT_RPS = int(os.getenv("RATE_LIMIT_RPS", "100"))
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"
ALLOWED_SOURCES = os.getenv("ALLOWED_SOURCES", "tradingview,custom,test").split(",")
SERVICE_NAME = os.getenv("SERVICE_NAME", "at-gateway")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB

# Feature flags for v1.0 enhancements
FF_TV_SLICE = os.getenv("FF_TV_SLICE", "false").lower() == "true"
FF_ENHANCED_LOGGING = os.getenv("FF_ENHANCED_LOGGING", "false").lower() == "true"
FF_CIRCUIT_BREAKER = os.getenv("FF_CIRCUIT_BREAKER", "true").lower() == "true"

# Prometheus metrics
webhooks_received = Counter('gateway_webhooks_received_total', 'Total webhooks received', ['source', 'status'])
webhook_duration = Histogram('gateway_webhook_duration_seconds', 'Webhook processing duration', ['status_class'])
validation_errors = Counter('gateway_validation_errors_total', 'Validation errors by type', ['type'])
nats_errors = Counter('gateway_nats_errors_total', 'NATS errors by type', ['type'])
normalization_errors = Counter('gateway_normalization_errors_total', 'Normalization errors', ['source'])
rate_limit_exceeded = Counter('gateway_rate_limit_exceeded_total', 'Rate limit violations', ['source'])
idempotency_conflicts = Counter('gateway_idempotency_conflicts_total', 'Idempotency key conflicts')
backpressure_engaged = Counter('gateway_backpressure_total', 'Backpressure events')
maintenance_mode_requests = Counter('gateway_maintenance_mode_total', 'Requests during maintenance')

# v1.0 Enhanced metrics
schema_validation_errors = Counter('gateway_schema_validation_errors_total', 'Schema validation errors', ['schema_type', 'field'])
signal_categorization_total = Counter('gateway_signal_categorization_total', 'Signal categorization', ['type', 'priority'])
feature_flag_evaluations = Counter('gateway_feature_flag_evaluations_total', 'Feature flag evaluations', ['flag', 'result'])
enhanced_processing_duration = Histogram('gateway_enhanced_processing_seconds', 'Enhanced processing duration')

app = FastAPI(
    title="at-gateway",
    description="Market Data Ingestion Service",
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
processed_nonces: Set[str] = set()
idempotency_cache: Dict[str, Dict] = {}
start_time = time.time()

class MarketSignal(BaseModel):
    """Legacy market signal for backward compatibility"""
    instrument: str = Field(..., min_length=1, max_length=20)
    price: float | str
    signal: str = Field(..., min_length=1, max_length=50)
    strength: float = Field(..., ge=0, le=1)
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator('price')
    def validate_price(cls, v):
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                raise ValueError(f"Invalid price: {v}")
        return v

def categorize_signal_type(signal: str, metadata: Optional[Dict] = None) -> str:
    """Categorize signal type from TradingView or custom signals"""
    signal_lower = signal.lower()

    # Momentum indicators
    if any(term in signal_lower for term in ['rsi', 'macd', 'momentum', 'stoch']):
        return 'momentum'

    # Breakout patterns
    if any(term in signal_lower for term in ['breakout', 'break', 'support', 'resistance']):
        return 'breakout'

    # Technical indicators
    if any(term in signal_lower for term in ['ema', 'sma', 'bollinger', 'adx']):
        return 'indicator'

    # Sentiment based
    if any(term in signal_lower for term in ['sentiment', 'fear', 'greed', 'vix']):
        return 'sentiment'

    # Default to custom
    return 'custom'

def determine_signal_priority(strength: float, signal_type: str, metadata: Optional[Dict] = None) -> str:
    """Determine signal priority based on strength and context"""
    # High priority thresholds
    if strength >= 0.8:
        return 'high'

    # Context-based priority
    if signal_type in ['breakout', 'momentum'] and strength >= 0.6:
        return 'high'

    return 'std'

def create_signal_event_v1(signal: MarketSignal, source: str, corr_id: str) -> Dict[str, Any]:
    """Convert legacy MarketSignal to SignalEventV1 format"""
    signal_type = categorize_signal_type(signal.signal, signal.metadata)
    priority = determine_signal_priority(signal.strength, signal_type, signal.metadata)

    return {
        "schema_version": "1.0.0",
        "intent_id": f"{source}_{uuid.uuid4().hex[:8]}",
        "correlation_id": corr_id,
        "source": source,
        "instrument": signal.instrument.upper(),
        "type": signal_type,
        "strength": signal.strength,
        "payload": {
            "price": float(signal.price),
            "signal": signal.signal,
            "metadata": signal.metadata or {},
            "priority": priority
        },
        "ts_iso": signal.timestamp or datetime.now(timezone.utc).isoformat()
    }

@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    """Enforce request size limit"""
    if request.headers.get("content-length"):
        content_length = int(request.headers["content-length"])
        if content_length > MAX_PAYLOAD_SIZE:
            validation_errors.labels(type="size").inc()
            return JSONResponse(
                status_code=413,
                content={
                    "error": "GW-008",
                    "message": "Payload too large",
                    "max_size": f"{MAX_PAYLOAD_SIZE} bytes"
                }
            )

    # Add correlation ID if not present
    # First check for correlation_id in body metadata if it's a POST with JSON
    corr_id = None
    if request.method == "POST" and request.headers.get("content-type") == "application/json":
        try:
            body_bytes = await request.body()
            request._body = body_bytes  # Cache the body for later use
            body_json = json.loads(body_bytes)
            if isinstance(body_json.get("metadata"), dict):
                corr_id = body_json["metadata"].get("correlation_id")
        except:
            pass

    # Fall back to header or generate new one
    if not corr_id:
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
    status_class = f"{response.status_code // 100}xx"
    webhook_duration.labels(status_class=status_class).observe(duration)

    return response

async def verify_hmac_signature(
    request: Request,
    x_signature: Optional[str] = Header(None),
    x_timestamp: Optional[str] = Header(None),
    x_nonce: Optional[str] = Header(None)
):
    """Verify HMAC signature and replay protection"""
    if not API_KEY_HMAC_SECRET:
        return  # Skip verification if no secret configured

    corr_id = request.state.corr_id

    # Check signature header
    if not x_signature:
        validation_errors.labels(type="signature").inc()
        logger.error("Missing signature header", corr_id=corr_id)
        raise HTTPException(status_code=401, detail="GW-001: Invalid signature")

    # Check timestamp and replay window
    if not x_timestamp:
        validation_errors.labels(type="replay").inc()
        logger.error("Missing timestamp header", corr_id=corr_id)
        raise HTTPException(status_code=401, detail="GW-002: Replay window exceeded")

    try:
        req_timestamp = float(x_timestamp)
        current_time = time.time()

        if abs(current_time - req_timestamp) > REPLAY_WINDOW_SEC:
            validation_errors.labels(type="replay").inc()
            logger.warning(
                "Request outside replay window",
                corr_id=corr_id,
                timestamp_provided=req_timestamp,
                window_sec=REPLAY_WINDOW_SEC,
                clock_skew_ms=(current_time - req_timestamp) * 1000
            )
            raise HTTPException(status_code=401, detail="GW-002: Replay window exceeded")
    except (ValueError, TypeError):
        validation_errors.labels(type="replay").inc()
        raise HTTPException(status_code=401, detail="GW-002: Invalid timestamp")

    # Check nonce for replay protection
    if x_nonce:
        if x_nonce in processed_nonces:
            validation_errors.labels(type="replay").inc()
            logger.warning("Duplicate nonce detected", corr_id=corr_id, nonce=x_nonce)
            raise HTTPException(status_code=401, detail="GW-002: Duplicate request")
        processed_nonces.add(x_nonce)

        # Clean old nonces periodically (simple implementation)
        if len(processed_nonces) > 10000:
            processed_nonces.clear()

    # Verify HMAC signature
    body = await request.body()
    message = f"{x_timestamp}.{x_nonce or ''}.{body.decode('utf-8')}"
    expected_signature = hmac.new(
        API_KEY_HMAC_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(x_signature, expected_signature):
        validation_errors.labels(type="signature").inc()
        logger.error(
            "Invalid HMAC signature",
            corr_id=corr_id,
            client_ip=request.client.host,
            signature_len=len(x_signature)
        )
        raise HTTPException(status_code=401, detail="GW-001: Invalid signature")

@app.on_event("startup")
async def startup_event():
    """Initialize NATS connection and JetStream"""
    global nats_client, js_client

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
        nats_client = await nats.connect(NATS_URL)
        js_client = nats_client.jetstream()

        # Create stream if it doesn't exist with v1.0 subjects
        try:
            await js_client.add_stream(
                name=NATS_STREAM,
                subjects=[
                    "signals.*",
                    "intents.*",
                    "decisions.*",
                    "outputs.*",
                    "executions.*",
                    "audit.*",
                    "dlq.*"
                ],
                retention="limits",
                max_msgs=1000000,
                max_age=7 * 24 * 3600,  # 7 days
                storage="file",
                num_replicas=1
            )
        except:
            pass  # Stream already exists

        logger.info(
            "Gateway service started",
            nats_url=NATS_URL,
            stream=NATS_STREAM,
            port=8001,
            service_name=SERVICE_NAME
        )
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        nats_client = None
        js_client = None

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    global nats_client
    if nats_client:
        await nats_client.close()
    logger.info("Gateway service stopped")

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "ok": True,
        "service": SERVICE_NAME,
        "uptime_seconds": int(time.time() - start_time),
        "nats_connected": nats_client is not None and nats_client.is_connected
    }

    if MAINTENANCE_MODE:
        health_status["ok"] = False
        health_status["maintenance"] = True
        return JSONResponse(status_code=503, content=health_status)

    if not health_status["nats_connected"]:
        health_status["ok"] = False
        health_status["error"] = "NATS disconnected"
        return JSONResponse(status_code=503, content=health_status)

    return health_status

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.post("/webhook/tradingview")
async def webhook_tradingview(
    request: Request,
    body: MarketSignal,
    x_idempotency_key: Optional[str] = Header(None),
    _: None = Depends(verify_hmac_signature)
):
    """TradingView webhook endpoint"""
    return await process_webhook(request, body, "tradingview", x_idempotency_key)

@app.post("/webhook/{source}")
async def webhook_generic(
    source: str,
    request: Request,
    body: MarketSignal,
    x_idempotency_key: Optional[str] = Header(None),
    _: None = Depends(verify_hmac_signature)
):
    """Generic webhook endpoint for any source"""
    if source not in ALLOWED_SOURCES:
        validation_errors.labels(type="source").inc()
        raise HTTPException(
            status_code=400,
            detail=f"GW-007: Source not allowed. Allowed: {ALLOWED_SOURCES}"
        )
    return await process_webhook(request, body, source, x_idempotency_key)

@app.post("/webhook")
async def webhook_default(
    request: Request,
    body: MarketSignal,
    x_idempotency_key: Optional[str] = Header(None),
    _: None = Depends(verify_hmac_signature)
):
    """Default webhook endpoint (alias to test source)"""
    return await process_webhook(request, body, "test", x_idempotency_key)

@app.get("/webhook/test")
async def webhook_test_redirect():
    """Redirect GET requests to the correct POST endpoint"""
    return {
        "message": "Use POST method for webhook submissions",
        "endpoints": {
            "default": "POST /webhook",
            "test_source": "POST /webhook/test",
            "tradingview": "POST /webhook/tradingview",
            "custom_source": "POST /webhook/{source}"
        },
        "documentation": "/docs"
    }

async def process_webhook(
    request: Request,
    body: MarketSignal,
    source: str,
    idempotency_key: Optional[str]
) -> Dict:
    """Process incoming webhook"""
    corr_id = request.state.corr_id

    # Check maintenance mode
    if MAINTENANCE_MODE:
        maintenance_mode_requests.inc()
        logger.warning("Request during maintenance", corr_id=corr_id)
        raise HTTPException(
            status_code=503,
            detail="GW-011: Service in maintenance mode",
            headers={"Retry-After": "3600"}
        )

    # Check idempotency
    if idempotency_key:
        if idempotency_key in idempotency_cache:
            cached = idempotency_cache[idempotency_key]
            if cached["payload_hash"] != hash(str(body.dict())):
                idempotency_conflicts.inc()
                logger.warning(
                    "Idempotency conflict",
                    corr_id=corr_id,
                    idempotency_key=idempotency_key,
                    original_corr_id=cached["corr_id"]
                )
                raise HTTPException(
                    status_code=409,
                    detail="GW-006: Idempotency conflict"
                )
            return cached["response"]

    # Check NATS connection
    if not nats_client or not nats_client.is_connected:
        nats_errors.labels(type="connection").inc()
        logger.error("NATS not connected", corr_id=corr_id)
        raise HTTPException(
            status_code=503,
            detail="GW-005: NATS unavailable"
        )

    try:
        # Feature flag: Use enhanced processing if enabled
        if FF_TV_SLICE:
            feature_flag_evaluations.labels(flag='FF_TV_SLICE', result='enabled').inc()
            return await process_webhook_enhanced(request, body, source, corr_id, idempotency_key)
        else:
            feature_flag_evaluations.labels(flag='FF_TV_SLICE', result='disabled').inc()
            return await process_webhook_legacy(request, body, source, corr_id, idempotency_key)

    except Exception as e:
        logger.error(
            "Webhook processing failed",
            corr_id=corr_id,
            source=source,
            error=str(e)
        )
        raise

async def process_webhook_legacy(
    request: Request,
    body: MarketSignal,
    source: str,
    corr_id: str,
    idempotency_key: Optional[str]
) -> Dict:
    """Legacy webhook processing for backward compatibility"""
    try:
        # Create raw signal event
        raw_signal = {
            "corr_id": corr_id,
            "source": source,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "payload": body.dict()
        }

        # Publish raw signal
        await js_client.publish(
            "signals.raw",
            json.dumps(raw_signal).encode(),
            headers={
                "Corr-ID": corr_id,
                "Source": source
            }
        )

        # Normalize signal (legacy format)
        normalized_signal = {
            "corr_id": corr_id,
            "timestamp": body.timestamp or datetime.now(timezone.utc).isoformat(),
            "instrument": body.instrument.upper(),
            "signal_type": body.signal,
            "strength": body.strength,
            "price": float(body.price),
            "source": source,
            "metadata": body.metadata or {}
        }

        # Publish normalized signal
        await js_client.publish(
            "signals.normalized",
            json.dumps(normalized_signal).encode(),
            headers={
                "Corr-ID": corr_id,
                "Instrument": body.instrument.upper()
            }
        )

        logger.info(
            "Legacy webhook processed",
            corr_id=corr_id,
            source=source,
            instrument=body.instrument,
            signal=body.signal
        )

        webhooks_received.labels(source=source, status="success").inc()

        response = {
            "status": "accepted",
            "corr_id": corr_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "processing_mode": "legacy"
        }

        return response

    except Exception as e:
        normalization_errors.labels(source=source).inc()
        logger.error(
            "Legacy webhook processing failed",
            corr_id=corr_id,
            error=str(e),
            source=source
        )
        raise HTTPException(
            status_code=500,
            detail="GW-009: Legacy processing failed"
        )

async def process_webhook_enhanced(
    request: Request,
    body: MarketSignal,
    source: str,
    corr_id: str,
    idempotency_key: Optional[str]
) -> Dict:
    """Enhanced webhook processing with v1.0 schema validation"""
    processing_start = time.time()

    try:
        # Convert to SignalEventV1 format
        signal_event = create_signal_event_v1(body, source, corr_id)

        # Validate against schema
        try:
            validate_signal_event(signal_event)
            if FF_ENHANCED_LOGGING:
                logger.debug(
                    "Schema validation passed",
                    corr_id=corr_id,
                    schema_version=signal_event["schema_version"]
                )
        except ValidationError as ve:
            schema_validation_errors.labels(
                schema_type='SignalEventV1',
                field=ve.field_name if hasattr(ve, 'field_name') else 'unknown'
            ).inc()
            logger.error(
                "Schema validation failed",
                corr_id=corr_id,
                validation_error=str(ve),
                payload_snippet=str(signal_event)[:200]
            )
            raise HTTPException(
                status_code=400,
                detail=f"GW-012: Schema validation failed: {str(ve)}"
            )

        # Create raw signal event
        raw_signal = {
            "corr_id": corr_id,
            "source": source,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "payload": body.dict(),
            "schema_version": "1.0.0"
        }

        # Publish raw signal
        await js_client.publish(
            "signals.raw",
            json.dumps(raw_signal).encode(),
            headers={
                "Corr-ID": corr_id,
                "Source": source,
                "Schema-Version": "1.0.0"
            }
        )

        # Enhanced subject routing with hierarchy
        signal_type = signal_event["type"]
        priority = signal_event["payload"]["priority"]
        instrument = signal_event["instrument"]

        enhanced_subject = f"signals.normalized.{priority}.{instrument}.{signal_type}"

        # Track categorization metrics
        signal_categorization_total.labels(type=signal_type, priority=priority).inc()

        # Publish enhanced normalized signal
        await js_client.publish(
            enhanced_subject,
            json.dumps(signal_event).encode(),
            headers={
                "Corr-ID": corr_id,
                "Source": source,
                "Instrument": instrument,
                "Signal-Type": signal_type,
                "Priority": priority,
                "Schema-Version": "1.0.0",
                "Nats-Msg-Id": f"{corr_id}_{int(time.time())}"
            }
        )

        processing_duration = time.time() - processing_start
        enhanced_processing_duration.observe(processing_duration)

        logger.info(
            "Enhanced webhook processed",
            corr_id=corr_id,
            source=source,
            instrument=instrument,
            signal_type=signal_type,
            priority=priority,
            subject=enhanced_subject,
            processing_duration_ms=processing_duration * 1000
        )

        webhooks_received.labels(source=source, status="success").inc()

        response = {
            "status": "accepted",
            "corr_id": corr_id,
            "intent_id": signal_event["intent_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "processing_mode": "enhanced",
            "schema_version": "1.0.0",
            "signal_classification": {
                "type": signal_type,
                "priority": priority,
                "subject": enhanced_subject
            }
        }

        return response

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        normalization_errors.labels(source=source).inc()
        enhanced_processing_duration.observe(time.time() - processing_start)
        logger.error(
            "Enhanced webhook processing failed",
            corr_id=corr_id,
            error=str(e),
            source=source
        )

        # Fallback to DLQ if available
        try:
            dlq_payload = {
                "original_payload": body.dict(),
                "error": str(e),
                "corr_id": corr_id,
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "processing_mode": "enhanced"
            }

            await js_client.publish(
                f"dlq.signals.normalized.{source}",
                json.dumps(dlq_payload).encode(),
                headers={"Corr-ID": corr_id, "Error-Type": "processing"}
            )

            logger.info(
                "Failed message sent to DLQ",
                corr_id=corr_id,
                dlq_subject=f"dlq.signals.normalized.{source}"
            )
        except Exception as dlq_error:
            logger.error(
                "Failed to send to DLQ",
                corr_id=corr_id,
                dlq_error=str(dlq_error)
            )

        raise HTTPException(
            status_code=500,
            detail="GW-013: Enhanced processing failed"
        )

        # Handle idempotency caching
        if idempotency_key and 'response' in locals():
            idempotency_cache[idempotency_key] = {
                "corr_id": corr_id,
                "payload_hash": hash(str(body.dict())),
                "response": response,
                "timestamp": time.time()
            }

            # Clean old cache entries
            if len(idempotency_cache) > 1000:
                cutoff = time.time() - 3600
                idempotency_cache.clear()

        return response

    except NatsTimeoutError:
        nats_errors.labels(type="timeout").inc()
        logger.error("NATS publish timeout", corr_id=corr_id)
        raise HTTPException(
            status_code=503,
            detail="GW-005: NATS timeout"
        )

# Health check enhancements for v1.0
@app.get("/healthz/detailed")
async def detailed_health_check():
    """Detailed health check with feature flag status"""
    health_status = {
        "ok": True,
        "service": SERVICE_NAME,
        "version": "1.0.0",
        "uptime_seconds": int(time.time() - start_time),
        "nats_connected": nats_client is not None and nats_client.is_connected,
        "feature_flags": {
            "FF_TV_SLICE": FF_TV_SLICE,
            "FF_ENHANCED_LOGGING": FF_ENHANCED_LOGGING,
            "FF_CIRCUIT_BREAKER": FF_CIRCUIT_BREAKER
        },
        "schema_registry": {
            "available": True,
            "schemas_loaded": ["SignalEventV1", "AgentOutputV1", "OrderIntentV1"]
        }
    }

    if MAINTENANCE_MODE:
        health_status["ok"] = False
        health_status["maintenance"] = True
        return JSONResponse(status_code=503, content=health_status)

    if not health_status["nats_connected"]:
        health_status["ok"] = False
        health_status["error"] = "NATS disconnected"
        return JSONResponse(status_code=503, content=health_status)

    return health_status

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)

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
from .agent_manager import AgentManager
from .context_store import ContextStore
from .mcp_client import MCPClient

# Configure structured logging
logger = structlog.get_logger()

# Environment variables
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
NATS_STREAM = os.getenv("NATS_STREAM", "trading-events")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SERVICE_NAME = os.getenv("SERVICE_NAME", "at-agent-orchestrator")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# AI Service Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Feature flags
FF_AGENT_GPT = os.getenv("FF_AGENT_GPT", "false").lower() == "true"
FF_ENHANCED_LOGGING = os.getenv("FF_ENHANCED_LOGGING", "false").lower() == "true"
FF_CIRCUIT_BREAKER = os.getenv("FF_CIRCUIT_BREAKER", "true").lower() == "true"

# Agent Configuration
AGENT_TIMEOUT_SEC = int(os.getenv("AGENT_TIMEOUT_SEC", "30"))
MAX_CONTEXT_LENGTH = int(os.getenv("MAX_CONTEXT_LENGTH", "8192"))
AGENT_RETRY_ATTEMPTS = int(os.getenv("AGENT_RETRY_ATTEMPTS", "3"))

# Prometheus metrics
agent_requests_total = Counter('orchestrator_agent_requests_total', 'Total agent requests', ['agent_type', 'status'])
agent_response_duration = Histogram('orchestrator_agent_response_seconds', 'Agent response duration', ['agent_type'])
context_operations = Counter('orchestrator_context_operations_total', 'Context store operations', ['operation', 'status'])
mcp_connections = Gauge('orchestrator_mcp_connections', 'Active MCP connections', ['agent_type'])
agent_errors = Counter('orchestrator_agent_errors_total', 'Agent errors', ['agent_type', 'error_type'])
feature_flag_evaluations = Counter('orchestrator_feature_flag_evaluations_total', 'Feature flag evaluations', ['flag', 'result'])

app = FastAPI(
    title="at-agent-orchestrator",
    description="GPT Agent Orchestration Service for Trading Intelligence",
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
agent_manager: Optional[AgentManager] = None
context_store: Optional[ContextStore] = None
mcp_client: Optional[MCPClient] = None
start_time = time.time()

class AgentRequest(BaseModel):
    """Manual agent request via REST API"""
    agent_type: str = Field(..., description="Type of agent to invoke")
    signal_data: Dict[str, Any] = Field(..., description="Signal data for analysis")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracking")
    context_key: Optional[str] = Field(None, description="Context key for persistent conversations")

class AgentResponse(BaseModel):
    """Agent response structure"""
    agent_id: str
    agent_type: str
    correlation_id: str
    status: str
    analysis: Optional[str] = None
    orders: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
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
    global nats_client, js_client, agent_manager, context_store, mcp_client

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

        # Initialize context store
        context_store = ContextStore(REDIS_URL)
        await context_store.initialize()

        # Initialize MCP client
        mcp_client = MCPClient(
            openai_api_key=OPENAI_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY
        )
        await mcp_client.initialize()

        # Initialize agent manager
        agent_manager = AgentManager(
            context_store=context_store,
            mcp_client=mcp_client,
            timeout_sec=AGENT_TIMEOUT_SEC,
            max_context_length=MAX_CONTEXT_LENGTH
        )

        # Subscribe to agent run intents if feature flag enabled
        if FF_AGENT_GPT:
            feature_flag_evaluations.labels(flag='FF_AGENT_GPT', result='enabled').inc()
            await setup_nats_subscriptions()
        else:
            feature_flag_evaluations.labels(flag='FF_AGENT_GPT', result='disabled').inc()
            logger.info("Agent orchestrator in standby mode (FF_AGENT_GPT disabled)")

        logger.info(
            "Agent orchestrator service started",
            nats_url=NATS_URL,
            redis_url=REDIS_URL,
            port=8010,
            service_name=SERVICE_NAME,
            ff_agent_gpt=FF_AGENT_GPT,
            agents_available=len(mcp_client.available_agents) if mcp_client else 0
        )

    except Exception as e:
        logger.error(f"Failed to start agent orchestrator: {e}")
        raise

async def setup_nats_subscriptions():
    """Set up NATS subscriptions for agent run intents"""
    try:
        # Subscribe to agent run intents
        await js_client.subscribe(
            "intents.agent_run.*",
            cb=handle_agent_intent,
            durable="orchestrator-agent-intents",
            manual_ack=True
        )

        logger.info("NATS subscriptions established", subjects=["intents.agent_run.*"])

    except Exception as e:
        logger.error(f"Failed to setup NATS subscriptions: {e}")
        raise

async def handle_agent_intent(msg):
    """Handle incoming agent run intents from NATS"""
    corr_id = msg.headers.get('Corr-ID', f"nats_{uuid.uuid4().hex[:8]}")

    try:
        # Parse message
        intent_data = json.loads(msg.data.decode())

        if FF_ENHANCED_LOGGING:
            logger.debug(
                "Agent intent received",
                corr_id=corr_id,
                subject=msg.subject,
                intent_id=intent_data.get('intent_id'),
                source=intent_data.get('source')
            )

        # Extract agent type from subject
        subject_parts = msg.subject.split('.')
        if len(subject_parts) >= 3:
            agent_type = subject_parts[2]  # intents.agent_run.{agent}
        else:
            agent_type = "default"

        # Process agent request
        response = await process_agent_request(
            agent_type=agent_type,
            signal_data=intent_data,
            correlation_id=corr_id
        )

        # Publish agent output
        await publish_agent_output(response, msg.subject)

        # Acknowledge message
        await msg.ack()

        agent_requests_total.labels(agent_type=agent_type, status='success').inc()

    except Exception as e:
        logger.error(
            "Failed to process agent intent",
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
                headers={"Corr-ID": corr_id, "Error-Type": "agent_processing"}
            )
        except Exception as dlq_error:
            logger.error(f"Failed to send to DLQ: {dlq_error}", corr_id=corr_id)

        await msg.ack()  # Ack to prevent redelivery
        agent_requests_total.labels(agent_type=agent_type, status='error').inc()

async def process_agent_request(
    agent_type: str,
    signal_data: Dict[str, Any],
    correlation_id: str,
    context_key: Optional[str] = None
) -> AgentResponse:
    """Process agent request and generate response"""
    agent_start_time = time.time()

    try:
        if not agent_manager:
            raise HTTPException(status_code=503, detail="Agent manager not initialized")

        # Generate context key if not provided
        if not context_key:
            context_key = f"{agent_type}_{correlation_id}"

        # Run agent
        result = await agent_manager.run_agent(
            agent_type=agent_type,
            signal_data=signal_data,
            context_key=context_key,
            correlation_id=correlation_id
        )

        # Record metrics
        duration = time.time() - agent_start_time
        agent_response_duration.labels(agent_type=agent_type).observe(duration)

        return AgentResponse(
            agent_id=result.get('agent_id', f"{agent_type}_{uuid.uuid4().hex[:8]}"),
            agent_type=agent_type,
            correlation_id=correlation_id,
            status="completed",
            analysis=result.get('analysis'),
            orders=result.get('orders', []),
            confidence=result.get('confidence'),
            reasoning=result.get('reasoning')
        )

    except Exception as e:
        agent_errors.labels(agent_type=agent_type, error_type=type(e).__name__).inc()
        logger.error(
            "Agent processing failed",
            corr_id=correlation_id,
            agent_type=agent_type,
            error=str(e)
        )

        return AgentResponse(
            agent_id=f"error_{uuid.uuid4().hex[:8]}",
            agent_type=agent_type,
            correlation_id=correlation_id,
            status="error",
            error=str(e)
        )

async def publish_agent_output(response: AgentResponse, original_subject: str):
    """Publish agent output to NATS"""
    try:
        # Determine severity based on response
        if response.status == "error":
            severity = "warn"
        elif response.confidence and response.confidence > 0.8:
            severity = "critical"  # High confidence decisions
        else:
            severity = "info"

        # Create AgentOutputV1 payload
        agent_output = {
            "schema_version": "1.0.0",
            "agent_id": response.agent_id,
            "correlation_id": response.correlation_id,
            "agent_type": response.agent_type,
            "analysis": response.analysis or "",
            "confidence": response.confidence or 0.0,
            "reasoning": response.reasoning or "",
            "orders": response.orders or [],
            "metadata": {
                "original_subject": original_subject,
                "processing_status": response.status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "ts_iso": datetime.now(timezone.utc).isoformat()
        }

        # Validate against schema
        try:
            validate_agent_output(agent_output)
        except ValidationError as ve:
            logger.error(
                "Agent output schema validation failed",
                corr_id=response.correlation_id,
                validation_error=str(ve)
            )
            # Continue publishing despite validation error for observability
            severity = "warn"

        # Publish to decisions subject
        subject = f"decisions.agent_output.{response.agent_type}.{severity}"

        await js_client.publish(
            subject,
            json.dumps(agent_output).encode(),
            headers={
                "Corr-ID": response.correlation_id,
                "Agent-Type": response.agent_type,
                "Agent-ID": response.agent_id,
                "Confidence": str(response.confidence or 0.0),
                "Schema-Version": "1.0.0"
            }
        )

        # Log audit event
        await js_client.publish(
            "audit.events",
            json.dumps({
                "event_type": "agent_output",
                "agent_type": response.agent_type,
                "correlation_id": response.correlation_id,
                "confidence": response.confidence,
                "status": response.status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }).encode(),
            headers={"Corr-ID": response.correlation_id}
        )

        if FF_ENHANCED_LOGGING:
            logger.info(
                "Agent output published",
                corr_id=response.correlation_id,
                subject=subject,
                agent_type=response.agent_type,
                confidence=response.confidence,
                orders_count=len(response.orders or [])
            )

    except Exception as e:
        logger.error(
            "Failed to publish agent output",
            corr_id=response.correlation_id,
            error=str(e)
        )

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "ok": True,
        "service": SERVICE_NAME,
        "version": "1.0.0",
        "uptime_seconds": int(time.time() - start_time),
        "nats_connected": nats_client is not None and nats_client.is_connected,
        "context_store_connected": context_store is not None and await context_store.health_check(),
        "agents_available": len(mcp_client.available_agents) if mcp_client else 0
    }

    if not health_status["nats_connected"]:
        health_status["ok"] = False
        health_status["error"] = "NATS disconnected"
        return JSONResponse(status_code=503, content=health_status)

    if not health_status["context_store_connected"]:
        health_status["ok"] = False
        health_status["error"] = "Context store disconnected"
        return JSONResponse(status_code=503, content=health_status)

    return health_status

@app.get("/healthz/detailed")
async def detailed_health_check():
    """Detailed health check with component status"""
    health_status = await health_check()

    if isinstance(health_status, JSONResponse):
        return health_status

    health_status.update({
        "feature_flags": {
            "FF_AGENT_GPT": FF_AGENT_GPT,
            "FF_ENHANCED_LOGGING": FF_ENHANCED_LOGGING,
            "FF_CIRCUIT_BREAKER": FF_CIRCUIT_BREAKER
        },
        "configuration": {
            "agent_timeout_sec": AGENT_TIMEOUT_SEC,
            "max_context_length": MAX_CONTEXT_LENGTH,
            "retry_attempts": AGENT_RETRY_ATTEMPTS
        },
        "available_agents": list(mcp_client.available_agents.keys()) if mcp_client else []
    })

    return health_status

@app.post("/agent/run")
async def run_agent_manual(request: Request, agent_request: AgentRequest):
    """Manual agent execution via REST API"""
    corr_id = request.state.corr_id

    if not FF_AGENT_GPT:
        feature_flag_evaluations.labels(flag='FF_AGENT_GPT', result='disabled').inc()
        raise HTTPException(
            status_code=503,
            detail="Agent orchestration disabled (FF_AGENT_GPT=false)"
        )

    feature_flag_evaluations.labels(flag='FF_AGENT_GPT', result='enabled').inc()

    # Use provided correlation ID or generate from request
    correlation_id = agent_request.correlation_id or corr_id

    response = await process_agent_request(
        agent_type=agent_request.agent_type,
        signal_data=agent_request.signal_data,
        correlation_id=correlation_id,
        context_key=agent_request.context_key
    )

    return response.dict()

@app.get("/agents")
async def list_agents():
    """List available agents"""
    if not mcp_client:
        return {"agents": []}

    return {
        "agents": list(mcp_client.available_agents.keys()),
        "total_count": len(mcp_client.available_agents),
        "feature_flag_enabled": FF_AGENT_GPT
    }

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
    global nats_client, context_store, mcp_client

    if context_store:
        await context_store.cleanup()

    if mcp_client:
        await mcp_client.cleanup()

    if nats_client:
        await nats_client.close()

    logger.info("Agent orchestrator service stopped")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8010))
    uvicorn.run(app, host="0.0.0.0", port=port)
import asyncio
import json
import logging
import os
import time
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from .nats_client import NATSClient
from .simulator import ExecutionSimulator

logger = structlog.get_logger()

app = FastAPI(
    title="at-exec-sim",
    description="Execution Simulator Service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=3600,
)

@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    if request.headers.get("content-length"):
        content_length = int(request.headers["content-length"])
        if content_length > 1024 * 1024:  # 1MB limit
            return JSONResponse(
                status_code=413,
                content={"error": "Request entity too large", "max_size": "1MB"}
            )

    response = await call_next(request)
    return response

# Global state
start_time = time.time()
nats_client: NATSClient = None
simulator: ExecutionSimulator = None

# Prometheus metrics
orders_received = Counter('exec_sim_orders_received_total', 'Total order intents received', ['status'])
fills_generated = Counter('exec_sim_fills_generated_total', 'Total fills generated', ['fill_type', 'instrument'])
simulation_duration = Histogram('exec_sim_simulation_duration_seconds', 'Simulation processing duration', ['instrument', 'order_type'])
validation_errors = Counter('exec_sim_validation_errors_total', 'Schema validation errors', ['type'])
nats_publish_errors = Counter('exec_sim_nats_publish_errors_total', 'NATS publishing errors', ['subject'])
pending_events = Gauge('exec_sim_pending_events_count', 'Number of pending events in buffer')
fetch_calls = Counter('exec_sim_fetch_calls_total', 'Total fetch calls made')
fetch_empty = Counter('exec_sim_fetch_empty_total', 'Total empty fetch results')
unknown_fields = Counter('exec_sim_unknown_fields_total', 'Total unknown fields in order data', ['field_name'])

@app.on_event("startup")
async def startup_event():
    global nats_client, simulator

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

    # Initialize NATS client and simulator
    nats_client = NATSClient()
    simulator = ExecutionSimulator(orders_received=orders_received, fills_generated=fills_generated)
    simulator.fetch_calls = fetch_calls
    simulator.fetch_empty = fetch_empty
    simulator.unknown_fields = unknown_fields

    # Start NATS consumer
    try:
        await nats_client.connect()
        await nats_client.start_consumer(simulator)

        # Verify consumer binding
        info = await nats_client.js.consumer_info("trading-events", nats_client.durable_name)
        logger.info("NATS consumer started successfully",
                   consumer_bound=True,
                   filter_subject=info.config.filter_subject,
                   durable_name=info.name,
                   num_pending=info.num_pending,
                   num_delivered=info.delivered.consumer_seq)

    except Exception as e:
        logger.error("Failed to start NATS consumer", error=str(e))
        raise

    logger.info("at-exec-sim service started", port=8004, service_name=os.getenv("SERVICE_NAME", "at-exec-sim"))

@app.on_event("shutdown")
async def shutdown_event():
    global nats_client
    if nats_client:
        await nats_client.disconnect()
    logger.info("at-exec-sim service stopped")

@app.get("/healthz")
async def health_check():
    global nats_client, start_time

    uptime = int(time.time() - start_time)

    if not nats_client:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "uptime_s": uptime,
                "nats": "disconnected",
                "version": "1.0.0",
                "processor_status": "stopped",
                "pending_events": 0,
                "error": "NATS client not initialized"
            }
        )

    nats_status = await nats_client.get_status()
    consumer_health = await nats_client.check_consumer_health()
    pending_count = await nats_client.get_pending_count()

    # Determine overall health
    processor_status = "active"
    if nats_status != "connected":
        processor_status = "stopped" if nats_status == "disconnected" else "degraded"
    elif consumer_health["status"] == "degraded":
        processor_status = "degraded"

    is_healthy = nats_status == "connected" and consumer_health["status"] == "healthy"
    status_code = 200 if is_healthy else 503

    # Update Prometheus metrics
    pending_events.set(pending_count)

    health_response = {
        "ok": is_healthy,
        "uptime_s": uptime,
        "nats": nats_status,
        "version": "1.0.0",
        "processor_status": processor_status,
        "pending_events": pending_count,
        "consumer": consumer_health
    }

    # Add failure details if not healthy
    if not is_healthy:
        if nats_status == "failed":
            health_response["error"] = "NATS connection failed after retries"
        elif nats_status == "disconnected":
            health_response["error"] = "NATS not connected"
        elif consumer_health["status"] == "degraded":
            health_response["error"] = f"Consumer degraded: {consumer_health.get('error', 'unknown')}"
        elif processor_status != "active":
            health_response["error"] = f"Processor status: {processor_status}"

    return JSONResponse(status_code=status_code, content=health_response)

@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8004))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

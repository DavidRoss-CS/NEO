#!/usr/bin/env python3
"""
Chaos Testing Runner for Agentic Trading System

This service provides chaos engineering capabilities including:
- NATS latency injection
- Service failure simulation
- Network partition tests
- Backpressure scenarios
- Load testing with duplicate messages
"""

import asyncio
import logging
import os
import signal
import time
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import uvicorn

from .chaos_tests import (
    NATSLatencyInjector,
    ServiceFailureSimulator,
    NetworkPartitionTester,
    BackpressureGenerator,
    LoadTester,
    DuplicateMessageGenerator
)

# Environment configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
CHAOS_MODE = os.getenv("CHAOS_MODE", "safe")  # safe, aggressive, destructive
PORT = int(os.getenv("PORT", "8008"))
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Prometheus metrics
chaos_tests_executed = Counter('chaos_tests_executed_total', 'Total chaos tests executed', ['test_type', 'status'])
chaos_test_duration = Histogram('chaos_test_duration_seconds', 'Chaos test execution duration', ['test_type'])
active_chaos_experiments = Gauge('chaos_active_experiments', 'Number of active chaos experiments')
system_recovery_time = Histogram('chaos_system_recovery_seconds', 'Time for system to recover from chaos', ['test_type'])
failures_injected = Counter('chaos_failures_injected_total', 'Total failures injected', ['failure_type'])

app = FastAPI(
    title="Chaos Testing Framework",
    description="Chaos engineering for agentic trading system",
    version="1.0.0"
)

# Global state
start_time = time.time()
active_experiments: Dict[str, Any] = {}
chaos_components = {}

class ChaosOrchestrator:
    """Orchestrates chaos experiments across the trading system"""

    def __init__(self):
        self.experiments = {}
        self.nats_injector = None
        self.service_simulator = None
        self.network_tester = None
        self.backpressure_gen = None
        self.load_tester = None
        self.duplicate_gen = None

    async def initialize(self):
        """Initialize chaos testing components"""
        try:
            self.nats_injector = NATSLatencyInjector(NATS_URL)
            self.service_simulator = ServiceFailureSimulator()
            self.network_tester = NetworkPartitionTester()
            self.backpressure_gen = BackpressureGenerator(NATS_URL)
            self.load_tester = LoadTester()
            self.duplicate_gen = DuplicateMessageGenerator(NATS_URL)

            # Initialize connections
            await self.nats_injector.connect()
            await self.backpressure_gen.connect()
            await self.duplicate_gen.connect()

            logger.info("Chaos orchestrator initialized", mode=CHAOS_MODE)

        except Exception as e:
            logger.error("Failed to initialize chaos orchestrator", error=str(e))
            raise

    async def shutdown(self):
        """Clean shutdown of chaos components"""
        try:
            # Stop all active experiments
            for exp_id in list(self.experiments.keys()):
                await self.stop_experiment(exp_id)

            # Disconnect components
            if self.nats_injector:
                await self.nats_injector.disconnect()
            if self.backpressure_gen:
                await self.backpressure_gen.disconnect()
            if self.duplicate_gen:
                await self.duplicate_gen.disconnect()

            logger.info("Chaos orchestrator shutdown complete")

        except Exception as e:
            logger.error("Error during chaos orchestrator shutdown", error=str(e))

    async def start_experiment(self, experiment_config: Dict[str, Any]) -> str:
        """Start a chaos experiment"""
        exp_id = f"chaos_{int(time.time())}_{experiment_config['type']}"
        exp_type = experiment_config['type']

        try:
            # Validate chaos mode
            if CHAOS_MODE == "safe" and exp_type in ["destructive_failure", "network_partition"]:
                raise HTTPException(400, f"Experiment type {exp_type} not allowed in safe mode")

            logger.info("Starting chaos experiment",
                       experiment_id=exp_id,
                       type=exp_type,
                       config=experiment_config)

            # Start timer
            start_time = time.time()

            # Execute based on experiment type
            if exp_type == "nats_latency":
                task = asyncio.create_task(
                    self.nats_injector.inject_latency(
                        delay_ms=experiment_config.get('delay_ms', 100),
                        duration_s=experiment_config.get('duration_s', 60)
                    )
                )
            elif exp_type == "service_failure":
                task = asyncio.create_task(
                    self.service_simulator.simulate_failure(
                        service=experiment_config.get('service', 'agent'),
                        failure_type=experiment_config.get('failure_type', 'crash'),
                        duration_s=experiment_config.get('duration_s', 30)
                    )
                )
            elif exp_type == "backpressure":
                task = asyncio.create_task(
                    self.backpressure_gen.generate_backpressure(
                        rate_multiplier=experiment_config.get('rate_multiplier', 10),
                        duration_s=experiment_config.get('duration_s', 60)
                    )
                )
            elif exp_type == "load_test":
                task = asyncio.create_task(
                    self.load_tester.run_load_test(
                        rps=experiment_config.get('rps', 100),
                        duration_s=experiment_config.get('duration_s', 120),
                        payload_size=experiment_config.get('payload_size', 1024)
                    )
                )
            elif exp_type == "duplicate_messages":
                task = asyncio.create_task(
                    self.duplicate_gen.generate_duplicates(
                        duplicate_rate=experiment_config.get('duplicate_rate', 0.1),
                        duration_s=experiment_config.get('duration_s', 60)
                    )
                )
            else:
                raise HTTPException(400, f"Unknown experiment type: {exp_type}")

            # Store experiment
            self.experiments[exp_id] = {
                'task': task,
                'type': exp_type,
                'config': experiment_config,
                'start_time': start_time,
                'status': 'running'
            }

            # Update metrics
            active_chaos_experiments.inc()

            # Set up completion callback
            task.add_done_callback(lambda t: self._experiment_completed(exp_id, t))

            return exp_id

        except Exception as e:
            chaos_tests_executed.labels(test_type=exp_type, status='failed').inc()
            logger.error("Failed to start chaos experiment",
                        experiment_id=exp_id,
                        error=str(e))
            raise

    async def stop_experiment(self, exp_id: str):
        """Stop a running chaos experiment"""
        if exp_id not in self.experiments:
            raise HTTPException(404, f"Experiment {exp_id} not found")

        experiment = self.experiments[exp_id]

        try:
            # Cancel the task
            experiment['task'].cancel()

            try:
                await experiment['task']
            except asyncio.CancelledError:
                pass

            # Update status
            experiment['status'] = 'stopped'

            # Update metrics
            duration = time.time() - experiment['start_time']
            chaos_test_duration.labels(test_type=experiment['type']).observe(duration)
            chaos_tests_executed.labels(test_type=experiment['type'], status='stopped').inc()
            active_chaos_experiments.dec()

            logger.info("Chaos experiment stopped",
                       experiment_id=exp_id,
                       duration=duration)

        except Exception as e:
            logger.error("Error stopping chaos experiment",
                        experiment_id=exp_id,
                        error=str(e))
            raise

    def _experiment_completed(self, exp_id: str, task: asyncio.Task):
        """Callback when experiment completes"""
        if exp_id not in self.experiments:
            return

        experiment = self.experiments[exp_id]
        duration = time.time() - experiment['start_time']

        try:
            # Check if task completed successfully or was cancelled
            if task.cancelled():
                status = 'cancelled'
            elif task.exception():
                status = 'failed'
                logger.error("Chaos experiment failed",
                           experiment_id=exp_id,
                           error=str(task.exception()))
            else:
                status = 'completed'
                logger.info("Chaos experiment completed",
                           experiment_id=exp_id,
                           duration=duration)

            # Update metrics
            chaos_test_duration.labels(test_type=experiment['type']).observe(duration)
            chaos_tests_executed.labels(test_type=experiment['type'], status=status).inc()
            active_chaos_experiments.dec()

            # Update experiment status
            experiment['status'] = status
            experiment['end_time'] = time.time()

        except Exception as e:
            logger.error("Error in experiment completion callback",
                        experiment_id=exp_id,
                        error=str(e))

# Global orchestrator
orchestrator = ChaosOrchestrator()

@app.on_event("startup")
async def startup_event():
    """Initialize chaos testing framework"""
    global orchestrator
    await orchestrator.initialize()
    logger.info("Chaos testing framework started", port=PORT, mode=CHAOS_MODE)

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    global orchestrator
    await orchestrator.shutdown()
    logger.info("Chaos testing framework stopped")

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    uptime = int(time.time() - start_time)

    health_status = {
        "ok": True,
        "service": "chaos-tests",
        "uptime_seconds": uptime,
        "chaos_mode": CHAOS_MODE,
        "active_experiments": len(orchestrator.experiments),
        "nats_connected": orchestrator.nats_injector and orchestrator.nats_injector.connected
    }

    return health_status

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/experiments")
async def start_experiment(experiment_config: Dict[str, Any]):
    """Start a new chaos experiment"""
    exp_id = await orchestrator.start_experiment(experiment_config)
    return {"experiment_id": exp_id, "status": "started"}

@app.delete("/experiments/{exp_id}")
async def stop_experiment(exp_id: str):
    """Stop a running chaos experiment"""
    await orchestrator.stop_experiment(exp_id)
    return {"experiment_id": exp_id, "status": "stopped"}

@app.get("/experiments")
async def list_experiments():
    """List all experiments"""
    experiments = []
    for exp_id, exp_data in orchestrator.experiments.items():
        experiments.append({
            "experiment_id": exp_id,
            "type": exp_data['type'],
            "status": exp_data['status'],
            "start_time": exp_data['start_time'],
            "config": exp_data['config']
        })
    return {"experiments": experiments}

@app.get("/experiments/{exp_id}")
async def get_experiment(exp_id: str):
    """Get experiment details"""
    if exp_id not in orchestrator.experiments:
        raise HTTPException(404, f"Experiment {exp_id} not found")

    exp_data = orchestrator.experiments[exp_id]
    return {
        "experiment_id": exp_id,
        "type": exp_data['type'],
        "status": exp_data['status'],
        "start_time": exp_data['start_time'],
        "config": exp_data['config'],
        "duration": time.time() - exp_data['start_time'] if exp_data['status'] == 'running' else None
    }

# Predefined experiment templates
@app.get("/templates")
async def get_experiment_templates():
    """Get predefined chaos experiment templates"""
    templates = {
        "nats_latency_mild": {
            "type": "nats_latency",
            "delay_ms": 50,
            "duration_s": 60,
            "description": "Mild NATS latency injection (50ms)"
        },
        "nats_latency_severe": {
            "type": "nats_latency",
            "delay_ms": 500,
            "duration_s": 120,
            "description": "Severe NATS latency injection (500ms)"
        },
        "agent_crash": {
            "type": "service_failure",
            "service": "agent",
            "failure_type": "crash",
            "duration_s": 30,
            "description": "Simulate agent service crash for 30s"
        },
        "backpressure_10x": {
            "type": "backpressure",
            "rate_multiplier": 10,
            "duration_s": 120,
            "description": "Generate 10x normal message rate"
        },
        "load_test_100rps": {
            "type": "load_test",
            "rps": 100,
            "duration_s": 300,
            "payload_size": 2048,
            "description": "Load test at 100 RPS for 5 minutes"
        },
        "duplicate_messages_10pct": {
            "type": "duplicate_messages",
            "duplicate_rate": 0.1,
            "duration_s": 180,
            "description": "Inject 10% duplicate messages"
        }
    }
    return templates

if __name__ == "__main__":
    uvicorn.run(
        "chaos_runner:app",
        host="0.0.0.0",
        port=PORT,
        log_level=LOG_LEVEL.lower()
    )
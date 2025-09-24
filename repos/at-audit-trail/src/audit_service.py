#!/usr/bin/env python3
"""
Audit Trail Service for Agentic Trading System

Provides immutable audit logging with hash chain validation for:
- All trading decisions and rationale
- Signal flow tracking
- Execution reconciliation
- Compliance reporting
"""

import asyncio
import json
import os
import time
import hashlib
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import nats
from nats.js import JetStreamContext
import uvicorn

# Environment configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PORT = int(os.getenv("PORT", "8009"))
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
NATS_STREAM = os.getenv("NATS_STREAM", "trading-events")
AUDIT_STORAGE_PATH = os.getenv("AUDIT_STORAGE_PATH", "/app/audit_logs")
DB_PATH = os.path.join(AUDIT_STORAGE_PATH, "audit.db")

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
audit_events_recorded = Counter('audit_events_recorded_total', 'Total audit events recorded', ['event_type'])
audit_hash_validations = Counter('audit_hash_validations_total', 'Hash chain validations performed', ['status'])
audit_storage_size = Gauge('audit_storage_size_bytes', 'Size of audit database')
audit_query_latency = Histogram('audit_query_duration_seconds', 'Audit query latency')
compliance_reports_generated = Counter('audit_compliance_reports_total', 'Compliance reports generated', ['report_type'])

app = FastAPI(
    title="Audit Trail Service",
    description="Immutable audit logging for trading decisions",
    version="1.0.0"
)

# Global state
start_time = time.time()
nats_client = None
js_client = None
audit_db = None

class AuditEvent(BaseModel):
    """Audit event model"""
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    event_type: str
    timestamp: str
    correlation_id: Optional[str] = None
    service: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = {}
    previous_hash: Optional[str] = None
    event_hash: Optional[str] = None

class AuditDatabase:
    """SQLite-based audit storage with hash chaining"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.initialize_database()

    def initialize_database(self):
        """Create audit database and tables"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Create audit events table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                correlation_id TEXT,
                service TEXT NOT NULL,
                data TEXT NOT NULL,
                metadata TEXT,
                previous_hash TEXT,
                event_hash TEXT NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(event_hash)
            )
        """)

        # Create indexes for efficient queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_correlation_id
            ON audit_events(correlation_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON audit_events(timestamp)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_type
            ON audit_events(event_type)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_service
            ON audit_events(service)
        """)

        # Create compliance views
        self.conn.execute("""
            CREATE VIEW IF NOT EXISTS decision_audit AS
            SELECT * FROM audit_events
            WHERE event_type IN ('decision', 'order_intent', 'risk_check')
        """)

        self.conn.commit()
        logger.info("Audit database initialized", path=self.db_path)

    def get_last_hash(self) -> Optional[str]:
        """Get the hash of the last event in the chain"""
        cursor = self.conn.execute("""
            SELECT event_hash FROM audit_events
            ORDER BY created_at DESC LIMIT 1
        """)
        result = cursor.fetchone()
        return result[0] if result else None

    def calculate_event_hash(self, event: AuditEvent, previous_hash: Optional[str]) -> str:
        """Calculate hash for an event"""
        # Create deterministic string representation
        hash_input = json.dumps({
            'event_id': event.event_id,
            'event_type': event.event_type,
            'timestamp': event.timestamp,
            'correlation_id': event.correlation_id,
            'service': event.service,
            'data': event.data,
            'metadata': event.metadata,
            'previous_hash': previous_hash or 'GENESIS'
        }, sort_keys=True)

        # Calculate SHA-256 hash
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def record_event(self, event: AuditEvent) -> str:
        """Record an audit event with hash chaining"""
        try:
            # Get previous hash for chaining
            previous_hash = self.get_last_hash()
            event.previous_hash = previous_hash

            # Calculate event hash
            event_hash = self.calculate_event_hash(event, previous_hash)
            event.event_hash = event_hash

            # Store in database
            self.conn.execute("""
                INSERT INTO audit_events
                (event_id, event_type, timestamp, correlation_id, service,
                 data, metadata, previous_hash, event_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.event_type,
                event.timestamp,
                event.correlation_id,
                event.service,
                json.dumps(event.data),
                json.dumps(event.metadata) if event.metadata else None,
                previous_hash,
                event_hash,
                time.time()
            ))
            self.conn.commit()

            # Update metrics
            audit_events_recorded.labels(event_type=event.event_type).inc()

            logger.info("Audit event recorded",
                       event_id=event.event_id,
                       event_type=event.event_type,
                       correlation_id=event.correlation_id,
                       hash=event_hash[:8])

            return event_hash

        except sqlite3.IntegrityError as e:
            logger.error("Duplicate event hash detected", error=str(e))
            raise HTTPException(409, "Duplicate event detected")
        except Exception as e:
            logger.error("Failed to record audit event", error=str(e))
            raise

    def validate_chain(self, limit: int = 100) -> bool:
        """Validate the hash chain integrity"""
        try:
            cursor = self.conn.execute("""
                SELECT event_id, event_type, timestamp, correlation_id,
                       service, data, metadata, previous_hash, event_hash
                FROM audit_events
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            events = cursor.fetchall()
            if not events:
                return True

            # Check each event's hash
            for i, row in enumerate(events):
                event = AuditEvent(
                    event_id=row[0],
                    event_type=row[1],
                    timestamp=row[2],
                    correlation_id=row[3],
                    service=row[4],
                    data=json.loads(row[5]),
                    metadata=json.loads(row[6]) if row[6] else {},
                    previous_hash=row[7],
                    event_hash=row[8]
                )

                # Calculate expected hash
                expected_hash = self.calculate_event_hash(event, event.previous_hash)

                if expected_hash != event.event_hash:
                    logger.error("Hash chain validation failed",
                               event_id=event.event_id,
                               expected=expected_hash,
                               actual=event.event_hash)
                    audit_hash_validations.labels(status='failed').inc()
                    return False

                # Check chain continuity
                if i < len(events) - 1:
                    next_event = events[i + 1]
                    if next_event[8] != event.previous_hash:
                        logger.error("Hash chain broken",
                                   event_id=event.event_id,
                                   expected_prev=next_event[8],
                                   actual_prev=event.previous_hash)
                        audit_hash_validations.labels(status='failed').inc()
                        return False

            audit_hash_validations.labels(status='success').inc()
            return True

        except Exception as e:
            logger.error("Hash chain validation error", error=str(e))
            audit_hash_validations.labels(status='error').inc()
            return False

    def query_events(self,
                    correlation_id: Optional[str] = None,
                    event_type: Optional[str] = None,
                    service: Optional[str] = None,
                    start_time: Optional[str] = None,
                    end_time: Optional[str] = None,
                    limit: int = 100) -> List[Dict]:
        """Query audit events with filters"""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params = []

        if correlation_id:
            query += " AND correlation_id = ?"
            params.append(correlation_id)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        if service:
            query += " AND service = ?"
            params.append(service)

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        columns = [desc[0] for desc in cursor.description]

        events = []
        for row in cursor.fetchall():
            event = dict(zip(columns, row))
            # Parse JSON fields
            event['data'] = json.loads(event['data'])
            if event['metadata']:
                event['metadata'] = json.loads(event['metadata'])
            events.append(event)

        return events

    def generate_compliance_report(self,
                                  report_type: str,
                                  start_date: str,
                                  end_date: str) -> Dict[str, Any]:
        """Generate compliance reports"""
        report = {
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'data': {}
        }

        if report_type == 'decision_audit':
            # Get all trading decisions in period
            cursor = self.conn.execute("""
                SELECT COUNT(*) as total_decisions,
                       COUNT(DISTINCT correlation_id) as unique_flows,
                       COUNT(DISTINCT json_extract(data, '$.instrument')) as instruments_traded,
                       AVG(json_extract(data, '$.confidence')) as avg_confidence
                FROM audit_events
                WHERE event_type IN ('decision', 'order_intent')
                AND timestamp BETWEEN ? AND ?
            """, (start_date, end_date))

            result = cursor.fetchone()
            report['data'] = {
                'total_decisions': result[0],
                'unique_flows': result[1],
                'instruments_traded': result[2],
                'average_confidence': result[3]
            }

        elif report_type == 'risk_violations':
            # Get risk violations
            cursor = self.conn.execute("""
                SELECT * FROM audit_events
                WHERE event_type = 'risk_violation'
                AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """, (start_date, end_date))

            violations = []
            for row in cursor.fetchall():
                violations.append({
                    'timestamp': row[2],
                    'correlation_id': row[3],
                    'data': json.loads(row[5])
                })

            report['data'] = {
                'total_violations': len(violations),
                'violations': violations
            }

        compliance_reports_generated.labels(report_type=report_type).inc()
        return report

# Global audit database
audit_db = AuditDatabase(DB_PATH)

async def process_nats_message(msg):
    """Process incoming NATS message for audit logging"""
    try:
        # Parse message
        data = json.loads(msg.data.decode())

        # Extract metadata
        correlation_id = data.get('correlation_id') or data.get('corr_id')
        service = msg.subject.split('.')[0]  # Extract service from subject

        # Create audit event
        event = AuditEvent(
            event_type=msg.subject,
            timestamp=data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            correlation_id=correlation_id,
            service=service,
            data=data,
            metadata={
                'subject': msg.subject,
                'stream': NATS_STREAM,
                'headers': dict(msg.headers) if msg.headers else {}
            }
        )

        # Record in audit trail
        audit_db.record_event(event)

        # Acknowledge message
        await msg.ack()

    except Exception as e:
        logger.error("Error processing NATS message for audit",
                    subject=msg.subject,
                    error=str(e))

@app.on_event("startup")
async def startup_event():
    """Initialize audit service"""
    global nats_client, js_client

    try:
        # Connect to NATS
        nats_client = await nats.connect(NATS_URL)
        js_client = nats_client.jetstream()

        # Subscribe to all trading events for audit
        await js_client.subscribe(
            "",  # Subscribe to all subjects in stream
            stream=NATS_STREAM,
            durable="audit-all",
            manual_ack=True,
            cb=process_nats_message
        )

        logger.info("Audit trail service started",
                   port=PORT,
                   nats_url=NATS_URL,
                   db_path=DB_PATH)

    except Exception as e:
        logger.error("Failed to start audit service", error=str(e))
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    global nats_client

    if nats_client:
        await nats_client.close()

    if audit_db:
        audit_db.conn.close()

    logger.info("Audit trail service stopped")

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    uptime = int(time.time() - start_time)
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

    audit_storage_size.set(db_size)

    # Validate chain integrity
    chain_valid = audit_db.validate_chain(limit=10)

    health_status = {
        "ok": chain_valid and nats_client and nats_client.is_connected,
        "service": "audit-trail",
        "uptime_seconds": uptime,
        "nats_connected": nats_client is not None and nats_client.is_connected,
        "chain_valid": chain_valid,
        "db_size_bytes": db_size
    }

    status_code = 200 if health_status["ok"] else 503
    return JSONResponse(status_code=status_code, content=health_status)

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/audit")
async def record_audit_event(event: AuditEvent):
    """Manually record an audit event"""
    try:
        event_hash = audit_db.record_event(event)
        return {
            "status": "recorded",
            "event_id": event.event_id,
            "event_hash": event_hash
        }
    except Exception as e:
        logger.error("Failed to record audit event", error=str(e))
        raise HTTPException(500, f"Failed to record event: {str(e)}")

@app.get("/audit/query")
async def query_audit_events(
    correlation_id: Optional[str] = Query(None, description="Correlation ID to filter by"),
    event_type: Optional[str] = Query(None, description="Event type to filter by"),
    service: Optional[str] = Query(None, description="Service to filter by"),
    start_time: Optional[str] = Query(None, description="Start timestamp (ISO format)"),
    end_time: Optional[str] = Query(None, description="End timestamp (ISO format)"),
    limit: int = Query(100, description="Maximum number of events to return")
):
    """Query audit events with filters"""
    with audit_query_latency.time():
        events = audit_db.query_events(
            correlation_id=correlation_id,
            event_type=event_type,
            service=service,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

    return {
        "count": len(events),
        "events": events
    }

@app.get("/audit/validate")
async def validate_chain(limit: int = Query(100, description="Number of recent events to validate")):
    """Validate hash chain integrity"""
    is_valid = audit_db.validate_chain(limit=limit)

    return {
        "valid": is_valid,
        "events_checked": limit,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/audit/flow/{correlation_id}")
async def get_audit_flow(correlation_id: str):
    """Get complete audit trail for a correlation ID"""
    events = audit_db.query_events(correlation_id=correlation_id, limit=1000)

    if not events:
        raise HTTPException(404, f"No events found for correlation_id: {correlation_id}")

    # Sort by timestamp to show flow
    events.sort(key=lambda x: x['timestamp'])

    return {
        "correlation_id": correlation_id,
        "event_count": len(events),
        "start_time": events[0]['timestamp'] if events else None,
        "end_time": events[-1]['timestamp'] if events else None,
        "services_involved": list(set(e['service'] for e in events)),
        "events": events
    }

@app.post("/audit/compliance/report")
async def generate_compliance_report(
    report_type: str = Query(..., description="Type of report (decision_audit, risk_violations)"),
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)")
):
    """Generate compliance reports"""
    try:
        report = audit_db.generate_compliance_report(report_type, start_date, end_date)
        return report
    except Exception as e:
        logger.error("Failed to generate compliance report", error=str(e))
        raise HTTPException(500, f"Failed to generate report: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "audit_service:app",
        host="0.0.0.0",
        port=PORT,
        log_level=LOG_LEVEL.lower()
    )
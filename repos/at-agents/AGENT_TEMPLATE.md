# Agent Template

**Standard skeleton for building new trading agents.**

## Overview

This template provides the canonical structure for creating new trading agents. All agents should follow this pattern to ensure consistency, maintainability, and proper integration with the agentic trading architecture.

## Agent Structure

### Directory Layout
```
agents/[agent-name]/
├── README.md              # Agent-specific documentation
├── agent.py               # Main agent implementation
├── config.py              # Configuration management
├── handler.py             # Message processing logic
├── schemas.py             # Agent-specific schemas
├── metrics.py             # Agent-specific metrics
└── tests/                 # Agent unit tests
    ├── test_handler.py    # Handler logic tests
    ├── test_config.py     # Configuration tests
    └── fixtures/          # Test data
```

### Required Components

1. **Configuration Management** (`config.py`)
2. **NATS Connection & Subscription** (`agent.py`)
3. **Message Handler** (`handler.py`)
4. **Schema Validation** (`schemas.py`)
5. **Metrics Collection** (`metrics.py`)
6. **Error Handling & Logging**
7. **Health Checks**

## Template Implementation

### 1. Configuration (`config.py`)

```python
import os
from dataclasses import dataclass
from typing import List

@dataclass
class AgentConfig:
    """Agent configuration from environment variables."""
    
    # NATS Configuration
    nats_url: str = os.getenv('NATS_URL', 'nats://localhost:4222')
    nats_stream: str = os.getenv('NATS_STREAM', 'trading-events')
    nats_durable: str = os.getenv('NATS_DURABLE', 'agent-consumer')
    nats_max_inflight: int = int(os.getenv('NATS_MAX_INFLIGHT', '10'))
    
    # Agent Configuration
    agent_name: str = os.getenv('AGENT_NAME', 'template-agent')
    agent_version: str = os.getenv('AGENT_VERSION', '1.0.0')
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # Subscription Configuration
    input_subjects: List[str] = None
    output_subject: str = None
    
    # Agent-Specific Configuration
    # Add agent-specific config here
    
    def __post_init__(self):
        if self.input_subjects is None:
            self.input_subjects = ['signals.normalized']
        if self.output_subject is None:
            self.output_subject = f'signals.enriched.{self.agent_name}'

def load_config() -> AgentConfig:
    """Load configuration with validation."""
    config = AgentConfig()
    
    # Validate required configuration
    if not config.nats_url:
        raise ValueError("NATS_URL is required")
    
    return config
```

### 2. Main Agent (`agent.py`)

```python
import asyncio
import signal
import sys
from typing import Optional

import nats
from nats.aio.client import Client as NATS
from nats.js.api import ConsumerConfig, DeliverPolicy
import structlog

from .config import load_config
from .handler import MessageHandler
from .metrics import AgentMetrics

class TradingAgent:
    """Base trading agent implementation."""
    
    def __init__(self):
        self.config = load_config()
        self.logger = structlog.get_logger(agent=self.config.agent_name)
        self.nats: Optional[NATS] = None
        self.jetstream = None
        self.handler = MessageHandler(self.config)
        self.metrics = AgentMetrics(self.config.agent_name)
        self.running = False
    
    async def connect(self):
        """Connect to NATS and set up JetStream."""
        try:
            self.nats = NATS()
            await self.nats.connect(self.config.nats_url)
            self.jetstream = self.nats.jetstream()
            
            self.logger.info("Connected to NATS", 
                           nats_url=self.config.nats_url)
            
        except Exception as e:
            self.logger.error("Failed to connect to NATS", error=str(e))
            raise
    
    async def subscribe(self):
        """Subscribe to input subjects with durable consumer."""
        try:
            for subject in self.config.input_subjects:
                await self.jetstream.subscribe(
                    subject=subject,
                    cb=self._message_callback,
                    durable=f"{self.config.nats_durable}-{subject}",
                    config=ConsumerConfig(
                        deliver_policy=DeliverPolicy.ALL,
                        max_inflight=self.config.nats_max_inflight
                    )
                )
                
                self.logger.info("Subscribed to subject", 
                               subject=subject,
                               durable=self.config.nats_durable)
            
        except Exception as e:
            self.logger.error("Failed to subscribe", error=str(e))
            raise
    
    async def _message_callback(self, msg):
        """Handle incoming NATS messages."""
        corr_id = None
        try:
            # Extract correlation ID for tracing
            corr_id = self.handler.extract_correlation_id(msg)
            
            self.logger.info("Processing message", 
                           corr_id=corr_id,
                           subject=msg.subject)
            
            # Process message
            await self.handler.handle_message(msg, self.jetstream)
            
            # Acknowledge message
            await msg.ack()
            
            # Update metrics
            self.metrics.increment_processed(msg.subject)
            
        except Exception as e:
            self.logger.error("Message processing failed", 
                            corr_id=corr_id,
                            error=str(e))
            
            # Negative acknowledge for retry
            await msg.nak()
            
            # Update error metrics
            self.metrics.increment_errors(msg.subject, type(e).__name__)
    
    async def health_check(self):
        """Check agent health status."""
        if not self.nats or not self.nats.is_connected:
            return {'status': 'unhealthy', 'reason': 'NATS disconnected'}
        
        return {
            'status': 'healthy',
            'agent': self.config.agent_name,
            'version': self.config.agent_version,
            'nats_connected': self.nats.is_connected
        }
    
    async def start(self):
        """Start the agent."""
        self.logger.info("Starting agent", 
                        agent=self.config.agent_name,
                        version=self.config.agent_version)
        
        await self.connect()
        await self.subscribe()
        
        self.running = True
        self.logger.info("Agent started successfully")
        
        # Keep agent running
        while self.running:
            await asyncio.sleep(1)
    
    async def stop(self):
        """Gracefully stop the agent."""
        self.logger.info("Stopping agent")
        self.running = False
        
        if self.nats:
            await self.nats.close()
        
        self.logger.info("Agent stopped")
    
    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info("Received shutdown signal", signal=signum)
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Main entry point."""
    agent = TradingAgent()
    agent.setup_signal_handlers()
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        await agent.stop()
    except Exception as e:
        agent.logger.error("Agent crashed", error=str(e))
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
```

### 3. Message Handler (`handler.py`)

```python
import json
from datetime import datetime
from typing import Dict, Any, Optional

import structlog
from jsonschema import validate, ValidationError

from .config import AgentConfig
from .schemas import load_schemas

class MessageHandler:
    """Handles message processing logic."""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = structlog.get_logger(agent=config.agent_name)
        self.schemas = load_schemas()
    
    def extract_correlation_id(self, msg) -> Optional[str]:
        """Extract correlation ID from message."""
        try:
            data = json.loads(msg.data.decode())
            return data.get('corr_id')
        except Exception:
            return None
    
    async def handle_message(self, msg, jetstream):
        """Process incoming message and emit enriched signal."""
        # Parse message
        data = json.loads(msg.data.decode())
        
        # Validate against input schema
        self._validate_input(data)
        
        # Apply agent-specific logic
        enriched_data = await self._process_signal(data)
        
        # Validate output
        self._validate_output(enriched_data)
        
        # Publish enriched signal
        await self._publish_result(enriched_data, jetstream)
    
    def _validate_input(self, data: Dict[str, Any]):
        """Validate input against normalized signal schema."""
        try:
            validate(instance=data, schema=self.schemas['input'])
        except ValidationError as e:
            raise ValueError(f"Input validation failed: {e.message}")
    
    def _validate_output(self, data: Dict[str, Any]):
        """Validate output against enriched signal schema."""
        try:
            validate(instance=data, schema=self.schemas['output'])
        except ValidationError as e:
            raise ValueError(f"Output validation failed: {e.message}")
    
    async def _process_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Apply agent-specific processing logic.
        
        Override this method in agent implementations.
        """
        # Template implementation - replace with agent logic
        enriched = {
            'schema_version': '1.0.0',
            'agent_name': self.config.agent_name,
            'agent_version': self.config.agent_version,
            'corr_id': signal['corr_id'],
            'source_signal': {
                'instrument': signal['instrument'],
                'price': signal['price'],
                'timestamp': signal['timestamp']
            },
            'enriched_at': datetime.utcnow().isoformat(),
            'analysis': {
                'processed': True,
                'agent_specific_field': 'value'
            }
        }
        
        return enriched
    
    async def _publish_result(self, data: Dict[str, Any], jetstream):
        """Publish enriched signal to output subject."""
        message = json.dumps(data).encode()
        
        await jetstream.publish(
            subject=self.config.output_subject,
            payload=message
        )
        
        self.logger.info("Published enriched signal", 
                        corr_id=data['corr_id'],
                        subject=self.config.output_subject)
```

### 4. Schema Management (`schemas.py`)

```python
import json
from pathlib import Path
from typing import Dict, Any

def load_schemas() -> Dict[str, Dict[str, Any]]:
    """Load schemas for input and output validation."""
    
    # Path to at-core schemas
    core_schemas_path = Path('../at-core/schemas')
    
    # Load input schema (normalized signals)
    with open(core_schemas_path / 'signals.normalized.schema.json') as f:
        input_schema = json.load(f)
    
    # Define output schema (enriched signals)
    output_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": [
            "schema_version",
            "agent_name",
            "agent_version",
            "corr_id",
            "source_signal",
            "enriched_at",
            "analysis"
        ],
        "properties": {
            "schema_version": {"type": "string"},
            "agent_name": {"type": "string"},
            "agent_version": {"type": "string"},
            "corr_id": {"type": "string"},
            "source_signal": {"type": "object"},
            "enriched_at": {"type": "string", "format": "date-time"},
            "analysis": {"type": "object"}
        },
        "additionalProperties": False
    }
    
    return {
        'input': input_schema,
        'output': output_schema
    }
```

### 5. Metrics (`metrics.py`)

```python
from prometheus_client import Counter, Histogram, Gauge

class AgentMetrics:
    """Prometheus metrics for agent monitoring."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        
        # Message processing metrics
        self.messages_processed = Counter(
            'agent_messages_processed_total',
            'Total messages processed by agent',
            ['agent', 'subject']
        )
        
        self.messages_published = Counter(
            'agent_messages_published_total',
            'Total messages published by agent',
            ['agent', 'subject']
        )
        
        self.processing_duration = Histogram(
            'agent_processing_duration_seconds',
            'Time spent processing messages',
            ['agent']
        )
        
        self.errors_total = Counter(
            'agent_errors_total',
            'Total errors by agent',
            ['agent', 'subject', 'error_type']
        )
        
        self.consumer_lag = Gauge(
            'agent_consumer_lag',
            'NATS consumer lag',
            ['agent', 'subject']
        )
    
    def increment_processed(self, subject: str):
        """Increment processed message counter."""
        self.messages_processed.labels(
            agent=self.agent_name,
            subject=subject
        ).inc()
    
    def increment_published(self, subject: str):
        """Increment published message counter."""
        self.messages_published.labels(
            agent=self.agent_name,
            subject=subject
        ).inc()
    
    def record_processing_time(self, duration: float):
        """Record processing duration."""
        self.processing_duration.labels(
            agent=self.agent_name
        ).observe(duration)
    
    def increment_errors(self, subject: str, error_type: str):
        """Increment error counter."""
        self.errors_total.labels(
            agent=self.agent_name,
            subject=subject,
            error_type=error_type
        ).inc()
    
    def set_consumer_lag(self, subject: str, lag: int):
        """Set consumer lag gauge."""
        self.consumer_lag.labels(
            agent=self.agent_name,
            subject=subject
        ).set(lag)
```

## Agent Development Guidelines

### Conventions

1. **Correlation ID Propagation**: Always preserve and propagate `corr_id` from input to output
2. **Schema Versioning**: Include schema version in all output events
3. **Agent Versioning**: Tag all outputs with agent name and version
4. **Immutable Inputs**: Never modify input signals; create new enriched events
5. **Graceful Degradation**: Handle schema validation errors without crashing

### Logging Standards

```python
# Use structured logging with correlation IDs
logger.info("Processing signal",
           corr_id=signal['corr_id'],
           agent=self.config.agent_name,
           instrument=signal['instrument'],
           processing_time_ms=duration * 1000)

# Log errors with context
logger.error("Analysis failed",
           corr_id=signal['corr_id'],
           error=str(e),
           signal_price=signal['price'],
           error_type=type(e).__name__)
```

### Error Handling

```python
# Validation errors - don't retry
try:
    validate(signal, schema)
except ValidationError:
    logger.error("Invalid signal format", corr_id=signal['corr_id'])
    await msg.ack()  # Acknowledge to prevent redelivery
    return

# Processing errors - retry
try:
    result = await process_signal(signal)
except Exception as e:
    logger.error("Processing failed", error=str(e))
    await msg.nak()  # Negative ack for retry
    return
```

### Testing Requirements

1. **Unit tests** for processing logic
2. **Schema validation tests** for input/output
3. **Integration tests** with NATS
4. **Contract tests** against at-core schemas
5. **Load tests** for performance validation

## Deployment

### Environment Variables

```bash
# Required
NATS_URL=nats://localhost:4222
AGENT_NAME=my-agent

# Optional
NATS_STREAM=trading-events
NATS_DURABLE=my-agent-consumer
NATS_MAX_INFLIGHT=10
LOG_LEVEL=INFO
```

### Health Checks

```bash
# Agent should expose health endpoint
curl http://localhost:8080/health

# Expected response:
{
  "status": "healthy",
  "agent": "my-agent",
  "version": "1.0.0",
  "nats_connected": true
}
```

### Scaling Considerations

- Use durable consumers for at-least-once delivery
- Set appropriate `max_inflight` for throughput vs. resource usage
- Monitor consumer lag and scale horizontally when needed
- Implement circuit breakers for downstream dependencies

---

**Next Steps**: Use this template to create your agent implementation, replacing the placeholder logic in `_process_signal()` with your specific strategy.
"""
at-core: Shared contracts, schemas, and utilities for the trading system
"""

from .validators import validate_event, load_schema
from .events import create_event_header, generate_correlation_id

__version__ = "1.0.0"

__all__ = [
    "validate_event",
    "load_schema",
    "create_event_header",
    "generate_correlation_id"
]
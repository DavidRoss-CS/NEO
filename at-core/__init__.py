"""
at-core: Core utilities and schemas for NEO trading system.

This package provides:
- JSONSchema specifications for all message types
- Validation utilities with caching and error handling
- Event creation helpers for NATS messaging
- Common utilities shared across NEO services
"""

__version__ = "1.0.0"
__all__ = ["schemas", "validators", "events"]
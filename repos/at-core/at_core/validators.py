"""
Schema validation utilities for event contracts
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import jsonschema
from jsonschema import Draft202012Validator


class SchemaRegistry:
    """Centralized schema registry for event validation"""

    def __init__(self, schema_dir: Optional[str] = None):
        if schema_dir is None:
            # Default to schemas directory relative to this file
            self.schema_dir = Path(__file__).parent.parent / "schemas"
        else:
            self.schema_dir = Path(schema_dir)

        self._schemas: Dict[str, Dict] = {}
        self._validators: Dict[str, Draft202012Validator] = {}
        self._load_schemas()

    def _load_schemas(self):
        """Load all schema files from the schemas directory"""
        if not self.schema_dir.exists():
            raise ValueError(f"Schema directory not found: {self.schema_dir}")

        for schema_file in self.schema_dir.glob("*.schema.json"):
            schema_name = schema_file.stem.replace(".schema", "")
            try:
                with open(schema_file, 'r') as f:
                    schema = json.load(f)

                self._schemas[schema_name] = schema
                self._validators[schema_name] = Draft202012Validator(schema)

            except Exception as e:
                print(f"Warning: Failed to load schema {schema_file}: {e}")

    def get_schema(self, schema_name: str) -> Dict[str, Any]:
        """Get a schema by name"""
        if schema_name not in self._schemas:
            raise ValueError(f"Schema not found: {schema_name}")
        return self._schemas[schema_name]

    def validate(self, schema_name: str, data: Dict[str, Any]) -> bool:
        """Validate data against a schema"""
        if schema_name not in self._validators:
            raise ValueError(f"Schema not found: {schema_name}")

        validator = self._validators[schema_name]
        try:
            validator.validate(data)
            return True
        except jsonschema.ValidationError:
            return False

    def validate_with_errors(self, schema_name: str, data: Dict[str, Any]) -> tuple[bool, list]:
        """Validate data and return detailed errors"""
        if schema_name not in self._validators:
            raise ValueError(f"Schema not found: {schema_name}")

        validator = self._validators[schema_name]
        errors = list(validator.iter_errors(data))

        return len(errors) == 0, [str(error) for error in errors]

    def list_schemas(self) -> list[str]:
        """List all available schema names"""
        return list(self._schemas.keys())


# Global registry instance
_registry = None


def get_registry() -> SchemaRegistry:
    """Get the global schema registry instance"""
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
    return _registry


def validate_event(event_type: str, data: Dict[str, Any], raise_on_error: bool = True) -> bool:
    """
    Validate an event against its schema

    Args:
        event_type: Event type (e.g., 'signals.raw', 'decisions.order_intent')
        data: Event data to validate
        raise_on_error: Whether to raise exception on validation failure

    Returns:
        True if valid, False if invalid (when raise_on_error=False)

    Raises:
        ValueError: If schema not found or validation fails (when raise_on_error=True)
    """
    registry = get_registry()

    try:
        is_valid, errors = registry.validate_with_errors(event_type, data)

        if not is_valid:
            error_msg = f"Validation failed for {event_type}: {'; '.join(errors)}"
            if raise_on_error:
                raise ValueError(error_msg)
            return False

        return True

    except ValueError as e:
        if raise_on_error:
            raise
        return False


def load_schema(event_type: str) -> Dict[str, Any]:
    """
    Load a schema by event type

    Args:
        event_type: Event type (e.g., 'signals.raw')

    Returns:
        Schema dictionary

    Raises:
        ValueError: If schema not found
    """
    registry = get_registry()
    return registry.get_schema(event_type)


def list_available_schemas() -> list[str]:
    """List all available event schemas"""
    registry = get_registry()
    return registry.list_schemas()
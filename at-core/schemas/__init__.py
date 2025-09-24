from importlib.resources import files
import json

__all__ = [
    "load_schema",
    "SIGNAL_EVENT_V1",
    "AGENT_OUTPUT_V1",
    "ORDER_INTENT_V1",
]

_cache = {}

def load_schema(name: str) -> dict:
    """Load and cache a JSONSchema by filename.

    Args:
        name: Schema filename (e.g., 'SignalEventV1.json')

    Returns:
        Parsed JSON schema dictionary

    Raises:
        FileNotFoundError: If schema file doesn't exist
        json.JSONDecodeError: If schema file is invalid JSON
    """
    if name in _cache:
        return _cache[name]

    try:
        schema_file = files(__package__).joinpath(name)
        if not schema_file.is_file():
            raise FileNotFoundError(f"Schema file not found: {name}")

        data = schema_file.read_text(encoding="utf-8")
        _cache[name] = json.loads(data)
        return _cache[name]
    except Exception as e:
        # Clear cache entry on error to allow retry
        _cache.pop(name, None)
        raise

# Pre-load commonly used schemas
SIGNAL_EVENT_V1 = load_schema("SignalEventV1.json")
AGENT_OUTPUT_V1 = load_schema("AgentOutputV1.json")
ORDER_INTENT_V1 = load_schema("OrderIntentV1.json")
#!/usr/bin/env python3
"""
Quick test script for schema registry functionality.
"""

import json
import sys
import os
import datetime as dt

# Add at-core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'at-core'))

def test_direct_schema_loading():
    """Test direct JSON schema loading"""
    print("🔍 Testing direct schema loading...")

    with open('at-core/schemas/SignalEventV1.json') as f:
        signal_schema = json.load(f)

    print(f"✅ SignalEventV1: {signal_schema['title']} v{signal_schema['properties']['schema_version']['const']}")

    with open('at-core/schemas/AgentOutputV1.json') as f:
        agent_schema = json.load(f)

    print(f"✅ AgentOutputV1: {agent_schema['title']} v{agent_schema['properties']['schema_version']['const']}")

    with open('at-core/schemas/OrderIntentV1.json') as f:
        order_schema = json.load(f)

    print(f"✅ OrderIntentV1: {order_schema['title']} v{order_schema['properties']['schema_version']['const']}")

    return signal_schema, agent_schema, order_schema

def test_schema_validation():
    """Test schema validation with jsonschema"""
    print("\n🔍 Testing schema validation...")

    try:
        from jsonschema import Draft202012Validator

        # Load signal schema and create validator
        with open('at-core/schemas/SignalEventV1.json') as f:
            signal_schema = json.load(f)

        validator = Draft202012Validator(signal_schema)

        # Test valid payload
        valid_signal = {
            "schema_version": "1.0.0",
            "intent_id": "intent-123456",
            "correlation_id": "corr-123456",
            "source": "tradingview",
            "instrument": "BTCUSD",
            "type": "momentum",
            "strength": 0.82,
            "priority": "standard",
            "payload": {"price": 120000.25},
            "ts_iso": dt.datetime(2025,1,1,tzinfo=dt.timezone.utc).isoformat()
        }

        errors = list(validator.iter_errors(valid_signal))
        if errors:
            print(f"❌ Validation failed: {[e.message for e in errors]}")
        else:
            print("✅ Valid signal payload validated successfully")

        # Test invalid payload (missing required field)
        invalid_signal = valid_signal.copy()
        del invalid_signal['instrument']

        errors = list(validator.iter_errors(invalid_signal))
        if errors:
            print(f"✅ Invalid signal properly rejected: {errors[0].message}")
        else:
            print("❌ Invalid signal should have been rejected")

    except ImportError as e:
        print(f"⚠️  jsonschema not available for validation test: {e}")

def main():
    """Run all schema registry tests"""
    print("🚀 Testing NEO Schema Registry v1.0.0")
    print("=" * 50)

    # Test direct schema loading
    schemas = test_direct_schema_loading()

    # Test validation if jsonschema available
    test_schema_validation()

    print("\n🎉 Schema registry tests completed!")
    print(f"📁 Schema files created in: {os.path.abspath('at-core/schemas')}")
    print("📋 Ready for integration with NEO services")

if __name__ == "__main__":
    main()
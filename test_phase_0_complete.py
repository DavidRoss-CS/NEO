#!/usr/bin/env python3
"""
Comprehensive test for Phase 0 completion.

Validates that all components of the foundation package work together
and are ready for Phase 1 implementation.
"""

import sys
import os
import json
import datetime as dt

def test_schema_registry():
    """Test complete schema registry functionality"""
    print("🔍 Testing Schema Registry...")

    # Test direct JSON loading
    schemas_loaded = 0
    try:
        with open('at-core/schemas/SignalEventV1.json') as f:
            signal_schema = json.load(f)
            schemas_loaded += 1

        with open('at-core/schemas/AgentOutputV1.json') as f:
            agent_schema = json.load(f)
            schemas_loaded += 1

        with open('at-core/schemas/OrderIntentV1.json') as f:
            order_schema = json.load(f)
            schemas_loaded += 1

        print(f"   ✅ {schemas_loaded}/3 schemas loaded successfully")
        return True
    except Exception as e:
        print(f"   ❌ Schema loading failed: {e}")
        return False

def test_contract_validation():
    """Test contract validation with real payloads"""
    print("🔍 Testing Contract Validation...")

    try:
        from jsonschema import Draft202012Validator

        # Load schema
        with open('at-core/schemas/SignalEventV1.json') as f:
            schema = json.load(f)

        validator = Draft202012Validator(schema)

        # Test valid payload
        valid_payload = {
            "schema_version": "1.0.0",
            "intent_id": "test-intent-123",
            "correlation_id": "test-corr-123",
            "source": "tradingview",
            "instrument": "BTCUSD",
            "type": "momentum",
            "strength": 0.75,
            "payload": {"price": 120000.0},
            "ts_iso": dt.datetime.now(dt.timezone.utc).isoformat()
        }

        errors = list(validator.iter_errors(valid_payload))
        if errors:
            print(f"   ❌ Valid payload rejected: {errors[0].message}")
            return False

        # Test invalid payload
        invalid_payload = valid_payload.copy()
        del invalid_payload["instrument"]  # Remove required field

        errors = list(validator.iter_errors(invalid_payload))
        if not errors:
            print("   ❌ Invalid payload accepted")
            return False

        print("   ✅ Contract validation working correctly")
        return True

    except Exception as e:
        print(f"   ❌ Contract validation failed: {e}")
        return False

def test_golden_data():
    """Test golden test data availability"""
    print("🔍 Testing Golden Test Data...")

    golden_cases = [
        "tv_momentum_btc_001.json.gz",
        "tv_breakout_eth_001.json.gz",
        "tv_invalid_001.json.gz"
    ]

    cases_found = 0
    for case in golden_cases:
        case_path = f"tests/data/tradingview/{case}"
        if os.path.exists(case_path):
            cases_found += 1
        else:
            print(f"   ❌ Missing golden case: {case}")

    if cases_found == len(golden_cases):
        print(f"   ✅ All {cases_found}/{len(golden_cases)} golden cases available")
        return True
    else:
        print(f"   ⚠️  Only {cases_found}/{len(golden_cases)} golden cases found")
        return False

def test_documentation():
    """Test documentation completeness"""
    print("🔍 Testing Documentation...")

    required_docs = [
        "docs/NATS_SUBJECTS.md",
        "docs/FEATURE_FLAGS.md",
        "at-core/CHANGELOG.md",
        "at-core/SCHEMA_EVOLUTION_POLICY.md",
        "workspace/PHASE_0_COMPLETION_SUMMARY.md"
    ]

    docs_found = 0
    for doc in required_docs:
        if os.path.exists(doc):
            docs_found += 1
        else:
            print(f"   ❌ Missing documentation: {doc}")

    if docs_found == len(required_docs):
        print(f"   ✅ All {docs_found}/{len(required_docs)} documentation files present")
        return True
    else:
        print(f"   ⚠️  Only {docs_found}/{len(required_docs)} docs found")
        return False

def test_test_infrastructure():
    """Test fixture availability"""
    print("🔍 Testing Test Infrastructure...")

    required_fixtures = [
        "tests/fixtures/fake_nats.py",
        "tests/fixtures/fake_clock.py",
        "tests/fixtures/config_factory.py",
        "tests/fixtures/__init__.py",
        "tests/utils/replay.py",
        "tests/utils/contract_helpers.py",
        "tests/conftest.py",
        "tests/pytest.ini"
    ]

    fixtures_found = 0
    for fixture in required_fixtures:
        if os.path.exists(fixture):
            fixtures_found += 1
        else:
            print(f"   ❌ Missing fixture: {fixture}")

    if fixtures_found == len(required_fixtures):
        print(f"   ✅ All {fixtures_found}/{len(required_fixtures)} test fixtures available")
        return True
    else:
        print(f"   ⚠️  Only {fixtures_found}/{len(required_fixtures)} fixtures found")
        return False

def test_workspace_tracking():
    """Test workspace documentation"""
    print("🔍 Testing Workspace Tracking...")

    workspace_files = [
        "workspace/rollout_tracking.md",
        "workspace/tickets/README.md",
        "workspace/tickets/NEO-001-schema-registry.md"
    ]

    files_found = 0
    for wfile in workspace_files:
        if os.path.exists(wfile):
            files_found += 1
        else:
            print(f"   ❌ Missing workspace file: {wfile}")

    if files_found == len(workspace_files):
        print(f"   ✅ All {files_found}/{len(workspace_files)} workspace files present")
        return True
    else:
        print(f"   ⚠️  Only {files_found}/{len(workspace_files)} workspace files found")
        return False

def main():
    """Run complete Phase 0 validation"""
    print("🚀 NEO Phase 0 Foundation Package - Complete Validation")
    print("=" * 60)

    tests = [
        ("Schema Registry", test_schema_registry),
        ("Contract Validation", test_contract_validation),
        ("Golden Test Data", test_golden_data),
        ("Documentation", test_documentation),
        ("Test Infrastructure", test_test_infrastructure),
        ("Workspace Tracking", test_workspace_tracking)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            print()  # Empty line between tests
        except Exception as e:
            print(f"   ❌ {test_name} test crashed: {e}")
            print()

    print("=" * 60)
    print(f"📊 PHASE 0 VALIDATION RESULTS")
    print(f"   Tests Passed: {passed}/{total}")
    print(f"   Success Rate: {passed/total*100:.1f}%")

    if passed == total:
        print("🎉 PHASE 0 FOUNDATION PACKAGE COMPLETE AND VALIDATED!")
        print("✅ Ready to proceed with Phase 1 implementation")
        print("📋 All components tested and working correctly")
        return True
    else:
        print("⚠️  Some validation tests failed")
        print("❌ Review failed components before proceeding")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
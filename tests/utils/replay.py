"""
Test data recording and replay utilities.

Provides functionality to record real webhook payloads and replay them
in tests for deterministic validation of the complete system.
"""

import gzip
import json
import pathlib
from typing import Dict, Any, Optional, List
import datetime as dt


# Test data directory
DATA_DIR = pathlib.Path(__file__).parents[1] / "data"
TRADINGVIEW_DIR = DATA_DIR / "tradingview"


def record_case(case_name: str, body: Dict[str, Any], headers: Dict[str, str],
                category: str = "tradingview") -> pathlib.Path:
    """
    Record a test case for later replay.

    Args:
        case_name: Unique identifier for the test case
        body: HTTP request body (will be JSON serialized)
        headers: HTTP request headers
        category: Category subdirectory (tradingview, webhook, etc.)

    Returns:
        Path to the saved test case file
    """
    category_dir = DATA_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)

    # Create test case data structure
    test_case = {
        "metadata": {
            "case_name": case_name,
            "category": category,
            "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "version": "1.0.0"
        },
        "request": {
            "body": body,
            "headers": headers
        }
    }

    # Save as compressed JSON
    case_file = category_dir / f"{case_name}.json.gz"
    with gzip.open(case_file, 'wt', encoding='utf-8') as f:
        json.dump(test_case, f, indent=2, sort_keys=True)

    return case_file


def load_case(case_name: str, category: str = "tradingview") -> Dict[str, Any]:
    """
    Load a test case for replay.

    Args:
        case_name: Test case identifier
        category: Category subdirectory

    Returns:
        Test case data with metadata, body, and headers

    Raises:
        FileNotFoundError: If test case file doesn't exist
        json.JSONDecodeError: If test case file is corrupted
    """
    case_file = DATA_DIR / category / f"{case_name}.json.gz"

    if not case_file.exists():
        raise FileNotFoundError(f"Test case not found: {case_file}")

    with gzip.open(case_file, 'rt', encoding='utf-8') as f:
        return json.load(f)


def list_cases(category: str = "tradingview") -> List[str]:
    """
    List available test cases in a category.

    Args:
        category: Category subdirectory to search

    Returns:
        List of case names (without .json.gz extension)
    """
    category_dir = DATA_DIR / category

    if not category_dir.exists():
        return []

    cases = []
    for case_file in category_dir.glob("*.json.gz"):
        case_name = case_file.stem.replace(".json", "")
        cases.append(case_name)

    return sorted(cases)


def get_case_metadata(case_name: str, category: str = "tradingview") -> Dict[str, Any]:
    """Get metadata for a test case without loading the full payload."""
    test_case = load_case(case_name, category)
    return test_case.get("metadata", {})


class ReplaySession:
    """
    Context manager for replaying multiple test cases in sequence.

    Example:
        with ReplaySession() as session:
            case1 = session.load("tv_momentum_btc_001")
            case2 = session.load("tv_breakout_eth_001")
            # ... use test cases
    """

    def __init__(self, category: str = "tradingview"):
        self.category = category
        self._loaded_cases: Dict[str, Dict[str, Any]] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._loaded_cases.clear()

    def load(self, case_name: str) -> Dict[str, Any]:
        """Load a test case (cached within the session)."""
        if case_name not in self._loaded_cases:
            self._loaded_cases[case_name] = load_case(case_name, self.category)
        return self._loaded_cases[case_name]

    def get_body(self, case_name: str) -> Dict[str, Any]:
        """Get just the request body from a test case."""
        case = self.load(case_name)
        return case["request"]["body"]

    def get_headers(self, case_name: str) -> Dict[str, str]:
        """Get just the request headers from a test case."""
        case = self.load(case_name)
        return case["request"]["headers"]

    def list_cases(self) -> List[str]:
        """List available cases in this category."""
        return list_cases(self.category)


# Convenience functions for common test scenarios

def create_sample_tradingview_case() -> Dict[str, Any]:
    """Create a sample TradingView webhook payload for testing."""
    return {
        "passphrase": "test-passphrase",
        "time": int(dt.datetime.now().timestamp()),
        "ticker": "BINANCE:BTCUSDT",
        "strategy": {
            "order_action": "buy",
            "order_contracts": 1,
            "order_price": 120000.25
        },
        "price": 120000.25,
        "message": "BTC momentum long signal",
        "signal_strength": 0.82
    }


def create_sample_headers(timestamp: Optional[float] = None,
                         nonce: Optional[str] = None,
                         signature: Optional[str] = None) -> Dict[str, str]:
    """Create sample HTTP headers for webhook testing."""
    if timestamp is None:
        timestamp = dt.datetime.now().timestamp()

    if nonce is None:
        nonce = f"test-nonce-{int(timestamp)}"

    return {
        "Content-Type": "application/json",
        "X-Timestamp": str(timestamp),
        "X-Nonce": nonce,
        "X-Signature": signature or "test-signature",
        "User-Agent": "TradingView-Webhook"
    }


def record_golden_cases():
    """Record the standard golden test cases."""
    # Golden case 1: BTC momentum long
    btc_momentum_body = create_sample_tradingview_case()
    btc_momentum_headers = create_sample_headers()

    record_case("tv_momentum_btc_001", btc_momentum_body, btc_momentum_headers)

    # Golden case 2: ETH breakout short
    eth_breakout_body = {
        "passphrase": "test-passphrase",
        "time": int(dt.datetime.now().timestamp()),
        "ticker": "BINANCE:ETHUSDT",
        "strategy": {
            "order_action": "sell",
            "order_contracts": 10,
            "order_price": 4250.50
        },
        "price": 4250.50,
        "message": "ETH resistance breakout short",
        "signal_strength": 0.75
    }

    record_case("tv_breakout_eth_001", eth_breakout_body, create_sample_headers())

    # Golden case 3: Invalid payload (for error testing)
    invalid_body = {
        "invalid": "payload",
        "missing_required_fields": True
    }

    record_case("tv_invalid_001", invalid_body, create_sample_headers())

    print("✅ Golden test cases recorded")
    print(f"📁 Cases saved to: {TRADINGVIEW_DIR}")


if __name__ == "__main__":
    # When run directly, record golden cases
    record_golden_cases()
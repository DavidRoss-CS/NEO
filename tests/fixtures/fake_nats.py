"""
Fake NATS client for testing NEO services in isolation.

Provides a simple in-memory message broker that mimics NATS behavior
without requiring an actual NATS server.
"""

from collections import defaultdict, deque
from typing import Dict, List, Callable, Any, Optional, Tuple
import asyncio
import re
import json


class FakeMessage:
    """Fake NATS message for testing."""

    def __init__(self, subject: str, data: bytes, headers: Optional[Dict[str, str]] = None):
        self.subject = subject
        self.data = data
        self.headers = headers or {}
        self._acked = False

    async def ack(self):
        """Acknowledge the message."""
        self._acked = True

    @property
    def acked(self) -> bool:
        """Check if message was acknowledged."""
        return self._acked


class FakeNats:
    """
    Fake NATS client that mimics basic publish/subscribe behavior.

    Features:
    - Subject pattern matching with wildcards (* and >)
    - Message queuing and delivery
    - Subscription management
    - JetStream-like message persistence (optional)
    """

    def __init__(self, persist_messages: bool = False):
        self._subscriptions: Dict[str, List[Callable]] = defaultdict(list)
        self._messages: deque = deque(maxlen=1000)  # Message history
        self._persist = persist_messages
        self._msg_id_counter = 0

    async def publish(self, subject: str, data: bytes, headers: Optional[Dict[str, str]] = None):
        """
        Publish a message to a subject.

        Args:
            subject: NATS subject
            data: Message payload as bytes
            headers: Optional message headers
        """
        msg = FakeMessage(subject, data, headers)

        if self._persist:
            self._messages.append((subject, data, headers))

        # Deliver to matching subscribers
        for pattern, callbacks in self._subscriptions.items():
            if self._subject_matches(subject, pattern):
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(msg)
                        else:
                            callback(msg)
                    except Exception as e:
                        # Log but don't fail the publish
                        print(f"Warning: Subscriber callback failed: {e}")

    def subscribe(self, subject_pattern: str, callback: Callable):
        """
        Subscribe to messages matching a subject pattern.

        Args:
            subject_pattern: Subject pattern with wildcards (* and >)
            callback: Function to call with matching messages
        """
        self._subscriptions[subject_pattern].append(callback)

    def unsubscribe(self, subject_pattern: str, callback: Optional[Callable] = None):
        """
        Unsubscribe from a subject pattern.

        Args:
            subject_pattern: Subject pattern to unsubscribe from
            callback: Specific callback to remove (None to remove all)
        """
        if callback is None:
            self._subscriptions[subject_pattern].clear()
        else:
            try:
                self._subscriptions[subject_pattern].remove(callback)
            except ValueError:
                pass

    def get_messages(self) -> List[Tuple[str, bytes, Optional[Dict[str, str]]]]:
        """Get all messages sent through this fake client."""
        return list(self._messages)

    def clear_messages(self):
        """Clear message history."""
        self._messages.clear()

    def get_subscriptions(self) -> Dict[str, int]:
        """Get subscription count by subject pattern."""
        return {pattern: len(callbacks) for pattern, callbacks in self._subscriptions.items()}

    def _subject_matches(self, subject: str, pattern: str) -> bool:
        """
        Check if a subject matches a pattern.

        Wildcard rules:
        - '*' matches exactly one token
        - '>' matches one or more tokens (must be at the end)
        """
        if subject == pattern:
            return True

        subject_tokens = subject.split('.')
        pattern_tokens = pattern.split('.')

        return self._tokens_match(subject_tokens, pattern_tokens)

    def _tokens_match(self, subject_tokens: List[str], pattern_tokens: List[str]) -> bool:
        """Check if subject tokens match pattern tokens."""
        s_idx = 0  # subject index
        p_idx = 0  # pattern index

        while s_idx < len(subject_tokens) and p_idx < len(pattern_tokens):
            pattern_token = pattern_tokens[p_idx]

            if pattern_token == '>':
                # '>' matches rest of subject
                return True
            elif pattern_token == '*':
                # '*' matches one token
                s_idx += 1
                p_idx += 1
            elif pattern_token == subject_tokens[s_idx]:
                # Exact match
                s_idx += 1
                p_idx += 1
            else:
                # No match
                return False

        # Check if we consumed all tokens correctly
        if p_idx < len(pattern_tokens):
            # Remaining pattern tokens must be '>'
            return p_idx == len(pattern_tokens) - 1 and pattern_tokens[p_idx] == '>'

        return s_idx == len(subject_tokens)


class FakeJetStream:
    """Fake JetStream client for testing stream operations."""

    def __init__(self, nats_client: FakeNats):
        self._nats = nats_client
        self._streams: Dict[str, Dict] = {}

    async def add_stream(self, name: str, subjects: List[str], **kwargs):
        """Add a stream (fake implementation)."""
        self._streams[name] = {
            'name': name,
            'subjects': subjects,
            'config': kwargs
        }

    async def publish(self, subject: str, data: bytes, headers: Optional[Dict[str, str]] = None):
        """Publish to JetStream (delegates to regular NATS)."""
        await self._nats.publish(subject, data, headers)

    async def subscribe(self, subject: str, cb: Callable, durable: Optional[str] = None, **kwargs):
        """Subscribe with JetStream (delegates to regular NATS)."""
        self._nats.subscribe(subject, cb)

    def get_streams(self) -> Dict[str, Dict]:
        """Get all configured streams."""
        return self._streams.copy()


# Convenience functions for common test scenarios

def create_test_nats(persist: bool = True) -> Tuple[FakeNats, FakeJetStream]:
    """Create a fake NATS client and JetStream for testing."""
    nats = FakeNats(persist_messages=persist)
    js = FakeJetStream(nats)
    return nats, js


async def publish_test_signal(nats: FakeNats, instrument: str = "BTCUSD",
                             signal_type: str = "momentum", strength: float = 0.8):
    """Publish a test signal to the fake NATS client."""
    import datetime as dt

    signal = {
        "schema_version": "1.0.0",
        "intent_id": f"test-{dt.datetime.now().timestamp()}",
        "correlation_id": f"corr-{dt.datetime.now().timestamp()}",
        "source": "test",
        "instrument": instrument,
        "type": signal_type,
        "strength": strength,
        "payload": {"test": True},
        "ts_iso": dt.datetime.now(dt.timezone.utc).isoformat()
    }

    await nats.publish(
        f"signals.normalized.std.{instrument}.{signal_type}",
        json.dumps(signal).encode(),
        {"Corr-ID": signal["correlation_id"]}
    )
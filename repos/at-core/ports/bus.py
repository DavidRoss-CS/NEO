from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

@dataclass(frozen=True)
class Message:
    topic: str
    key: bytes
    value: bytes
    headers: Mapping[str, str]

class Subscription(Protocol):
    def close(self) -> None: ...

Handler = Callable[[Message], None]

class Bus(Protocol):
    def publish(self, topic: str, key: bytes, value: bytes, headers: Mapping[str, str] | None = None) -> None: ...
    def subscribe(self, topic: str, group: str, handler: Handler) -> Subscription: ...

class _InMemorySubscription:
    def __init__(self, bus: "InMemoryBus", topic: str, group: str) -> None:
        self._bus = bus; self._topic = topic; self._group = group; self._closed = False
    def close(self) -> None:
        if not self._closed:
            self._bus._handlers.get(self._topic, {}).pop(self._group, None)
            self._closed = True

class InMemoryBus(Bus):
    def __init__(self) -> None:
        self._handlers: dict[str, dict[str, Handler]] = {}
    def publish(self, topic: str, key: bytes, value: bytes, headers: Mapping[str, str] | None = None) -> None:
        msg = Message(topic=topic, key=key, value=value, headers=dict(headers or {}))
        for handler in list(self._handlers.get(topic, {}).values()):
            handler(msg)
    def subscribe(self, topic: str, group: str, handler: Handler) -> Subscription:
        self._handlers.setdefault(topic, {})[group] = handler
        return _InMemorySubscription(self, topic, group)

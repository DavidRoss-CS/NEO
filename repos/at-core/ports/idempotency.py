from __future__ import annotations
from typing import Protocol

class Idempotency(Protocol):
    def seen(self, scope: str, key: str) -> bool: ...
    def mark(self, scope: str, key: str, ttl_s: int) -> None: ...

class InMemoryIdempotency(Idempotency):
    def __init__(self) -> None:
        self._scopes: dict[str, set[str]] = {}
    def seen(self, scope: str, key: str) -> bool:
        return key in self._scopes.get(scope, set())
    def mark(self, scope: str, key: str, ttl_s: int) -> None:
        self._scopes.setdefault(scope, set()).add(key)

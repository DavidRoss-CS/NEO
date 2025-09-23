from __future__ import annotations
from typing import Protocol

class Store(Protocol):
    def get(self, key: str) -> bytes | None: ...
    def put(self, key: str, value: bytes, ttl_s: int | None = None) -> None: ...
    def delete(self, key: str) -> None: ...

class InMemoryStore(Store):
    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
    def get(self, key: str) -> bytes | None:
        return self._data.get(key)
    def put(self, key: str, value: bytes, ttl_s: int | None = None) -> None:
        self._data[key] = value
    def delete(self, key: str) -> None:
        self._data.pop(key, None)

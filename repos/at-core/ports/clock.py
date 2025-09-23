from __future__ import annotations
from datetime import datetime, timezone
from typing import Protocol

class Clock(Protocol):
    def now_utc(self) -> datetime: ...
    def monotonic_ns(self) -> int: ...

class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)
    def monotonic_ns(self) -> int:
        from time import monotonic_ns
        return monotonic_ns()

from __future__ import annotations
from contextlib import contextmanager
from typing import Protocol, Iterator

class Span(Protocol):
    def set_tag(self, key: str, value): ...
    def record_exception(self, err: BaseException) -> None: ...
    def end(self) -> None: ...

class Tracer(Protocol):
    def start_span(self, name: str, trace_id: str | None = None) -> Span: ...

class _NoopSpan:
    def set_tag(self, key: str, value): pass
    def record_exception(self, err: BaseException) -> None: pass
    def end(self) -> None: pass

class NoopTracer:
    def start_span(self, name: str, trace_id: str | None = None) -> Span:
        return _NoopSpan()

@contextmanager
def span_cm(tracer: Tracer, name: str, trace_id: str | None = None) -> Iterator[Span]:
    s = NoopTracer().start_span(name, trace_id) if not hasattr(tracer, "start_span") else tracer.start_span(name, trace_id)
    try: yield s
    finally: s.end()

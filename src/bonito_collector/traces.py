"""OpenTelemetry trace export for Bonito (BON-007).

Emits a span per slow/top query and per lock/blocking pair when
``BONITO_OTLP_ENDPOINT`` is configured. Everything is a **no-op** when the
endpoint is unset or the OTLP deps are missing — the collector must never
break because tracing is unavailable.
"""
from __future__ import annotations

from typing import Any

_tracer: Any = None


def init_otlp(endpoint: str | None) -> bool:
    """Configure the OTLP tracer. Returns False (and stays a no-op) when the
    endpoint is unset or the OpenTelemetry deps are not importable."""
    global _tracer
    _tracer = None
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": "bonito-collector"}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=5))
    )
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("bonito-collector")
    return True


def _span(name: str, attributes: dict[str, Any]) -> None:
    if _tracer is None:
        return
    span = _tracer.start_span(name)
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)
    span.end()


def emit_query_span(
    fingerprint: str,
    query_text: str,
    mean_ms: Any = None,
    max_ms: Any = None,
    calls: Any = None,
    rows: Any = None,
    buffer_hit_ratio: Any = None,
    db_instance: str = "default",
) -> None:
    _span(
        f"query.{fingerprint}",
        {
            "db.system": "postgresql",
            "db.instance": db_instance,
            "bonito.fingerprint": str(fingerprint),
            "bonito.query": (query_text or "")[:500],
            "bonito.mean_ms": mean_ms,
            "bonito.max_ms": max_ms,
            "bonito.calls": calls,
            "bonito.rows": rows,
            "bonito.buffer_hit_ratio": buffer_hit_ratio,
        },
    )


def emit_lock_span(
    blocked_pid: Any,
    blocking_pid: Any,
    wait_event_type: Any = None,
    wait_event: Any = None,
    db_instance: str = "default",
) -> None:
    _span(
        f"lock.blocking.{blocking_pid}->{blocked_pid}",
        {
            "db.system": "postgresql",
            "db.instance": db_instance,
            "bonito.blocked_pid": blocked_pid,
            "bonito.blocking_pid": blocking_pid,
            "bonito.wait_event_type": wait_event_type,
            "bonito.wait_event": wait_event,
        },
    )
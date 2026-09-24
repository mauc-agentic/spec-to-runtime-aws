"""Trazas del agente (OpenTelemetry). Sin el distro de AWS configurado, todo esto es un no-op."""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import baggage, context, trace

_tracer = trace.get_tracer("spec_to_runtime.agent")


@contextmanager
def session_context(session_id: str) -> Iterator[None]:
    """Marca la traza con `session.id`: la consola de AgentCore agrupa las trazas por conversación."""
    token = context.attach(baggage.set_baggage("session.id", session_id))
    try:
        yield
    finally:
        context.detach(token)


def annotate(**attributes) -> None:
    """Atributos `app.*` en el span actual: sirven para filtrar y correlacionar en la consola."""
    span = trace.get_current_span()
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(f"app.{key}", value)


@contextmanager
def span(name: str, **attributes) -> Iterator[trace.Span]:
    with _tracer.start_as_current_span(name) as current:
        annotate(**attributes)
        yield current

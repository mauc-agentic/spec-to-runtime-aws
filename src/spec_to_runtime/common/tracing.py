"""Trazas de punta a punta: une la traza de las Lambdas (X-Ray) con la del agente (OpenTelemetry).

Lambda con "active tracing" deja la cabecera de X-Ray en `_X_AMZN_TRACE_ID`
(`Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1`). AgentCore Runtime
entiende también la cabecera W3C `traceparent`, así que se pasan las dos con el mismo id: los spans
del agente cuelgan del segmento de la Lambda y todo aparece como una sola traza.
"""

import os
import re

_ROOT = re.compile(r"Root=(1-[0-9a-f]{8}-[0-9a-f]{24})")
_PARENT = re.compile(r"Parent=([0-9a-f]{16})")
_SAMPLED = re.compile(r"Sampled=([01])")


def xray_header() -> str | None:
    """Cabecera de traza de la invocación actual de Lambda, si tiene el trazado activo."""
    return os.environ.get("_X_AMZN_TRACE_ID") or None


def root_trace_id(header: str | None) -> str | None:
    match = _ROOT.search(header or "")
    return match.group(1) if match else None


def to_traceparent(header: str | None) -> str | None:
    """`Root=1-<8 hex>-<24 hex>;Parent=<16 hex>;Sampled=1` -> `00-<32 hex>-<16 hex>-01`."""
    root, parent = root_trace_id(header), _PARENT.search(header or "")
    if not root or not parent:
        return None
    sampled = _SAMPLED.search(header)
    flags = "01" if sampled is None or sampled.group(1) == "1" else "00"
    return f"00-{root[2:10]}{root[11:]}-{parent.group(1)}-{flags}"


def runtime_trace_kwargs(session_id: str) -> dict[str, str]:
    """Argumentos de `invoke_agent_runtime` para continuar la traza; vacío si no hay traza activa."""
    header = xray_header()
    traceparent = to_traceparent(header)
    if not header or not traceparent:
        return {}
    # `baggage` con session.id agrupa las trazas por conversación en la consola de AgentCore.
    return {"traceId": header, "traceParent": traceparent, "baggage": f"session.id={session_id}"}

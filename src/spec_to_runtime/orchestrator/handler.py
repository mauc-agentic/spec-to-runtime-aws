"""Orquestador (UC-004): consume la cola, invoca al agente y va escribiendo la respuesta.

El navegador consulta la solicitud cada ~1 s (polling), así que el texto parcial se guarda en
DynamoDB mientras llega, con estados En cola, Buscando y Redactando (NFR-011).
"""

import functools
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from spec_to_runtime.common import metrics, quota, requests_store, tracing
from spec_to_runtime.orchestrator import formatting, stream

logger = logging.getLogger(__name__)

FLUSH_SECONDS = 0.7  # cada cuánto se publica el texto parcial
DEADLINE_SECONDS = 60  # UC-004 BR-007: pasado este tiempo la solicitud falla
DEFAULT_BLOCKED = "No puedo responder a esta pregunta. Pregúntame sobre el repositorio o la charla."


@dataclass
class Deps:
    table: object
    usage_client: object
    runtime: object
    usage_table: str
    runtime_arn: str


@functools.cache
def _deps() -> Deps:
    region = os.environ.get("AWS_REGION", "us-east-1")
    return Deps(
        table=boto3.resource("dynamodb", region_name=region).Table(os.environ["REQUESTS_TABLE"]),
        usage_client=boto3.client("dynamodb", region_name=region),
        runtime=boto3.client(
            "bedrock-agentcore",
            region_name=region,
            config=Config(read_timeout=DEADLINE_SECONDS + 10, retries={"max_attempts": 1}),
        ),
        usage_table=os.environ["USAGE_TABLE"],
        runtime_arn=os.environ["AGENT_RUNTIME_ARN"],
    )


def _decimals(value):
    """DynamoDB no admite float: las puntuaciones de las citas pasan a Decimal."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def _finish(deps: Deps, message: dict, status: str, fields: dict, now) -> None:
    fields = {**fields, "status": status, "phase": status, "completed_at": now().isoformat()}
    requests_store.update_request(deps.table, message["user_id"], message["request_id"], fields)
    if status == "Failed":  # UC-004 BR-006: los fallos no consumen cuota
        quota.release(deps.usage_client, deps.usage_table, message["user_id"], message["day"])


def _trace_fields() -> dict:
    """Traza principal de la pregunta (orquestador + agente); enlaza a la traza de la API."""
    trace_id = tracing.root_trace_id(tracing.xray_header())
    return {"trace_id": trace_id} if trace_id else {}


def _queue_wait_ms(message: dict, now) -> float | None:
    """Cuánto esperó la solicitud en la cola (el mensaje trae la hora en que la API la aceptó)."""
    created = message.get("created_at")
    if not created:
        return None
    return max((now() - datetime.fromisoformat(created)).total_seconds() * 1000, 0)


def _emit_metrics(message, outcome, extra, total_ms, first_text_ms, queue_wait_ms) -> None:
    """Métricas propias (EMF): resultado, latencias por tramo y tokens."""
    values = {"Requests": (1, "Count"), "TotalLatencyMs": (total_ms, "Milliseconds")}
    if first_text_ms is not None:
        values["FirstTextMs"] = (first_text_ms, "Milliseconds")
    if queue_wait_ms is not None:
        values["QueueWaitMs"] = (queue_wait_ms, "Milliseconds")
    usage = extra.get("usage") or {}
    for key, name in (("input_tokens", "InputTokens"), ("output_tokens", "OutputTokens")):
        if usage.get(key):
            values[name] = (float(usage[key]), "Count")
    properties = {
        "request_id": message["request_id"],
        "profile": message["profile"],
        "role": message["role"],
        "error_code": extra.get("error_code"),
        "trace_id": tracing.root_trace_id(tracing.xray_header()),
    }
    metrics.emit(values, {"Outcome": outcome}, {k: v for k, v in properties.items() if v})


def process(message: dict, deps: Deps, *, clock=time.monotonic, now=requests_store.now_utc) -> str:
    """Procesa una solicitud y devuelve su estado final (o 'Skipped' si ya se atendió)."""
    user_id, request_id = message["user_id"], message["request_id"]
    try:  # SQS entrega al menos una vez: solo se atiende lo que sigue En cola
        requests_store.update_request(
            deps.table,
            user_id,
            request_id,
            {"status": "Processing", "phase": "Processing", **_trace_fields()},
            only_if_status="Queued",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return "Skipped"
        raise

    payload = {
        "prompt": message["prompt"],
        "profile": message["profile"],
        "role": message["role"],
        "user_id": user_id,
        "session_id": message["session_id"],
        "request_id": request_id,  # une la traza del agente con DynamoDB y los logs
    }
    started = clock()
    deadline, last_flush = started + DEADLINE_SECONDS, started
    queue_wait_ms = _queue_wait_ms(message, now)
    first_text_ms = None
    parts: list[str] = []
    outcome, extra = None, {}
    try:
        response = deps.runtime.invoke_agent_runtime(
            agentRuntimeArn=deps.runtime_arn,
            runtimeSessionId=message["session_id"],
            payload=json.dumps(payload).encode(),
            contentType="application/json",
            # Continúa la traza de la Lambda en el agente y agrupa por conversación.
            **tracing.runtime_trace_kwargs(message["session_id"]),
        )
        for event in stream.iter_events(response["response"]):
            if clock() > deadline:
                outcome, extra = "Failed", {"error_code": "timeout"}
                break
            kind = event.get("type")
            if kind == "status":
                requests_store.update_request(
                    deps.table, user_id, request_id, {"phase": event["status"]}
                )
            elif kind in ("text", "no_source"):
                if first_text_ms is None:
                    first_text_ms = (clock() - started) * 1000
                parts.append(event["text"])
                if clock() - last_flush >= FLUSH_SECONDS:
                    requests_store.update_request(
                        deps.table,
                        user_id,
                        request_id,
                        {"text": "".join(parts), "phase": "Writing"},
                    )
                    last_flush = clock()
            elif kind == "blocked":
                outcome = "Blocked"
            elif kind == "done":
                outcome = "Completed"
                extra = {
                    "citations": _decimals(event.get("citations", [])),
                    "no_source": bool(event.get("no_source")),
                    "truncated": bool(event.get("truncated")),
                    "usage": _decimals(event.get("usage", {})),
                }
            elif kind == "error":
                outcome, extra = "Failed", {"error_code": event.get("code", "agent_failed")}
                break
        if outcome is None:  # el stream terminó sin evento final
            outcome, extra = "Failed", {"error_code": "incomplete_stream"}
    except Exception as error:
        logger.exception("orchestration_failed request_id=%s", request_id)
        outcome, extra = "Failed", {"error_code": type(error).__name__}

    text = "".join(parts)
    if outcome == "Completed":
        text = formatting.final_text(
            text, extra.get("citations", []), extra.get("truncated", False)
        )
    elif outcome == "Blocked":
        text = text.strip() or DEFAULT_BLOCKED
    else:
        text = ""  # UC-004 postcondiciones: no se guarda como respuesta válida
    _finish(deps, message, outcome, {**extra, "text": text}, now)
    _emit_metrics(message, outcome, extra, (clock() - started) * 1000, first_text_ms, queue_wait_ms)
    return outcome


def handler(event, _context):
    deps = _deps()
    for record in event["Records"]:
        try:
            process(json.loads(record["body"]), deps)
        except Exception:
            # Un mensaje que ni siquiera se puede procesar no se reintenta: iría a la cola de errores.
            logger.exception("record_failed message_id=%s", record.get("messageId"))
            raise
    return {"batchItemFailures": []}

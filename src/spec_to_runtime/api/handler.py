"""API HTTP de la demo (UC-001, UC-004, UC-005, UC-006, UC-007 y UC-003).

API Gateway valida el JWT de Cognito antes de llegar aquí; el usuario y el rol salen de sus
claims, nunca del cuerpo de la petición.
"""

import functools
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import boto3
from botocore.config import Config

from spec_to_runtime.common import quota, requests_store

logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 500  # UC-004 BR-001
PROFILES = {"Basic", "Technical", "General"}
SESSIONS_PAGE = 20  # UC-006 A4
SYNC_TIMEOUT_SECONDS = 25  # API Gateway corta a los 30 s


@dataclass
class Deps:
    table: object
    usage_client: object
    sqs: object
    lambda_client: object
    queue_url: str
    usage_table: str
    sync_function: str
    project_cap: int


@functools.cache
def _deps() -> Deps:
    region = os.environ.get("AWS_REGION", "us-east-1")
    return Deps(
        table=boto3.resource("dynamodb", region_name=region).Table(os.environ["REQUESTS_TABLE"]),
        usage_client=boto3.client("dynamodb", region_name=region),
        sqs=boto3.client("sqs", region_name=region),
        lambda_client=boto3.client(
            "lambda",
            region_name=region,
            config=Config(read_timeout=SYNC_TIMEOUT_SECONDS, retries={"max_attempts": 1}),
        ),
        queue_url=os.environ["QUEUE_URL"],
        usage_table=os.environ["USAGE_TABLE"],
        sync_function=os.environ["SYNC_FUNCTION"],
        project_cap=int(os.environ.get("PROJECT_CAP", quota.PROJECT_CAP)),
    )


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def _error(status: int, code: str, message: str, **extra) -> dict:
    return _response(status, {"code": code, "message": message, **extra})


def _identity(event: dict) -> tuple[str, str]:
    """(user_id, role). El rol Ponente sale del grupo de Cognito (UC-001 BR-003)."""
    claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    groups = re.findall(r"[\w-]+", str(claims.get("cognito:groups", "")))
    return claims["sub"], "Speaker" if "Ponente" in groups else "Participant"


def _body(event: dict) -> dict:
    try:
        body = json.loads(event.get("body") or "{}")
    except TypeError, ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def submit_question(event: dict, now: datetime | None = None) -> dict:
    """UC-004 pasos 2 a 5: valida, cuenta la consulta, la guarda y la encola."""
    deps, now = _deps(), now or requests_store.now_utc()
    user_id, role = _identity(event)
    body = _body(event)

    prompt = str(body.get("prompt", "")).strip()
    if not 1 <= len(prompt) <= MAX_PROMPT_CHARS:
        return _error(400, "invalid_prompt", "La pregunta debe tener entre 1 y 500 caracteres.")
    profile = body.get("profile", "General")
    if profile not in PROFILES:
        return _error(400, "invalid_profile", "El perfil debe ser Basic, Technical o General.")

    # La sesión la crea el servidor y debe ser del usuario: una sesión ajena compartiría contexto.
    session_id, context_expired = body.get("session_id"), False
    if session_id:
        last = requests_store.session_last_activity(deps.table, user_id, session_id)
        if last is None:
            return _error(404, "session_not_found", "La conversación no existe.")
        if now - last > timedelta(hours=requests_store.SESSION_IDLE_HOURS):  # UC-005 A2
            session_id, context_expired = None, True
    session_id = session_id or requests_store.new_session_id()
    request_id = requests_store.new_request_id(now)
    item = requests_store.build_item(
        user_id=user_id, request_id=request_id, session_id=session_id, prompt=prompt,
        profile=profile, role=role, now=now,
    )  # fmt: skip

    try:
        quota.reserve(deps.usage_client, deps.usage_table, user_id, role, now, deps.project_cap)
    except quota.LimitReachedError as limit:  # UC-004 A2: se registra sin consultar al agente
        rejected = {
            **item,
            "status": "Rejected",
            "phase": "Rejected",
            "error_code": f"{limit.kind}_limit",
        }
        requests_store.put_request(deps.table, rejected)
        message = (
            "Se alcanzó el límite de preguntas del proyecto."
            if limit.kind == "project"
            else "Alcanzaste tu límite de preguntas de hoy."
        )
        return _error(
            429,
            f"{limit.kind}_limit",
            message,
            resets_at=quota.next_reset(now),
            request_id=request_id,
        )

    requests_store.put_request(deps.table, item)
    try:
        deps.sqs.send_message(
            QueueUrl=deps.queue_url,
            MessageBody=json.dumps(
                {
                    "user_id": user_id,
                    "request_id": request_id,
                    "session_id": session_id,
                    "prompt": prompt,
                    "profile": profile,
                    "role": role,
                    "day": item["day"],
                }
            ),
        )
    except Exception:
        logger.exception("enqueue_failed request_id=%s", request_id)
        requests_store.update_request(
            deps.table,
            user_id,
            request_id,
            {"status": "Failed", "phase": "Failed", "error_code": "enqueue_failed"},
        )
        quota.release(deps.usage_client, deps.usage_table, user_id, item["day"])
        return _error(503, "unavailable", "No se pudo enviar la pregunta. Inténtalo de nuevo.")

    return _response(
        202,
        {
            "request_id": request_id,
            "session_id": session_id,
            "status": "Queued",
            "context_expired": context_expired,
        },
    )


def get_request(event: dict) -> dict:
    user_id, _ = _identity(event)
    item = requests_store.get_request(_deps().table, user_id, event["pathParameters"]["request_id"])
    if item is None:
        return _error(404, "not_found", "La consulta no existe.")
    return _response(200, requests_store.public_view(item))


def list_sessions(event: dict) -> dict:
    """UC-006 pasos 3 y A4: conversaciones del usuario, la más reciente primero."""
    user_id, _ = _identity(event)
    sessions: dict[str, dict] = {}
    for item in requests_store.user_requests(_deps().table, user_id):  # de más nueva a más vieja
        entry = sessions.setdefault(
            item["session_id"],
            {
                "session_id": item["session_id"],
                "last_activity_at": item["created_at"],
                "questions": 0,
            },
        )
        entry["questions"] += 1
        entry["first_question"] = item["prompt"]  # queda la más antigua
        entry["started_at"] = item["created_at"]
    ordered = sorted(sessions.values(), key=lambda s: s["last_activity_at"], reverse=True)
    return _response(
        200, {"sessions": ordered[:SESSIONS_PAGE], "has_more": len(ordered) > SESSIONS_PAGE}
    )


def get_session(event: dict) -> dict:
    user_id, _ = _identity(event)
    session_id = event["pathParameters"]["session_id"]
    items = [
        i
        for i in requests_store.user_requests(_deps().table, user_id)
        if i["session_id"] == session_id
    ]
    if not items:
        return _error(404, "not_found", "La conversación no existe.")
    return _response(
        200,
        {
            "session_id": session_id,
            "items": [requests_store.public_view(i) for i in reversed(items)],
        },
    )


def sync_documents(event: dict) -> dict:
    """UC-003 pasos 1 y 2 y A1: solo el Ponente sincroniza."""
    _, role = _identity(event)
    if role != "Speaker":
        return _error(403, "forbidden", "Solo el Ponente puede sincronizar los documentos.")
    payload = {"action": "status"} if event["routeKey"].startswith("GET") else {}
    try:
        result = _deps().lambda_client.invoke(
            FunctionName=_deps().sync_function, Payload=json.dumps(payload).encode()
        )
        return _response(200, json.loads(result["Payload"].read()))
    except Exception:
        logger.exception("sync_invoke_failed")
        return _error(
            202,
            "sync_running",
            "La sincronización sigue en curso; consulta el estado en unos segundos.",
        )


ROUTES = {
    "POST /questions": submit_question,
    "GET /requests/{request_id}": get_request,
    "GET /sessions": list_sessions,
    "GET /sessions/{session_id}": get_session,
    "POST /admin/sync": sync_documents,
    "GET /admin/sync": sync_documents,
}


def handler(event, _context):
    route = ROUTES.get(event.get("routeKey", ""))
    if route is None:
        return _error(404, "not_found", "Ruta no encontrada.")
    try:
        return route(event)
    except Exception:
        logger.exception("api_failed route=%s", event.get("routeKey"))
        return _error(500, "internal_error", "Ocurrió un error inesperado.")

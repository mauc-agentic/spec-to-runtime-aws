"""Solicitudes en DynamoDB (entidades AGENT_REQUEST y AGENT_RESULT, UC-004 y UC-006).

La clave es (user_id, request_id): el usuario siempre sale del token, así que ninguna consulta
puede tocar datos de otra persona (NFR-009, UC-006 BR-001).
"""

import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from boto3.dynamodb.conditions import Attr, Key

from spec_to_runtime.common.quota import local_day

TTL_DAYS = 30
SESSION_IDLE_HOURS = 24  # UC-005 BR-002
FINAL_STATUSES = {"Completed", "Blocked", "Failed", "Rejected"}


def new_request_id(now: datetime | None = None) -> str:
    """Ordenable por fecha, para que las consultas de un usuario salgan cronológicas."""
    now = now or datetime.now(UTC)
    return f"{int(now.timestamp() * 1000):013d}-{uuid.uuid4().hex[:12]}"


def new_session_id() -> str:
    return "sess-" + uuid.uuid4().hex  # AgentCore exige al menos 33 caracteres


def build_item(
    *, user_id, request_id, session_id, prompt, profile, role, now, status="Queued"
) -> dict:
    return {
        "user_id": user_id,
        "request_sk": request_id,
        "request_id": request_id,
        "session_id": session_id,
        "prompt": prompt,
        "profile": profile,
        "role": role,
        "status": status,
        "phase": status,
        "text": "",
        "day": local_day(now),
        "created_at": now.isoformat(),
        "expires_at": int(now.timestamp()) + TTL_DAYS * 86400,
    }


def put_request(table, item: dict) -> None:
    table.put_item(Item=item, ConditionExpression="attribute_not_exists(request_sk)")


def get_request(table, user_id: str, request_id: str) -> dict | None:
    return table.get_item(Key={"user_id": user_id, "request_sk": request_id}).get("Item")


def update_request(
    table, user_id: str, request_id: str, fields: dict, only_if_status: str | None = None
):
    names = {f"#{k}": k for k in fields}
    values = {f":{k}": v for k, v in fields.items()}
    kwargs = {
        "Key": {"user_id": user_id, "request_sk": request_id},
        "UpdateExpression": "SET " + ", ".join(f"#{k} = :{k}" for k in fields),
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
    }
    if only_if_status:
        kwargs["ConditionExpression"] = Attr("status").eq(only_if_status)
    table.update_item(**kwargs)


def user_requests(table, user_id: str, limit: int = 200) -> list[dict]:
    """Las consultas de un usuario, de la más reciente a la más antigua."""
    page = table.query(
        KeyConditionExpression=Key("user_id").eq(user_id), ScanIndexForward=False, Limit=limit
    )
    return page.get("Items", [])


def session_last_activity(table, user_id: str, session_id: str) -> datetime | None:
    """Última actividad de una sesión del usuario; None si la sesión no es suya o no existe."""
    for item in user_requests(table, user_id):
        if item["session_id"] == session_id:
            return datetime.fromisoformat(item["created_at"])
    return None


def public_view(item: dict, include_trace: bool = False) -> dict:
    """Solo lo que el navegador necesita; nunca el identificador del usuario.

    El identificador de traza solo se entrega al Ponente, para abrir la traza en CloudWatch.
    """
    keys = (
        "request_id", "session_id", "prompt", "profile", "status", "phase", "text",
        "citations", "truncated", "no_source", "error_code", "created_at", "completed_at",
    )  # fmt: skip
    keys = (*keys, "trace_id") if include_trace else keys
    return {k: _plain(item[k]) for k in keys if k in item}


def _plain(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def now_utc() -> datetime:
    return datetime.fromtimestamp(time.time(), UTC)

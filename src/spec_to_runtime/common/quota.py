"""Cuotas de uso (NFR-013, UC-004 BR-005 y BR-006, UC-007 BR-007).

Cada consulta aceptada reserva una unidad del contador del usuario y otra del contador global
en una sola transacción: o entran las dos o no entra ninguna.
"""

from datetime import UTC, datetime, timedelta, timezone

from botocore.exceptions import ClientError

# El evento es en Colombia (UTC-5, sin horario de verano): el "día" de las cuotas es el local.
LOCAL_TZ = timezone(timedelta(hours=-5))
DAILY_LIMITS = {"Participant": 25, "Speaker": 100}
PROJECT_CAP = 3000
GLOBAL_KEY = ("GLOBAL", "TOTAL")
COUNTER_TTL_DAYS = 30


class LimitReachedError(Exception):
    """kind es 'daily' (tope del usuario) o 'project' (tope global de 3.000)."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


def local_day(now: datetime) -> str:
    return now.astimezone(LOCAL_TZ).date().isoformat()


def next_reset(now: datetime) -> str:
    """Medianoche local siguiente, en UTC (para decir cuándo vuelven a estar disponibles)."""
    local = now.astimezone(LOCAL_TZ)
    midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(UTC).isoformat()


def _key(scope: str, usage_date: str) -> dict:
    return {"scope": {"S": scope}, "usage_date": {"S": usage_date}}


def _increment(table: str, key: dict, limit: int, expires_at: int) -> dict:
    return {
        "Update": {
            "TableName": table,
            "Key": key,
            "UpdateExpression": "SET request_count = if_not_exists(request_count, :zero) + :one, "
            "expires_at = :exp",
            "ConditionExpression": "attribute_not_exists(request_count) OR request_count < :limit",
            "ExpressionAttributeValues": {
                ":zero": {"N": "0"},
                ":one": {"N": "1"},
                ":limit": {"N": str(limit)},
                ":exp": {"N": str(expires_at)},
            },
        }
    }


def reserve(
    client, table: str, user_id: str, role: str, now: datetime, project_cap: int = PROJECT_CAP
):
    """Reserva una consulta o lanza LimitReachedError."""
    expires_at = int(now.timestamp()) + COUNTER_TTL_DAYS * 86400
    items = [
        _increment(table, _key(f"USER#{user_id}", local_day(now)), DAILY_LIMITS[role], expires_at),
        _increment(table, _key(*GLOBAL_KEY), project_cap, expires_at),
    ]
    try:
        client.transact_write_items(TransactItems=items)
    except ClientError as error:
        if error.response["Error"]["Code"] != "TransactionCanceledException":
            raise
        reasons = [r.get("Code") for r in error.response.get("CancellationReasons", [])]
        # El límite global tiene prioridad: es el que protege el presupuesto.
        if len(reasons) > 1 and reasons[1] == "ConditionalCheckFailed":
            raise LimitReachedError("project") from error
        raise LimitReachedError("daily") from error


def release(client, table: str, user_id: str, day: str) -> None:
    """Devuelve la unidad de una consulta fallida o rechazada (UC-004 BR-006)."""
    items = [
        {
            "Update": {
                "TableName": table,
                "Key": key,
                "UpdateExpression": "SET request_count = request_count - :one",
                "ConditionExpression": "request_count > :zero",
                "ExpressionAttributeValues": {":one": {"N": "1"}, ":zero": {"N": "0"}},
            }
        }
        for key in (_key(f"USER#{user_id}", day), _key(*GLOBAL_KEY))
    ]
    try:
        client.transact_write_items(TransactItems=items)
    except ClientError as error:
        if error.response["Error"]["Code"] != "TransactionCanceledException":
            raise

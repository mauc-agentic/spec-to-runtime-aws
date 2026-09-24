"""Top 10 de preguntas para el Ponente (UC-007).

El modelo solo asigna cada pregunta a un tema por su identificador; los conteos, los
porcentajes y el orden los calcula el código, para que las cifras sean exactas
(UC-007 BR-003, BR-004 y BR-006).
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from boto3.dynamodb.conditions import Attr, Key

from spec_to_runtime.common.quota import LOCAL_TZ

MAX_QUESTIONS = 1000
QUESTION_LIMIT = 200
TOP = 10
OTHERS = "Otros"

_CLASSIFY_PROMPT = """Agrupa estas preguntas de una audiencia en temas.
Devuelve SOLO un JSON con la forma {{"topics": [{{"name": "...", "ids": [1, 2]}}]}}.
Reglas: cada id aparece en exactamente un tema; nombres de máximo 8 palabras, en español;
junta preguntas parecidas; no inventes ids.

Preguntas:
{questions}"""


@dataclass(frozen=True)
class Question:
    id: int
    text: str
    no_source: bool
    created_at: str


@dataclass(frozen=True)
class Topic:
    name: str
    count: int
    share: float
    example: str
    no_source: int
    latest: str


def local_days(start: datetime, end: datetime) -> list[str]:
    """Días (hora de Colombia) entre dos instantes.

    Las preguntas se guardan con el día local (índice by_day); buscar por fecha UTC no encuentra
    nada por la tarde-noche colombiana, cuando en UTC ya es el día siguiente.
    """
    first, last = start.astimezone(LOCAL_TZ).date(), end.astimezone(LOCAL_TZ).date()
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def fetch_questions(table, since: datetime | None, now: datetime | None = None) -> list[Question]:
    """Preguntas de participantes ya respondidas, en orden cronológico (índice by_day)."""
    now = now or datetime.now(UTC)
    start = since or now - timedelta(days=30)
    days = local_days(start, now)
    rows = []
    for day in days:
        kwargs = {
            "IndexName": "by_day",
            "KeyConditionExpression": Key("day").eq(day) & Key("created_at").gte(start.isoformat()),
            "FilterExpression": Attr("role").eq("Participant") & Attr("status").eq("Completed"),
        }
        while True:
            page = table.query(**kwargs)
            rows.extend(page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    rows.sort(key=lambda r: r["created_at"])
    rows = rows[-MAX_QUESTIONS:]
    return [
        Question(
            i, str(r["prompt"])[:QUESTION_LIMIT], bool(r.get("no_source", False)), r["created_at"]
        )
        for i, r in enumerate(rows, start=1)
    ]


def parse_topics(raw: str, questions: list[Question]) -> dict[str, list[Question]]:
    """Cada pregunta queda en un solo tema; lo no asignado va a 'Otros' (BR-003)."""
    by_id = {q.id: q for q in questions}
    try:
        data = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
        entries = data["topics"]
    except ValueError, KeyError, TypeError:
        entries = []
    grouped: dict[str, list[Question]] = {}
    seen: set[int] = set()
    for entry in entries:
        name = str(entry.get("name", "")).strip()[:80] or OTHERS
        for qid in entry.get("ids", []):
            if isinstance(qid, int) and qid in by_id and qid not in seen:
                seen.add(qid)
                grouped.setdefault(name, []).append(by_id[qid])
    leftovers = [q for q in questions if q.id not in seen]
    if leftovers:
        grouped.setdefault(OTHERS, []).extend(leftovers)
    return grouped


def rank_topics(grouped: dict[str, list[Question]], total: int) -> list[Topic]:
    """Orden por cantidad; en empate gana la pregunta más reciente (BR-004). Máximo diez."""
    topics = []
    for name, items in grouped.items():
        latest = max(items, key=lambda q: q.created_at)
        topics.append(
            Topic(
                name=name,
                count=len(items),
                share=len(items) / total * 100,
                example=latest.text,
                no_source=sum(q.no_source for q in items),
                latest=latest.created_at,
            )
        )
    topics.sort(key=lambda t: (t.count, t.latest), reverse=True)
    return topics[:TOP]


def format_report(topics: list[Topic], total: int, period: str) -> str:
    """Informe con posición, tema, cantidad, porcentaje, ejemplo y sin fuente (BR-006)."""
    lines = [f"**Top {len(topics)} de preguntas** · {period} · {total} preguntas analizadas", ""]
    for position, t in enumerate(topics, start=1):
        lines.append(
            f"{position}. **{t.name}** — {t.count} preguntas ({t.share:.0f} %), "
            f"{t.no_source} sin fuente en el repositorio\n   Ejemplo: «{t.example}»"
        )
    return "\n".join(lines)


def top_questions_report(
    *,
    table,
    classify: Callable[[str], str],
    period_hours: int = 0,
    now: datetime | None = None,
) -> str:
    """Genera el informe completo (flujo principal y A4-A6 de UC-007)."""
    now = now or datetime.now(UTC)
    since = now - timedelta(hours=period_hours) if period_hours > 0 else None
    period = f"últimas {period_hours} horas" if since else "todo el evento hasta ahora"
    questions = fetch_questions(table, since, now)
    if not questions:
        return (
            "No encontré preguntas de participantes en ese periodo. "
            "Las preguntas del ponente no cuentan. Prueba con un periodo más amplio."
        )
    listing = "\n".join(f"{q.id}. {q.text}" for q in questions)
    grouped = parse_topics(classify(_CLASSIFY_PROMPT.format(questions=listing)), questions)
    return format_report(rank_topics(grouped, len(questions)), len(questions), period)

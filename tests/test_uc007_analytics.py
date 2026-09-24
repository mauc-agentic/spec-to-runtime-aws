"""UC-007 Consultar top 10 de preguntas: conteos exactos calculados por el código."""

import json
from datetime import UTC, datetime

from spec_to_runtime.agent import analytics

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def _row(i, text=None, no_source=False, minute=0):
    return {
        "user_id": f"secreto-{i}",
        "prompt": text or f"pregunta {i}",
        "no_source": no_source,
        "created_at": f"2026-09-26T10:{minute:02d}:00+00:00",
        "day": "2026-09-26",
    }


class FakeTable:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def query(self, **_kw):
        self.calls += 1
        if self.calls == 1:
            return {"Items": self.rows[:2], "LastEvaluatedKey": {"k": 1}}
        return {"Items": self.rows[2:]}


def _questions(n):
    return [
        analytics.Question(i, f"q{i}", False, f"2026-09-26T10:{i:02d}:00+00:00")
        for i in range(1, n + 1)
    ]


def test_uc007_br003_each_question_belongs_to_exactly_one_topic():
    qs = _questions(4)
    raw = json.dumps({"topics": [{"name": "A", "ids": [1, 2]}, {"name": "B", "ids": [2, 3, 99]}]})
    grouped = analytics.parse_topics(raw, qs)
    assert [q.id for q in grouped["A"]] == [1, 2]
    assert [q.id for q in grouped["B"]] == [3]  # 2 ya estaba en A; 99 no existe
    assert [q.id for q in grouped[analytics.OTHERS]] == [4]  # lo no asignado va a Otros
    assert sum(len(v) for v in grouped.values()) == 4


def test_uc007_br003_malformed_model_output_falls_back_to_others():
    grouped = analytics.parse_topics("no es json", _questions(3))
    assert list(grouped) == [analytics.OTHERS] and len(grouped[analytics.OTHERS]) == 3


def test_uc007_br004_ranking_by_count_then_most_recent_and_max_ten():
    qs = _questions(30)
    grouped = {f"T{i}": [qs[i]] for i in range(12)}  # 12 temas de 1 pregunta
    grouped["Grande"] = qs[12:18]
    ranked = analytics.rank_topics(grouped, 30)
    assert ranked[0].name == "Grande" and ranked[0].count == 6
    assert len(ranked) == 10
    assert ranked[1].name == "T11"  # empate: gana la más reciente


def test_uc007_a5_no_questions_gives_a_notice_instead_of_an_empty_report():
    report = analytics.top_questions_report(table=FakeTable([]), classify=lambda _p: "{}", now=NOW)
    assert "No encontré preguntas" in report


def test_uc007_report_shows_totals_period_shares_and_no_source_count():
    rows = [
        _row(1, "¿Qué es AIUP?", minute=1),
        _row(2, "¿Qué es AIUP?", True, 2),
        _row(3, "¿Costo?", minute=3),
    ]
    classify = lambda _p: json.dumps(
        {"topics": [{"name": "AIUP", "ids": [1, 2]}, {"name": "Costos", "ids": [3]}]}
    )
    report = analytics.top_questions_report(
        table=FakeTable(rows), classify=classify, period_hours=2, now=NOW
    )
    assert "3 preguntas analizadas" in report and "últimas 2 horas" in report
    assert "1. **AIUP** — 2 preguntas (67 %), 1 sin fuente" in report
    assert "2. **Costos** — 1 preguntas (33 %)" in report


def test_uc007_br005_report_never_reveals_who_asked():
    rows = [_row(1), _row(2), _row(3)]
    classify = lambda _p: json.dumps({"topics": [{"name": "X", "ids": [1, 2, 3]}]})
    report = analytics.top_questions_report(table=FakeTable(rows), classify=classify, now=NOW)
    assert "secreto-" not in report


def test_uc007_fetch_follows_pagination_and_caps_the_analysis():
    rows = [_row(i, minute=i % 60) for i in range(1, 6)]
    questions = analytics.fetch_questions(FakeTable(rows), NOW.replace(hour=6), NOW)
    assert len(questions) == 5
    assert [q.id for q in questions] == [1, 2, 3, 4, 5]


def test_uc007_br002_the_report_says_when_only_the_most_recent_questions_were_analyzed(monkeypatch):
    monkeypatch.setattr(analytics, "MAX_QUESTIONS", 3)
    classify = lambda _p: json.dumps({"topics": [{"name": "X", "ids": [1, 2, 3]}]})
    capped = analytics.top_questions_report(
        table=FakeTable([_row(i, minute=i) for i in range(1, 6)]), classify=classify, now=NOW
    )
    assert "3 preguntas analizadas" in capped
    assert "Solo se analizaron las 3 preguntas más recientes del periodo" in capped
    within = analytics.top_questions_report(
        table=FakeTable([_row(i, minute=i) for i in range(1, 3)]),
        classify=lambda _p: json.dumps({"topics": [{"name": "X", "ids": [1, 2]}]}),
        now=NOW,
    )
    assert "Solo se analizaron" not in within


def test_uc007_the_search_uses_the_local_day_not_the_utc_day():
    # Sábado 8:00 p. m. en Colombia = domingo 01:00 UTC: las preguntas están guardadas como "26".
    start = datetime(2026, 9, 27, 1, 0, tzinfo=UTC)
    end = datetime(2026, 9, 27, 3, 0, tzinfo=UTC)  # 10:00 p. m. del 26 en Colombia
    assert analytics.local_days(start, end) == ["2026-09-26"]
    assert analytics.local_days(datetime(2026, 9, 25, 12, 0, tzinfo=UTC), end) == [
        "2026-09-25",
        "2026-09-26",
    ]


def test_uc007_a5_the_empty_notice_explains_that_the_speakers_own_questions_do_not_count():
    report = analytics.top_questions_report(table=FakeTable([]), classify=lambda _p: "{}", now=NOW)
    assert "preguntas del ponente no cuentan" in report


def _activity_rows():
    # u1 pregunta 4 veces, u2 dos, u3 una; una bloqueada, una sin fuente; tres perfiles.
    spec = [
        ("secreto-u1", "Basic", "Completed", False, 10), ("secreto-u1", "Basic", "Completed", True, 11),
        ("secreto-u1", "Technical", "Completed", False, 12), ("secreto-u1", "Basic", "Blocked", False, 13),
        ("secreto-u2", "General", "Completed", False, 14), ("secreto-u2", "General", "Completed", False, 15),
        ("secreto-u3", "Technical", "Completed", False, 16),
    ]  # fmt: skip
    return [
        {"user_id": u, "prompt": f"pregunta {i}", "profile": p, "status": st, "no_source": ns,
         "created_at": f"2026-09-26T{h}:00:00+00:00", "day": "2026-09-26"}
        for i, (u, p, st, ns, h) in enumerate(spec)
    ]  # fmt: skip


def test_uc007_activity_report_has_exact_numbers():
    report = analytics.activity_report(table=FakeTable(_activity_rows()), period_hours=6, now=NOW)
    assert "7 preguntas de 3 participantes (2.3 por participante)" in report
    assert "1. Participante 1 — 4 preguntas (57 %)" in report
    assert "2. Participante 2 — 2 preguntas (29 %)" in report
    assert "3. Participante 3 — 1 preguntas (14 %)" in report
    assert "Perfiles elegidos: Básico 3, Técnico 2, General 2" in report
    assert (
        "1 sin fuente en el repositorio" in report and "1 bloqueadas por los guardrails" in report
    )


def test_uc007_br005_activity_report_never_reveals_who_asked():
    report = analytics.activity_report(table=FakeTable(_activity_rows()), period_hours=6, now=NOW)
    assert "secreto-" not in report and "u1" not in report.replace("Participante 1", "")
    assert "anónimos" in report


def test_uc007_activity_report_names_the_busiest_hour_in_local_time():
    rows = _activity_rows()  # 10..16 UTC = 5 a. m. .. 11 a. m. en Colombia, una pregunta por hora
    for row in rows[:3]:
        row["created_at"] = (
            "2026-09-26T13:30:00+00:00"  # tres a las 8:30 a. m. locales (más la de las 13:00 UTC)
        )
    report = analytics.activity_report(table=FakeTable(rows), period_hours=6, now=NOW)
    assert "Hora con más actividad: 8 a. m. (4 preguntas)" in report


def test_uc007_activity_report_with_no_questions_explains_it():
    report = analytics.activity_report(table=FakeTable([]), now=NOW)
    assert "preguntas del ponente no cuentan" in report


def test_uc007_hour_label_uses_the_12_hour_clock():
    assert [analytics.hour_label(h) for h in (0, 8, 12, 15, 23)] == [
        "12 a. m.",
        "8 a. m.",
        "12 p. m.",
        "3 p. m.",
        "11 p. m.",
    ]

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
    questions = analytics.fetch_questions(FakeTable(rows), NOW.replace(hour=0), NOW)
    assert len(questions) == 5
    assert [q.id for q in questions] == [1, 2, 3, 4, 5]

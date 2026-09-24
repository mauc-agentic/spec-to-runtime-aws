"""Orquestador (UC-004): cola -> agente -> DynamoDB, con texto parcial, formato y cuotas."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from spec_to_runtime.common import quota, requests_store
from spec_to_runtime.orchestrator import formatting, stream
from spec_to_runtime.orchestrator import handler as orch
from tests.conftest import counter

NOW = datetime(2026, 9, 26, 15, 0, tzinfo=UTC)
DAY = "2026-09-26"
CITATIONS = [
    {"path": "docs/vision.md", "url": "https://x/docs/vision.md", "excerpt": "e", "score": 0.81}
]


class FakeBody:
    """Imitación del cuerpo del stream: entrega bytes en bloques, como `read1`."""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    def read1(self, _size):
        return self._chunks.pop(0) if self._chunks else b""


def sse(*events, split=False):
    frames = [f"data: {json.dumps(e, ensure_ascii=False)}\n\n".encode() for e in events]
    if split:  # un evento partido en dos bloques, como pasa en la red
        data = b"".join(frames)
        return FakeBody([data[:23], data[23:]])
    return FakeBody(frames)


@pytest.fixture
def setup(aws):
    def make(events=None, runtime_error=None, body=None):
        runtime = MagicMock()
        if runtime_error:
            runtime.invoke_agent_runtime.side_effect = runtime_error
        else:
            runtime.invoke_agent_runtime.return_value = {"response": body or sse(*events)}
        deps = orch.Deps(aws.requests, aws.usage_client, runtime, "usage", "arn:runtime")
        quota.reserve(
            aws.usage_client, "usage", "u1", "Participant", NOW
        )  # lo que hizo la API al aceptarla
        item = requests_store.build_item(
            user_id="u1", request_id="r1", session_id="sess-" + "a" * 32, prompt="¿Qué es AIUP?",
            profile="Basic", role="Participant", now=NOW,
        )  # fmt: skip
        requests_store.put_request(aws.requests, item)
        message = {
            k: item[k]
            for k in ("user_id", "request_id", "session_id", "prompt", "profile", "role", "day")
        }
        return deps, message, aws

    return make


def stored(aws):
    return requests_store.get_request(aws.requests, "u1", "r1")


HAPPY = [
    {"type": "status", "status": "Searching"},
    {"type": "status", "status": "Writing"},
    {"type": "text", "text": "AIUP es "},
    {"type": "text", "text": "una metodología."},
    {"type": "done", "citations": CITATIONS, "no_source": False, "truncated": False, "usage": {"input_tokens": 100, "output_tokens": 50}},
]  # fmt: skip


def test_uc004_main_flow_stores_the_formatted_answer_with_sources(setup):
    deps, message, aws = setup(HAPPY)
    assert orch.process(message, deps, now=lambda: NOW) == "Completed"
    item = stored(aws)
    assert item["status"] == "Completed" and item["phase"] == "Completed"
    assert item["text"].startswith("AIUP es una metodología.")
    assert "**Fuentes**\n- [docs/vision.md](https://x/docs/vision.md)" in item["text"]  # FR-023
    assert (
        item["citations"][0]["path"] == "docs/vision.md" and item["completed_at"] == NOW.isoformat()
    )
    assert counter(aws, "USER#u1", DAY) == 1  # BR-006: una respuesta completada cuenta


def test_uc004_the_agent_is_called_with_the_session_role_and_profile_from_the_queue(setup):
    deps, message, _ = setup(HAPPY)
    orch.process(message, deps, now=lambda: NOW)
    call = deps.runtime.invoke_agent_runtime.call_args.kwargs
    assert call["agentRuntimeArn"] == "arn:runtime" and len(call["runtimeSessionId"]) >= 33
    payload = json.loads(call["payload"])
    assert payload == {
        "prompt": "¿Qué es AIUP?",
        "profile": "Basic",
        "role": "Participant",
        "user_id": "u1",
        "session_id": call["runtimeSessionId"],
    }


def test_uc004_partial_text_and_phases_are_published_while_the_answer_arrives(setup, monkeypatch):
    deps, message, _ = setup(HAPPY)
    updates = []
    real = requests_store.update_request
    monkeypatch.setattr(
        orch.requests_store,
        "update_request",
        lambda t, u, r, f, only_if_status=None: (
            updates.append(dict(f)),
            real(t, u, r, f, only_if_status),
        )[1],
    )
    ticks = iter(
        range(0, 1000, 1)
    )  # el reloj avanza 1 s por lectura: fuerza publicar el texto parcial
    orch.process(message, deps, clock=lambda: next(ticks), now=lambda: NOW)
    assert [u["phase"] for u in updates if set(u) == {"phase"}] == ["Searching", "Writing"]
    partials = [u["text"] for u in updates if "text" in u and u.get("phase") == "Writing"]
    assert partials and partials[0] == "AIUP es "  # el navegador ve el texto crecer


def test_uc004_a2_no_source_completes_with_the_notice_and_no_sources_section(setup):
    events = [
        {"type": "status", "status": "Searching"},
        {"type": "no_source", "text": "No encontré una fuente."},
        {"type": "done", "citations": [], "no_source": True, "usage": {}},
    ]
    deps, message, aws = setup(events)
    assert orch.process(message, deps, now=lambda: NOW) == "Completed"
    item = stored(aws)
    assert (
        item["text"] == "No encontré una fuente."
        and item["no_source"] is True
        and "Fuentes" not in item["text"]
    )


def test_uc004_a6_blocked_answers_keep_the_notice_and_still_count(setup):
    deps, message, aws = setup(
        [
            {"type": "status", "status": "Writing"},
            {"type": "text", "text": "No puedo responder a esta pregunta."},
            {"type": "blocked"},
        ]
    )
    assert orch.process(message, deps, now=lambda: NOW) == "Blocked"
    assert (
        stored(aws)["text"] == "No puedo responder a esta pregunta."
        and stored(aws)["status"] == "Blocked"
    )
    assert counter(aws, "USER#u1", DAY) == 1  # BR-006: bloqueadas cuentan


def test_uc004_a6_a_block_without_text_uses_the_default_notice(setup):
    deps, message, aws = setup([{"type": "blocked"}])
    orch.process(message, deps, now=lambda: NOW)
    assert stored(aws)["text"] == orch.DEFAULT_BLOCKED


def test_uc004_a7_agent_errors_fail_the_request_return_the_quota_and_store_no_answer(setup):
    deps, message, aws = setup(
        [{"type": "text", "text": "parcial"}, {"type": "error", "code": "agent_failed"}]
    )
    assert orch.process(message, deps, now=lambda: NOW) == "Failed"
    item = stored(aws)
    assert (
        item["status"] == "Failed" and item["error_code"] == "agent_failed" and item["text"] == ""
    )
    assert counter(aws, "USER#u1", DAY) == 0 and counter(aws, "GLOBAL", "TOTAL") == 0  # BR-006


def test_uc004_a7_runtime_exceptions_fail_the_request_with_the_error_type(setup):
    deps, message, aws = setup(runtime_error=RuntimeError("throttled"))
    assert orch.process(message, deps, now=lambda: NOW) == "Failed"
    assert stored(aws)["error_code"] == "RuntimeError" and counter(aws, "USER#u1", DAY) == 0


def test_uc004_br007_an_answer_that_takes_over_60_seconds_fails(setup):
    deps, message, aws = setup(HAPPY)
    ticks = iter([0, 0, 61, 62, 63, 64, 65, 66])  # tras el primer evento ya pasaron 61 s
    assert orch.process(message, deps, clock=lambda: next(ticks), now=lambda: NOW) == "Failed"
    assert stored(aws)["error_code"] == "timeout" and counter(aws, "USER#u1", DAY) == 0


def test_uc004_a_stream_that_ends_without_a_final_event_fails(setup):
    deps, message, aws = setup([{"type": "text", "text": "cortado"}])
    assert orch.process(message, deps, now=lambda: NOW) == "Failed"
    assert stored(aws)["error_code"] == "incomplete_stream"


def test_uc004_truncated_answers_say_so(setup):
    events = [
        {"type": "text", "text": "Respuesta larga"},
        {"type": "done", "citations": [], "no_source": False, "truncated": True, "usage": {}},
    ]
    deps, message, aws = setup(events)
    orch.process(message, deps, now=lambda: NOW)
    assert formatting.TRUNCATED_NOTICE in stored(aws)["text"]


def test_sqs_delivers_at_least_once_so_an_attended_request_is_skipped(setup):
    deps, message, aws = setup(HAPPY)
    assert orch.process(message, deps, now=lambda: NOW) == "Completed"
    assert orch.process(message, deps, now=lambda: NOW) == "Skipped"
    assert deps.runtime.invoke_agent_runtime.call_count == 1
    assert counter(aws, "USER#u1", DAY) == 1  # no se cobró dos veces


def test_uc004_the_lambda_entry_point_processes_each_sqs_record(setup, monkeypatch):
    deps, message, aws = setup(HAPPY)
    monkeypatch.setattr(orch, "_deps", lambda: deps)
    result = orch.handler({"Records": [{"messageId": "m1", "body": json.dumps(message)}]}, None)
    assert result == {"batchItemFailures": []} and stored(aws)["status"] == "Completed"


def test_the_stream_reader_reassembles_events_split_across_chunks_and_skips_garbage():
    body = sse({"type": "text", "text": "hola"}, {"type": "done"}, split=True)
    assert [e["type"] for e in stream.iter_events(body)] == ["text", "done"]
    broken = FakeBody([b"data: {no es json\n\n", b'data: {"type": "done"}\n\n'])
    assert [e["type"] for e in stream.iter_events(broken)] == ["done"]


def test_formatting_adds_sources_only_when_there_are_citations():
    assert formatting.final_text(" hola ", [], False) == "hola"
    assert formatting.final_text("hola", CITATIONS, False).endswith(
        "- [docs/vision.md](https://x/docs/vision.md)"
    )

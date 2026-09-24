"""UC-004 Consultar al agente sobre el repositorio (flujo del agente, sin AWS)."""

import asyncio
from types import SimpleNamespace

import pytest

from spec_to_runtime.agent import handler, retrieval
from spec_to_runtime.agent.config import Settings
from spec_to_runtime.agent.profiles import NO_SOURCE_MESSAGE, Profile, Role, system_prompt

SETTINGS = Settings(
    knowledge_base_id="kb", guardrail_id="g", guardrail_version="1", requests_table="t"
)
PAYLOAD = {
    "prompt": "¿Qué es AIUP?",
    "profile": "Basic",
    "role": "Participant",
    "user_id": "u1",
    "session_id": "s1",
}


class FakeAgent:
    def __init__(self, events):
        self._events = events

    async def stream_async(self, _prompt):
        for event in self._events:
            if isinstance(event, Exception):
                raise event
            yield event


def _collect(payload, passages, events):
    calls = {"factory": 0, "retrieve": 0}

    def retrieve_fn(_query):
        calls["retrieve"] += 1
        return passages

    def factory(*_args, **kwargs):
        calls["factory"] += 1
        calls["kwargs"] = kwargs
        return FakeAgent(events)

    async def go():
        return [
            e
            async for e in handler.run(
                payload, SETTINGS, retrieve_fn=retrieve_fn, agent_factory=factory
            )
        ]

    return asyncio.run(go()), calls


def _passages():
    return [
        retrieval.Passage("docs/vision.md", "AIUP es una metodología", 0.8),
        retrieval.Passage("docs/vision.md", "otro fragmento", 0.5),
        retrieval.Passage("docs/requirements.md", "FR-002", 0.6),
    ]


def test_uc004_main_flow_streams_text_and_cites_each_document_once():
    result = SimpleNamespace(stop_reason="end_turn", metrics=None)
    events, calls = _collect(
        PAYLOAD, _passages(), [{"data": "AIUP "}, {"data": "es..."}, {"result": result}]
    )
    types = [e["type"] for e in events]
    assert types == ["status", "status", "text", "text", "done"]
    assert [e["status"] for e in events[:2]] == ["Searching", "Writing"]
    citations = events[-1]["citations"]
    assert [c["path"] for c in citations] == ["docs/vision.md", "docs/requirements.md"]
    assert citations[0]["url"].endswith("/docs/vision.md")
    assert (
        "AIUP es una metodología" in calls["kwargs"]["context"]
    )  # BR-003: respuesta desde el repo


def test_uc004_a5_no_related_documents_never_calls_the_model():
    events, calls = _collect(PAYLOAD, [], [])
    assert events[-2] == {"type": "no_source", "text": NO_SOURCE_MESSAGE}
    assert events[-1]["no_source"] is True
    assert calls["factory"] == 0


def test_uc004_a6_guardrail_intervention_is_reported_as_blocked():
    result = SimpleNamespace(stop_reason="guardrail_intervened", metrics=None)
    events, _ = _collect(PAYLOAD, _passages(), [{"data": "..."}, {"result": result}])
    assert events[-1] == {"type": "blocked"}


def test_uc004_a7_agent_failure_is_reported_so_the_user_can_retry():
    events, _ = _collect(PAYLOAD, _passages(), [RuntimeError("boom")])
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "agent_failed"


@pytest.mark.parametrize(
    "change",
    [
        {"prompt": ""},
        {"prompt": "x" * 501},
        {"profile": "Otro"},
        {"role": "Admin"},
        {"user_id": ""},
        {"session_id": None},
    ],
)
def test_uc004_br001_invalid_requests_are_rejected_before_anything_else(change):
    events, calls = _collect({**PAYLOAD, **change}, _passages(), [])
    assert events == [{"type": "error", "code": "invalid_request", "message": events[0]["message"]}]
    assert calls["retrieve"] == 0 and calls["factory"] == 0


def test_uc004_br001_boundary_of_500_characters_is_accepted():
    parsed = handler.parse_payload({**PAYLOAD, "prompt": "x" * 500})
    assert len(parsed["prompt"]) == 500


def test_uc007_speaker_skips_retrieval_and_uses_tools_instead():
    result = SimpleNamespace(stop_reason="end_turn", metrics=None)
    payload = {**PAYLOAD, "role": "Speaker", "prompt": "top de preguntas"}
    events, calls = _collect(payload, _passages(), [{"result": result}])
    assert calls["retrieve"] == 0
    assert events[-1]["type"] == "done" and events[-1]["citations"] == []


def test_uc002_each_profile_shapes_the_answer_differently():
    basic = system_prompt(Profile.BASIC, Role.PARTICIPANT)
    technical = system_prompt(Profile.TECHNICAL, Role.PARTICIPANT)
    general = system_prompt(Profile.GENERAL, Role.PARTICIPANT)
    assert "paso a paso" in basic and "trade-offs" in technical and "sin jerga" in general
    assert len({basic, technical, general}) == 3


def test_uc007_br001_speaker_instructions_only_for_the_speaker():
    assert "top_preguntas" in system_prompt(Profile.GENERAL, Role.SPEAKER)
    assert "top_preguntas" not in system_prompt(Profile.GENERAL, Role.PARTICIPANT)


def test_uc004_retrieval_filters_low_relevance_and_maps_s3_paths():
    class KB:
        def retrieve(self, **_kw):
            return {
                "retrievalResults": [
                    {
                        "content": {"text": "a"},
                        "location": {"s3Location": {"uri": "s3://b/docs/x.md"}},
                        "score": 0.9,
                    },
                    {
                        "content": {"text": "b"},
                        "location": {"s3Location": {"uri": "s3://b/docs/y.md"}},
                        "score": 0.1,
                    },
                ]
            }

    passages = retrieval.retrieve(KB(), "kb", "q", 4, 0.3)
    assert [p.source_path for p in passages] == ["docs/x.md"]

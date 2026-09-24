"""UC-004 Consultar al agente sobre el repositorio (flujo del agente, sin AWS)."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

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


class FakeState(dict):
    """Imita `agent.state` de Strands (donde `top_preguntas` deja el informe)."""


class FakeAgent:
    def __init__(self, events, state=None):
        self._events = events
        self.state = state

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


def test_uc004_a7_agent_failure_is_reported_so_the_user_can_retry(caplog):
    events, _ = _collect(PAYLOAD, _passages(), [RuntimeError("boom")])
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "agent_failed"
    # NFR-007: el detalle queda en los logs aunque el participante solo vea el tipo de error
    assert "agent_failed session_id=s1" in caplog.text and "boom" in caplog.text


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


@pytest.mark.parametrize("profile", list(Profile))
def test_uc004_br003_every_profile_forbids_inventing_reasons(profile):
    prompt = system_prompt(profile, Role.PARTICIPANT)
    assert "SOLO en los fragmentos" in prompt and "no infieras" in prompt


def test_uc004_br005_hitting_the_length_limit_truncates_instead_of_failing():
    from strands.types.exceptions import MaxTokensReachedException

    events, _ = _collect(
        PAYLOAD, _passages(), [{"data": "texto largo..."}, MaxTokensReachedException("tope")]
    )
    assert events[-1]["type"] == "done" and events[-1]["truncated"] is True
    assert [e["type"] for e in events].count("error") == 0


def test_uc007_the_report_is_shown_verbatim_and_not_rewritten_by_the_model():
    result = SimpleNamespace(stop_reason="end_turn", metrics=None)
    report = "**Top 2 de preguntas** · 3 preguntas analizadas\n1. **Costos** — 2 preguntas (67 %)"

    def factory(*_a, **_k):
        return FakeAgent([{"result": result}], FakeState(report=report))

    payload = {**PAYLOAD, "role": "Speaker", "prompt": "top de preguntas"}

    async def go():
        return [
            e
            async for e in handler.run(
                payload, SETTINGS, retrieve_fn=lambda _q: [], agent_factory=factory
            )
        ]

    events = asyncio.run(go())
    assert {"type": "text", "text": report} in events
    assert events[-1]["type"] == "done"


def test_uc007_br005_the_report_goes_through_the_guardrail_before_being_shown():
    from spec_to_runtime.agent.toolkit import mask_with_guardrail

    client = MagicMock()
    client.apply_guardrail.return_value = {
        "action": "GUARDRAIL_INTERVENED",
        "outputs": [{"text": "Ejemplo: {EMAIL}"}],
    }
    assert mask_with_guardrail(client, SETTINGS, "Ejemplo: juan@example.com") == "Ejemplo: {EMAIL}"
    call = client.apply_guardrail.call_args.kwargs
    assert call["source"] == "OUTPUT" and call["guardrailIdentifier"] == "g"
    client.apply_guardrail.return_value = {"action": "NONE"}
    assert mask_with_guardrail(client, SETTINGS, "sin datos personales") == "sin datos personales"


def _run_with_agent(agent):
    async def go():
        return [
            e
            async for e in handler.run(
                PAYLOAD,
                SETTINGS,
                retrieve_fn=lambda _q: _passages(),
                agent_factory=lambda *_a, **_k: agent,
            )
        ]

    return asyncio.run(go())


def test_uc005_a4_without_memory_the_answer_continues_and_the_user_is_told():
    result = SimpleNamespace(stop_reason="end_turn", metrics=None)
    agent = FakeAgent([{"data": "Respuesta"}, {"result": result}])
    agent.memory_degraded = True

    events = _run_with_agent(agent)

    types = [e["type"] for e in events]
    assert {"type": "notice", "code": "memory_unavailable"} in events
    assert types.index("notice") < types.index("text")  # el aviso llega antes de la respuesta
    assert types[-1] == "done"  # la consulta no falla


def test_uc005_a4_with_memory_no_notice_is_sent():
    result = SimpleNamespace(stop_reason="end_turn", metrics=None)
    events = _run_with_agent(FakeAgent([{"data": "Respuesta"}, {"result": result}]))
    assert "notice" not in [e["type"] for e in events]


def test_uc005_a4_factory_builds_the_agent_without_memory_when_memory_fails(monkeypatch):
    from spec_to_runtime.agent import factory

    def broken_memory(*_a, **_k):
        raise RuntimeError("AgentCore Memory no responde")

    monkeypatch.setattr(factory, "AgentCoreMemorySessionManager", broken_memory)
    settings = Settings(
        knowledge_base_id="kb", guardrail_id="g", guardrail_version="1",
        requests_table="t", memory_id="mem-1",
    )  # fmt: skip

    agent = factory.build_agent(
        settings, role=Role.PARTICIPANT, profile=Profile.GENERAL, session_id="s", actor_id="u"
    )

    assert getattr(agent, factory.MEMORY_DEGRADED_ATTR) is True


def test_uc005_a4_factory_marks_nothing_when_no_memory_is_configured():
    from spec_to_runtime.agent import factory

    agent = factory.build_agent(
        SETTINGS, role=Role.PARTICIPANT, profile=Profile.GENERAL, session_id="s", actor_id="u"
    )
    assert getattr(agent, factory.MEMORY_DEGRADED_ATTR, False) is False


def test_fr012_the_aws_docs_sources_are_added_to_the_citations_of_the_speaker_answer():
    result = SimpleNamespace(stop_reason="end_turn", metrics=None)
    sources = [
        {
            "path": "Gateway targets",
            "url": "https://docs.aws.amazon.com/x",
            "excerpt": "",
            "score": 0.0,
        }
    ]
    agent = FakeAgent(
        [{"data": "Respuesta"}, {"result": result}], state=FakeState(aws_docs_sources=sources)
    )

    speaker = {**PAYLOAD, "role": "Speaker"}

    async def go():
        return [
            e
            async for e in handler.run(
                speaker, SETTINGS, retrieve_fn=lambda _q: [], agent_factory=lambda *_a, **_k: agent
            )
        ]

    events = asyncio.run(go())
    assert events[-1]["type"] == "done" and events[-1]["citations"] == sources

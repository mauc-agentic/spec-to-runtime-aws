"""Flujo de una consulta al agente (UC-004, UC-005 y UC-007).

Emite eventos simples que la Lambda orquestadora traduce a estados y texto parcial:
status, text, blocked, no_source, done y error.
"""

import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import asdict
from typing import Any

from strands.types.exceptions import MaxTokensReachedException

from spec_to_runtime.agent import retrieval, telemetry
from spec_to_runtime.agent.config import Settings
from spec_to_runtime.agent.factory import (
    MEMORY_DEGRADED_ATTR,
    NOTICE_MEMORY_UNAVAILABLE,
    REPORT_KEY,
)
from spec_to_runtime.agent.profiles import NO_SOURCE_MESSAGE, Profile, Role

logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 500  # UC-004 BR-001


class InvalidRequestError(ValueError):
    """La solicitud no cumple las reglas de entrada."""


def parse_payload(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt", "")).strip()
    if not 1 <= len(prompt) <= MAX_PROMPT_CHARS:
        raise InvalidRequestError("La pregunta debe tener entre 1 y 500 caracteres.")
    try:
        profile = Profile(payload.get("profile", Profile.GENERAL))
        role = Role(payload.get("role", Role.PARTICIPANT))
    except ValueError as error:
        raise InvalidRequestError("Perfil o rol no válido.") from error
    for field in ("user_id", "session_id"):
        if not payload.get(field):
            raise InvalidRequestError(f"Falta {field}.")
    return {
        "prompt": prompt,
        "profile": profile,
        "role": role,
        "user_id": payload["user_id"],
        "session_id": payload["session_id"],
        # Opcional: el orquestador lo envía para unir la traza con DynamoDB y los logs.
        "request_id": str(payload.get("request_id", ""))[:64],
    }


def _usage(result) -> dict[str, int]:
    usage = getattr(getattr(result, "metrics", None), "accumulated_usage", None) or {}
    return {
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
    }


async def run(
    payload: dict[str, Any],
    settings: Settings,
    *,
    retrieve_fn: Callable[..., list[retrieval.Passage]],
    agent_factory: Callable[..., Any],
) -> AsyncIterator[dict[str, Any]]:
    try:
        request = parse_payload(payload)
    except InvalidRequestError as error:
        yield {"type": "error", "code": "invalid_request", "message": str(error)}
        return

    # Trazas: `session.id` agrupa por conversación y `request_id` une la traza con DynamoDB y los logs.
    with telemetry.session_context(request["session_id"]):
        telemetry.annotate(
            request_id=request["request_id"],
            profile=str(request["profile"]),
            role=str(request["role"]),
            prompt_chars=len(request["prompt"]),
        )
        async for event in _answer(request, settings, retrieve_fn, agent_factory):
            yield event


async def _answer(
    request: dict[str, Any],
    settings: Settings,
    retrieve_fn: Callable[..., list[retrieval.Passage]],
    agent_factory: Callable[..., Any],
) -> AsyncIterator[dict[str, Any]]:
    context, citations = "", []
    if request["role"] is Role.PARTICIPANT:
        yield {"type": "status", "status": "Searching"}
        with telemetry.span(
            "rag.retrieve", top_k=settings.retrieval_top_k, min_relevance=settings.min_relevance
        ):
            passages = retrieve_fn(request["prompt"])
            telemetry.annotate(
                passages=len(passages), top_score=max((p.score for p in passages), default=None)
            )
        if not passages:
            # UC-004 A5: sin fuente no se llama al modelo (ahorra costo).
            telemetry.annotate(outcome="no_source")
            yield {"type": "no_source", "text": NO_SOURCE_MESSAGE}
            yield {"type": "done", "citations": [], "no_source": True, "usage": _usage(None)}
            return
        context = retrieval.build_context(passages, settings.repo_url)
        citations = [asdict(c) for c in retrieval.to_citations(passages, settings.repo_url)]

    yield {"type": "status", "status": "Writing"}
    try:
        agent = agent_factory(
            settings,
            role=request["role"],
            profile=request["profile"],
            session_id=request["session_id"],
            actor_id=request["user_id"],
            context=context,
        )
        if getattr(agent, MEMORY_DEGRADED_ATTR, False):
            # UC-005 A4: sin la memoria se responde solo con la pregunta actual, y se avisa.
            telemetry.annotate(memory="unavailable")
            yield {"type": "notice", "code": NOTICE_MEMORY_UNAVAILABLE}
        result = None
        async for event in agent.stream_async(request["prompt"]):
            if "data" in event:
                yield {"type": "text", "text": event["data"]}
            elif "result" in event:
                result = event["result"]
    except MaxTokensReachedException:
        # UC-004 BR-005: el tope de longitud recorta la respuesta; el texto parcial ya se emitió.
        telemetry.annotate(outcome="truncated", citations=len(citations))
        yield {
            "type": "done",
            "citations": citations,
            "no_source": False,
            "truncated": True,
            "usage": _usage(None),
        }
        return
    except Exception as error:
        # NFR-007: el detalle va a CloudWatch; al participante solo le llega el tipo de error.
        logger.exception("agent_failed session_id=%s", request["session_id"])
        telemetry.annotate(outcome="error", error_type=type(error).__name__)
        yield {"type": "error", "code": "agent_failed", "message": type(error).__name__}
        return

    # El informe del top de preguntas se muestra tal cual, sin que el modelo lo reescriba.
    state = getattr(agent, "state", None)
    report = state.get(REPORT_KEY) if state is not None else None
    if report:
        yield {"type": "text", "text": report}

    if result is not None and result.stop_reason == "guardrail_intervened":
        telemetry.annotate(outcome="blocked")
        yield {"type": "blocked"}
        return
    usage = _usage(result)
    telemetry.annotate(
        outcome="completed",
        citations=len(citations),
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
    )
    yield {
        "type": "done",
        "citations": citations,
        "no_source": False,
        "truncated": False,
        "usage": usage,
    }

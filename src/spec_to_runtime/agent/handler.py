"""Flujo de una consulta al agente (UC-004, UC-005 y UC-007).

Emite eventos simples que la Lambda orquestadora traduce a estados y texto parcial:
status, text, blocked, no_source, done y error.
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import asdict
from typing import Any

from spec_to_runtime.agent import retrieval
from spec_to_runtime.agent.config import Settings
from spec_to_runtime.agent.profiles import NO_SOURCE_MESSAGE, Profile, Role

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

    context, citations = "", []
    if request["role"] is Role.PARTICIPANT:
        yield {"type": "status", "status": "Searching"}
        passages = retrieve_fn(request["prompt"])
        if not passages:
            # UC-004 A5: sin fuente no se llama al modelo (ahorra costo).
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
        result = None
        async for event in agent.stream_async(request["prompt"]):
            if "data" in event:
                yield {"type": "text", "text": event["data"]}
            elif "result" in event:
                result = event["result"]
    except Exception as error:  # noqa: BLE001 - UC-004 A7: cualquier fallo se informa y se reintenta
        yield {"type": "error", "code": "agent_failed", "message": type(error).__name__}
        return

    if result is not None and result.stop_reason == "guardrail_intervened":
        yield {"type": "blocked"}
        return
    yield {"type": "done", "citations": citations, "no_source": False, "usage": _usage(result)}

"""Construcción del agente Strands: modelo Nova 2 Lite, guardrails, memoria y herramientas."""

import boto3
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from strands import Agent, tool
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel

from spec_to_runtime.agent import analytics, retrieval
from spec_to_runtime.agent.config import Settings
from spec_to_runtime.agent.profiles import Profile, Role, system_prompt

# El análisis agrupa cientos de preguntas y devuelve identificadores: necesita más salida.
_ANALYSIS_MAX_TOKENS = 6000


def make_model(settings: Settings, max_tokens: int | None = None) -> BedrockModel:
    return BedrockModel(
        model_id=settings.model_id,
        region_name=settings.region,
        max_tokens=max_tokens or settings.max_output_tokens,
        temperature=0.2,
        guardrail_id=settings.guardrail_id,
        guardrail_version=settings.guardrail_version,
        # "sync": el texto solo se emite después de pasar los guardrails (UC-004 BR-004).
        guardrail_stream_processing_mode="sync",
        guardrail_latest_message=True,
    )


def make_classifier(settings: Settings):
    """Llamada aparte al modelo para agrupar preguntas por tema (UC-007)."""
    client = boto3.client("bedrock-runtime", region_name=settings.region)

    def classify(prompt: str) -> str:
        response = client.converse(
            modelId=settings.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": _ANALYSIS_MAX_TOKENS, "temperature": 0},
        )
        return response["output"]["message"]["content"][0]["text"]

    return classify


def speaker_tools(settings: Settings):
    """Herramientas solo para el Ponente (UC-007 BR-001). Los participantes no las reciben."""
    kb_client = boto3.client("bedrock-agent-runtime", region_name=settings.region)
    table = boto3.resource("dynamodb", region_name=settings.region).Table(settings.requests_table)
    classify = make_classifier(settings)

    @tool
    def buscar_documentos(consulta: str) -> str:
        """Busca en los documentos del repositorio y devuelve fragmentos con su enlace."""
        passages = retrieval.retrieve(
            kb_client,
            settings.knowledge_base_id,
            consulta,
            settings.retrieval_top_k,
            settings.min_relevance,
        )
        return retrieval.build_context(passages, settings.repo_url) or "Sin resultados."

    @tool
    def top_preguntas(periodo_horas: int = 0) -> str:
        """Devuelve el top 10 de preguntas más frecuentes de los participantes.

        Args:
            periodo_horas: Horas hacia atrás a analizar; 0 significa todo el evento.
        """
        return analytics.top_questions_report(
            table=table, classify=classify, period_hours=periodo_horas
        )

    return [buscar_documentos, top_preguntas]


def build_agent(
    settings: Settings,
    *,
    role: Role,
    profile: Profile,
    session_id: str,
    actor_id: str,
    context: str = "",
) -> Agent:
    session_manager = None
    if settings.memory_id:
        session_manager = AgentCoreMemorySessionManager(
            AgentCoreMemoryConfig(
                memory_id=settings.memory_id, session_id=session_id, actor_id=actor_id
            ),
            region_name=settings.region,
        )
    return Agent(
        model=make_model(settings),
        # El contexto va en el prompt del sistema y no en el mensaje: así no se guarda en la
        # memoria de la conversación ni infla las siguientes consultas (NFR-012).
        system_prompt=system_prompt(profile, role, context),
        tools=speaker_tools(settings) if role is Role.SPEAKER else [],
        session_manager=session_manager,
        conversation_manager=SlidingWindowConversationManager(
            window_size=settings.context_messages
        ),
        callback_handler=None,
    )

"""Construcción del agente Strands: modelo Nova 2 Lite, guardrails, memoria y herramientas."""

from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from strands import Agent, tool
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel
from strands.types.tools import ToolContext

from spec_to_runtime.agent.config import Settings
from spec_to_runtime.agent.gateway import GatewayClient
from spec_to_runtime.agent.profiles import Profile, Role, system_prompt

REPORT_KEY = "report"  # estado del agente donde `top_preguntas` deja el informe final


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


def speaker_tools(settings: Settings, gateway: GatewayClient | None = None):
    """Herramientas solo para el Ponente (UC-007 BR-001). Los participantes no las reciben.

    Se ejecutan en AgentCore Gateway (FR-012); aquí solo se declaran y se reenvía la llamada.
    """
    gateway = gateway or GatewayClient(settings.gateway_url, settings.region)

    def emit_report(tool_context: ToolContext, report: str) -> str:
        # El informe se muestra tal cual: si el modelo lo reescribe, puede inventar el resumen
        # (ya inventó que "ninguna pregunta tenía fuente"). Se corta el bucle y lo emite el handler.
        tool_context.agent.state.set(REPORT_KEY, report)
        tool_context.invocation_state.setdefault("request_state", {})["stop_event_loop"] = True
        return report

    @tool
    def buscar_documentos(consulta: str) -> str:
        """Busca en los documentos del repositorio y devuelve fragmentos con su enlace."""
        return gateway.call("buscar_documentos", {"consulta": consulta})

    @tool(context="tool_context")
    def top_preguntas(tool_context: ToolContext, periodo_horas: int = 0) -> str:
        """Devuelve el top 10 de preguntas más frecuentes de los participantes.

        Args:
            tool_context: Inyectado por el framework; no lo rellena el modelo.
            periodo_horas: Horas hacia atrás a analizar; 0 significa todo el evento.
        """
        return emit_report(
            tool_context, gateway.call("top_preguntas", {"periodo_horas": periodo_horas})
        )

    @tool(context="tool_context")
    def actividad_participantes(tool_context: ToolContext, periodo_horas: int = 0) -> str:
        """Resumen anónimo de la actividad: cuántas preguntas y participantes hay, quién ha preguntado
        más (sin decir quién es), la hora con más actividad y los perfiles elegidos.

        Args:
            tool_context: Inyectado por el framework; no lo rellena el modelo.
            periodo_horas: Horas hacia atrás a analizar; 0 significa todo el evento.
        """
        return emit_report(
            tool_context, gateway.call("actividad_participantes", {"periodo_horas": periodo_horas})
        )

    return [buscar_documentos, top_preguntas, actividad_participantes]


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

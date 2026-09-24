"""Herramientas del Ponente (FR-012, UC-007), sin depender de Strands.

Las ejecuta la Lambda `tools` detrás de AgentCore Gateway; el agente solo las llama por MCP.
Vive en `agent/` porque comparte configuración y lógica con el agente, pero no importa Strands:
el paquete de las Lambdas no lo incluye.
"""

import boto3

from spec_to_runtime.agent import analytics, retrieval
from spec_to_runtime.agent.config import Settings

# El análisis agrupa cientos de preguntas y devuelve identificadores: necesita más salida.
_ANALYSIS_MAX_TOKENS = 6000

TOOL_NAMES = ("buscar_documentos", "top_preguntas", "actividad_participantes")


def mask_with_guardrail(client, settings: Settings, text: str) -> str:
    """Pasa un texto por el guardrail: enmascara correos y teléfonos y bloquea claves de AWS."""
    response = client.apply_guardrail(
        guardrailIdentifier=settings.guardrail_id,
        guardrailVersion=settings.guardrail_version,
        source="OUTPUT",
        content=[{"text": {"text": text}}],
    )
    if response.get("action") == "GUARDRAIL_INTERVENED" and response.get("outputs"):
        return response["outputs"][0]["text"]
    return text


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


class Toolkit:
    """Las tres herramientas con sus clientes de AWS; se crea una vez por contenedor."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._kb_client = boto3.client("bedrock-agent-runtime", region_name=settings.region)
        self._guard_client = boto3.client("bedrock-runtime", region_name=settings.region)
        self._table = boto3.resource("dynamodb", region_name=settings.region).Table(
            settings.requests_table
        )
        self._classify = make_classifier(settings)

    def run(self, tool: str, arguments: dict) -> str:
        if tool == "buscar_documentos":
            return self._search(str(arguments.get("consulta", "")))
        period = int(arguments.get("periodo_horas") or 0)
        if tool == "top_preguntas":
            report = analytics.top_questions_report(
                table=self._table, classify=self._classify, period_hours=period
            )
        elif tool == "actividad_participantes":
            report = analytics.activity_report(table=self._table, period_hours=period)
        else:
            raise ValueError(f"Herramienta desconocida: {tool}")
        # UC-007 BR-005 y BR-009: el informe sale con los datos personales enmascarados.
        return mask_with_guardrail(self._guard_client, self.settings, report)

    def _search(self, query: str) -> str:
        passages = retrieval.retrieve(
            self._kb_client,
            self.settings.knowledge_base_id,
            query,
            self.settings.retrieval_top_k,
            self.settings.min_relevance,
        )
        return retrieval.build_context(passages, self.settings.repo_url) or "Sin resultados."

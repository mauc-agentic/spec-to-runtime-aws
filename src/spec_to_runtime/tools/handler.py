"""Lambda de herramientas del Ponente, target de AgentCore Gateway (FR-012).

Gateway invoca la función con los argumentos de la herramienta como evento y con el nombre de la
herramienta en `context.client_context.custom["bedrockAgentCoreToolName"]`, con la forma
`<target>___<herramienta>`.
"""

import logging
from functools import cache

from spec_to_runtime.agent.config import Settings
from spec_to_runtime.agent.toolkit import TOOL_NAMES, Toolkit

logger = logging.getLogger(__name__)

TARGET_SEPARATOR = "___"


@cache
def _toolkit() -> Toolkit:
    return Toolkit(Settings.from_env())


def tool_name(context) -> str:
    raw = context.client_context.custom["bedrockAgentCoreToolName"]
    return raw.split(TARGET_SEPARATOR, 1)[-1]


def handler(event, context):
    name = tool_name(context)
    if name not in TOOL_NAMES:
        raise ValueError(f"Herramienta desconocida: {name}")
    logger.info("tool=%s", name)
    return {"report": _toolkit().run(name, event or {})}

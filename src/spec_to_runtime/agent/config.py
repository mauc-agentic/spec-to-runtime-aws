"""Configuración del agente, leída del entorno del runtime (Terraform la inyecta)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    knowledge_base_id: str
    guardrail_id: str
    guardrail_version: str
    requests_table: str
    memory_id: str = ""
    region: str = "us-east-1"
    model_id: str = "us.amazon.nova-2-lite-v1:0"
    repo_url: str = "https://github.com/mauc-agentic/spec-to-runtime-aws/blob/main"
    # UC-004 BR-005: respuesta de unas 600 palabras (~800 tokens).
    max_output_tokens: int = 800
    retrieval_top_k: int = 4
    # Umbral de relevancia; se ajusta con el corpus real (ver docs/charla).
    min_relevance: float = 0.3
    # UC-005 BR-001: 10 interacciones recordadas = 20 mensajes.
    context_messages: int = 20

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        return cls(
            knowledge_base_id=env["KNOWLEDGE_BASE_ID"],
            guardrail_id=env["GUARDRAIL_ID"],
            guardrail_version=env["GUARDRAIL_VERSION"],
            requests_table=env["REQUESTS_TABLE"],
            memory_id=env.get("MEMORY_ID", ""),
            region=env.get("AWS_REGION", "us-east-1"),
            model_id=env.get("MODEL_ID", cls.model_id),
            min_relevance=float(env.get("MIN_RELEVANCE", cls.min_relevance)),
        )

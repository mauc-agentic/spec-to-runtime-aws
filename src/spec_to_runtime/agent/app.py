"""Punto de entrada de AgentCore Runtime (`/invocations` y `/ping` los aporta el SDK)."""

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from spec_to_runtime.agent import handler, retrieval
from spec_to_runtime.agent.config import Settings
from spec_to_runtime.agent.factory import build_agent

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload):
    settings = Settings.from_env()
    kb_client = boto3.client("bedrock-agent-runtime", region_name=settings.region)

    def retrieve_fn(query: str):
        return retrieval.retrieve(
            kb_client,
            settings.knowledge_base_id,
            query,
            settings.retrieval_top_k,
            settings.min_relevance,
        )

    async for event in handler.run(
        payload, settings, retrieve_fn=retrieve_fn, agent_factory=build_agent
    ):
        yield event


if __name__ == "__main__":
    app.run()

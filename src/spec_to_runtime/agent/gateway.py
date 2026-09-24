"""Cliente de AgentCore Gateway para el agente (FR-012).

El Gateway usa autorizador `AWS_IAM`: cada petición MCP se firma con SigV4 con el rol del
Runtime, que es el único con `bedrock-agentcore:InvokeGateway` sobre él.
"""

import json
import uuid

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from strands.tools.mcp import MCPClient

# Nombre del target en Terraform: Gateway antepone `ponente___` al nombre de cada herramienta.
TARGET = "ponente"
_SERVICE = "bedrock-agentcore"


class SigV4HttpxAuth(httpx.Auth):
    """Firma cada petición con las credenciales vigentes del rol (rotan solas en el Runtime)."""

    requires_request_body = True

    def __init__(self, region: str, session: boto3.Session | None = None):
        self._region = region
        self._session = session or boto3.Session()

    def auth_flow(self, request: httpx.Request):
        credentials = self._session.get_credentials().get_frozen_credentials()
        # Se firma solo lo imprescindible: httpx añade después otras cabeceras que romperían la firma.
        signed = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers={
                "Host": request.url.host,
                "Content-Type": request.headers.get("content-type", ""),
            },
        )
        SigV4Auth(credentials, _SERVICE, self._region).add_auth(signed)
        for name in ("Authorization", "X-Amz-Date", "X-Amz-Security-Token"):
            if name in signed.headers:
                request.headers[name] = signed.headers[name]
        yield request


class GatewayError(RuntimeError):
    """El Gateway respondió con un error al ejecutar la herramienta."""


class GatewayClient:
    def __init__(self, url: str, region: str):
        self._url = url
        self._region = region

    def call(self, tool: str, arguments: dict | None = None) -> str:
        """Ejecuta una herramienta del target y devuelve su texto."""
        client = MCPClient(url=self._url, auth_provider=SigV4HttpxAuth(self._region))
        with client:
            result = client.call_tool_sync(str(uuid.uuid4()), f"{TARGET}___{tool}", arguments or {})
        text = "".join(part.get("text", "") for part in result.get("content", []))
        if result.get("status") == "error":
            raise GatewayError(text[:200])
        return unwrap(text)


def unwrap(text: str) -> str:
    """La Lambda responde `{"report": "..."}`; Gateway lo entrega como texto JSON."""
    try:
        data = json.loads(text)
    except ValueError:
        return text
    return str(data["report"]) if isinstance(data, dict) and "report" in data else text

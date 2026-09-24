"""FR-012: las herramientas del Ponente se ejecutan detrás de AgentCore Gateway (UC-007 BR-001)."""

from types import SimpleNamespace

import boto3
import httpx
import pytest

from spec_to_runtime.agent import gateway
from spec_to_runtime.agent.config import Settings
from spec_to_runtime.agent.factory import REPORT_KEY, speaker_tools
from spec_to_runtime.agent.toolkit import Toolkit
from spec_to_runtime.tools import handler as tools_handler

SETTINGS = Settings(
    knowledge_base_id="kb", guardrail_id="g", guardrail_version="1", requests_table="t"
)


class FakeGateway:
    def __init__(self, reply="informe"):
        self.calls = []
        self.reply = reply

    def call(self, tool, arguments=None):
        self.calls.append((tool, arguments))
        return self.reply


def _tool(tools, name):
    return next(t for t in tools if t.tool_name == name)


def _tool_context():
    state = {}
    agent = SimpleNamespace(state=SimpleNamespace(set=state.__setitem__))
    return SimpleNamespace(agent=agent, invocation_state={}), state


def test_uc007_fr012_speaker_tools_call_the_gateway_and_keep_report_verbatim():
    fake = FakeGateway("## Top 10")
    tools = speaker_tools(SETTINGS, fake)
    context, state = _tool_context()

    result = _tool(tools, "top_preguntas")._tool_func(tool_context=context, periodo_horas=6)

    assert result == "## Top 10"
    assert fake.calls == [("top_preguntas", {"periodo_horas": 6})]
    assert state[REPORT_KEY] == "## Top 10"
    assert context.invocation_state["request_state"]["stop_event_loop"] is True


def test_uc007_fr012_search_goes_through_the_gateway_without_stopping_the_loop():
    fake = FakeGateway("[vision.md](https://x)\ntexto")
    tools = speaker_tools(SETTINGS, fake)

    result = _tool(tools, "buscar_documentos")._tool_func(consulta="AIUP")

    assert result.startswith("[vision.md]")
    assert fake.calls == [("buscar_documentos", {"consulta": "AIUP"})]


def test_uc007_fr012_lambda_dispatches_by_gateway_tool_name(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tools_handler,
        "_toolkit",
        lambda: SimpleNamespace(run=lambda n, a: calls.append((n, a)) or "ok"),
    )
    context = SimpleNamespace(
        client_context=SimpleNamespace(
            custom={"bedrockAgentCoreToolName": "ponente___top_preguntas"}
        )
    )

    assert tools_handler.handler({"periodo_horas": 3}, context) == {"report": "ok"}
    assert calls == [("top_preguntas", {"periodo_horas": 3})]


def test_uc007_fr012_lambda_rejects_unknown_tools():
    context = SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": "ponente___borrar_todo"})
    )
    with pytest.raises(ValueError, match="desconocida"):
        tools_handler.handler({}, context)


def test_uc007_fr012_toolkit_masks_reports_with_the_guardrail(monkeypatch):
    from spec_to_runtime.agent import analytics

    monkeypatch.setattr(analytics, "activity_report", lambda **_: "contacto: a@b.com")
    guard = SimpleNamespace(
        apply_guardrail=lambda **_: {
            "action": "GUARDRAIL_INTERVENED",
            "outputs": [{"text": "contacto: {EMAIL}"}],
        }
    )
    toolkit = object.__new__(Toolkit)
    toolkit.settings, toolkit._table, toolkit._guard_client = SETTINGS, object(), guard

    assert toolkit.run("actividad_participantes", {"periodo_horas": 0}) == "contacto: {EMAIL}"
    with pytest.raises(ValueError):
        toolkit.run("otra", {})


def test_fr012_gateway_requests_are_signed_with_sigv4_for_agentcore():
    session = boto3.Session(
        aws_access_key_id="AKIAEXAMPLE", aws_secret_access_key="secret", region_name="us-east-1"
    )
    request = httpx.Request(
        "POST",
        "https://gw.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        json={"jsonrpc": "2.0", "method": "tools/list"},
    )

    signed = next(gateway.SigV4HttpxAuth("us-east-1", session).auth_flow(request))

    authorization = signed.headers["Authorization"]
    assert authorization.startswith("AWS4-HMAC-SHA256 Credential=AKIAEXAMPLE/")
    assert "/us-east-1/bedrock-agentcore/aws4_request" in authorization
    assert "X-Amz-Date" in signed.headers


def test_fr012_gateway_client_prefixes_the_target_and_unwraps_the_report(monkeypatch):
    seen = {}

    class FakeMCP:
        def __init__(self, **kwargs):
            seen["init"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def call_tool_sync(self, _id, name, arguments):
            seen["call"] = (name, arguments)
            return {"status": "success", "content": [{"text": '{"report": "hola"}'}]}

    monkeypatch.setattr(gateway, "MCPClient", FakeMCP)
    monkeypatch.setattr(gateway, "SigV4HttpxAuth", lambda region: f"auth-{region}")

    client = gateway.GatewayClient("https://gw", "us-east-1")

    assert client.call("top_preguntas", {"periodo_horas": 0}) == "hola"
    assert seen["call"] == ("ponente___top_preguntas", {"periodo_horas": 0})
    assert seen["init"] == {"url": "https://gw", "auth_provider": "auth-us-east-1"}


def test_fr012_gateway_client_raises_on_tool_errors(monkeypatch):
    class FailingMCP:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def call_tool_sync(self, *_):
            return {"status": "error", "content": [{"text": "boom"}]}

    monkeypatch.setattr(gateway, "MCPClient", FailingMCP)
    with pytest.raises(gateway.GatewayError, match="boom"):
        gateway.GatewayClient("https://gw", "us-east-1").call("top_preguntas")


def test_fr012_unwrap_keeps_plain_text():
    assert gateway.unwrap("sin json") == "sin json"
    assert gateway.unwrap('{"otro": 1}') == '{"otro": 1}'

"""Observabilidad: trazas de punta a punta (X-Ray -> W3C), cola SQS y métricas propias (EMF)."""

import json
from datetime import timedelta

import pytest

from spec_to_runtime.api import handler as api
from spec_to_runtime.common import metrics, requests_store, tracing
from spec_to_runtime.orchestrator import handler as orch
from tests.test_uc004_api import ask, deps, event
from tests.test_uc004_orchestrator import HAPPY, NOW, setup

# Fixtures reutilizadas de los tests de la API y del orquestador (pytest las descubre por nombre).
__all__ = ["deps", "setup"]

XRAY = "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1"


# --- traductor de cabeceras --------------------------------------------------------------------


def test_the_xray_header_becomes_the_w3c_traceparent_with_the_same_trace_id():
    assert tracing.root_trace_id(XRAY) == "1-5759e988-bd862e3fe1be46a994272793"
    assert tracing.to_traceparent(XRAY) == "00-5759e988bd862e3fe1be46a994272793-53995c3f42cd8ad8-01"


def test_an_unsampled_trace_keeps_its_flag_and_extra_fields_are_ignored():
    header = (
        "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=0;Lineage=a:1"
    )
    assert tracing.to_traceparent(header).endswith("-00")


@pytest.mark.parametrize("header", [None, "", "basura", "Root=1-5759e988-bd862e3fe1be46a994272793"])
def test_without_a_usable_header_there_is_no_traceparent(header):
    assert tracing.to_traceparent(header) is None


def test_runtime_kwargs_carry_both_headers_and_the_session_for_grouping(monkeypatch):
    monkeypatch.setenv("_X_AMZN_TRACE_ID", XRAY)
    kwargs = tracing.runtime_trace_kwargs("sess-1")
    assert kwargs == {
        "traceId": XRAY,
        "traceParent": "00-5759e988bd862e3fe1be46a994272793-53995c3f42cd8ad8-01",
        "baggage": "session.id=sess-1",
    }
    monkeypatch.delenv("_X_AMZN_TRACE_ID")
    assert tracing.runtime_trace_kwargs("sess-1") == {}


# --- costura 1: la API deja la cabecera en el mensaje de la cola ---------------------------------


def test_the_api_puts_the_trace_header_on_the_queue_message_so_the_trace_is_not_cut(
    deps, monkeypatch
):
    monkeypatch.setenv("_X_AMZN_TRACE_ID", XRAY)
    _, body = ask(deps)
    message = deps.aws.sqs.receive_message(
        QueueUrl=deps.queue_url, MessageSystemAttributeNames=["AWSTraceHeader"]
    )["Messages"][0]
    assert message["Attributes"]["AWSTraceHeader"] == XRAY
    sent = json.loads(message["Body"])
    assert sent["request_id"] == body["request_id"] and sent["created_at"]
    item = requests_store.get_request(deps.table, "u1", body["request_id"])
    assert item["trace_id"] == "1-5759e988-bd862e3fe1be46a994272793"


def test_without_active_tracing_the_api_sends_no_trace_attribute(deps, monkeypatch):
    monkeypatch.delenv("_X_AMZN_TRACE_ID", raising=False)
    _, body = ask(deps)
    message = deps.aws.sqs.receive_message(
        QueueUrl=deps.queue_url, MessageSystemAttributeNames=["AWSTraceHeader"]
    )["Messages"][0]
    assert "AWSTraceHeader" not in message.get("Attributes", {})
    assert "trace_id" not in requests_store.get_request(deps.table, "u1", body["request_id"])


def test_only_the_speaker_gets_the_trace_id_to_open_the_trace(deps, monkeypatch):
    monkeypatch.setenv("_X_AMZN_TRACE_ID", XRAY)
    _, mine = ask(deps)
    path = {"request_id": mine["request_id"]}
    as_participant = json.loads(
        api.get_request(event("GET /requests/{request_id}", "u1", path=path))["body"]
    )
    assert "trace_id" not in as_participant
    _, theirs = ask(deps, user="p1", groups="[Ponente]")
    path = {"request_id": theirs["request_id"]}
    as_speaker = json.loads(
        api.get_request(event("GET /requests/{request_id}", "p1", "[Ponente]", path=path))["body"]
    )
    assert as_speaker["trace_id"] == "1-5759e988-bd862e3fe1be46a994272793"


# --- costura 2: el orquestador continúa la traza hacia el Runtime --------------------------------


def test_the_orchestrator_continues_the_trace_into_the_agent_runtime(setup, monkeypatch):
    monkeypatch.setenv("_X_AMZN_TRACE_ID", XRAY)
    deps_, message, _ = setup(HAPPY)
    orch.process(message, deps_, now=lambda: NOW)
    call = deps_.runtime.invoke_agent_runtime.call_args.kwargs
    assert call["traceParent"] == "00-5759e988bd862e3fe1be46a994272793-53995c3f42cd8ad8-01"
    assert call["traceId"] == XRAY and call["baggage"] == f"session.id={message['session_id']}"


def test_without_a_trace_the_orchestrator_still_invokes_the_agent_normally(setup, monkeypatch):
    monkeypatch.delenv("_X_AMZN_TRACE_ID", raising=False)
    deps_, message, _ = setup(HAPPY)
    assert orch.process(message, deps_, now=lambda: NOW) == "Completed"
    assert "traceParent" not in deps_.runtime.invoke_agent_runtime.call_args.kwargs


# --- métricas propias (EMF) ------------------------------------------------------------------------


def emf_lines(capsys):
    return [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]


def test_emf_lines_are_valid_cloudwatch_metric_records(capsys):
    metrics.emit(
        {"Requests": (1, "Count"), "TotalLatencyMs": (850.5, "Milliseconds")},
        {"Outcome": "Completed"},
        {"request_id": "r1"},
    )
    (record,) = emf_lines(capsys)
    directive = record["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "SpecToRuntime" and directive["Dimensions"] == [["Outcome"]]
    assert [m["Name"] for m in directive["Metrics"]] == ["Requests", "TotalLatencyMs"]
    assert (
        record["Outcome"] == "Completed"
        and record["TotalLatencyMs"] == 850.5
        and record["request_id"] == "r1"
    )


def test_the_orchestrator_reports_outcome_latency_queue_wait_and_tokens(setup, capsys, monkeypatch):
    monkeypatch.setenv("_X_AMZN_TRACE_ID", XRAY)
    deps_, message, _ = setup(HAPPY)
    message["created_at"] = (NOW - timedelta(milliseconds=1500)).isoformat()
    ticks = iter(range(1000))  # 1 s por lectura del reloj
    orch.process(message, deps_, clock=lambda: float(next(ticks)), now=lambda: NOW)
    (record,) = emf_lines(capsys)
    assert record["Outcome"] == "Completed" and record["Requests"] == 1
    assert (
        record["QueueWaitMs"] == 1500
        and record["FirstTextMs"] > 0
        and record["TotalLatencyMs"] > record["FirstTextMs"]
    )
    assert record["InputTokens"] == 100 and record["OutputTokens"] == 50
    assert (
        record["trace_id"] == "1-5759e988-bd862e3fe1be46a994272793" and record["request_id"] == "r1"
    )


def test_failures_are_reported_with_their_error_code_so_alarms_can_use_them(setup, capsys):
    deps_, message, _ = setup(runtime_error=RuntimeError("caído"))
    orch.process(message, deps_, now=lambda: NOW)
    (record,) = emf_lines(capsys)
    assert record["Outcome"] == "Failed" and record["error_code"] == "RuntimeError"


def test_the_api_counts_submissions_and_quota_rejections(deps, capsys):
    ask(deps)
    for _ in range(25):
        ask(deps)
    records = emf_lines(capsys)
    submitted = [r for r in records if "Submitted" in r]
    rejected = [r for r in records if "Rejections" in r]
    assert len(submitted) == 25 and submitted[0]["Role"] == "Participant"
    assert len(rejected) == 1 and rejected[0]["Reason"] == "daily"


def test_the_agent_annotations_are_harmless_without_an_opentelemetry_sdk():
    from spec_to_runtime.agent import telemetry

    with telemetry.session_context("sess-1"):
        telemetry.annotate(profile="Basic", top_score=None, passages=3)
        with telemetry.span("rag.retrieve", top_k=6) as span:
            assert span is not None

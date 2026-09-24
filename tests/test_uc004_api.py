"""API: UC-004 (preguntar), UC-005 (sesiones), UC-006 (historial) y UC-003/UC-007 (rol Ponente)."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from spec_to_runtime.api import handler as api
from spec_to_runtime.common import requests_store
from tests.conftest import counter

NOW = datetime(2026, 9, 26, 15, 0, tzinfo=UTC)
DAY = "2026-09-26"


@pytest.fixture
def deps(aws, monkeypatch):
    lambda_client = MagicMock()
    lambda_client.invoke.return_value = {
        "Payload": MagicMock(read=lambda: b'{"result": "Started"}')
    }
    d = api.Deps(
        table=aws.requests, usage_client=aws.usage_client, sqs=aws.sqs, lambda_client=lambda_client,
        queue_url=aws.queue_url, usage_table="usage", sync_function="sync-fn", project_cap=3000,
    )  # fmt: skip
    monkeypatch.setattr(api, "_deps", lambda: d)
    d.aws = aws
    return d


def event(route, user="u1", groups="", body=None, path=None):
    return {
        "routeKey": route,
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": path or {},
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user, "cognito:groups": groups}}}
        },
    }


def ask(deps, prompt="¿Qué es AIUP?", user="u1", groups="", now=NOW, **extra):
    response = api.submit_question(
        event("POST /questions", user, groups, {"prompt": prompt, **extra}), now
    )
    return response["statusCode"], json.loads(response["body"])


def queued_messages(deps):
    return deps.aws.sqs.receive_message(QueueUrl=deps.queue_url, MaxNumberOfMessages=10).get(
        "Messages", []
    )


def queue_size(deps):
    attrs = deps.aws.sqs.get_queue_attributes(
        QueueUrl=deps.queue_url, AttributeNames=["ApproximateNumberOfMessages"]
    )
    return int(attrs["Attributes"]["ApproximateNumberOfMessages"])


def test_uc004_main_flow_saves_counts_and_enqueues(deps):
    status, body = ask(deps, profile="Basic")
    assert status == 202 and body["status"] == "Queued" and body["context_expired"] is False
    item = requests_store.get_request(deps.table, "u1", body["request_id"])
    assert (
        item["status"] == "Queued" and item["profile"] == "Basic" and item["role"] == "Participant"
    )
    assert counter(deps.aws, "USER#u1", DAY) == 1  # BR-005: se cuenta al aceptarla
    (message,) = queued_messages(deps)
    sent = json.loads(message["Body"])
    assert (
        sent["request_id"] == body["request_id"] and sent["user_id"] == "u1" and sent["day"] == DAY
    )


@pytest.mark.parametrize("prompt", ["", "   ", "x" * 501])
def test_uc004_br001_invalid_length_is_rejected_without_side_effects(deps, prompt):
    status, body = ask(deps, prompt=prompt)
    assert status == 400 and body["code"] == "invalid_prompt"
    assert counter(deps.aws, "USER#u1", DAY) == 0 and queued_messages(deps) == []


def test_uc004_br001_500_characters_are_accepted(deps):
    assert ask(deps, prompt="x" * 500)[0] == 202


def test_uc002_invalid_profile_is_rejected_and_general_is_the_default(deps):
    assert ask(deps, profile="Otro")[1]["code"] == "invalid_profile"
    _, body = ask(deps)
    assert requests_store.get_request(deps.table, "u1", body["request_id"])["profile"] == "General"


def test_uc007_br001_the_role_comes_from_the_token_never_from_the_body(deps):
    _, forged = ask(deps, role="Speaker")  # un participante que intenta hacerse pasar por Ponente
    assert (
        requests_store.get_request(deps.table, "u1", forged["request_id"])["role"] == "Participant"
    )
    _, real = ask(deps, user="p1", groups="[Ponente]")
    assert requests_store.get_request(deps.table, "p1", real["request_id"])["role"] == "Speaker"


def test_uc004_a2_daily_limit_is_recorded_as_rejected_and_never_reaches_the_agent(deps):
    for _ in range(25):
        assert ask(deps)[0] == 202
    assert queue_size(deps) == 25
    status, body = ask(deps)
    assert (
        status == 429
        and body["code"] == "daily_limit"
        and body["resets_at"] == "2026-09-27T05:00:00+00:00"
    )
    assert requests_store.get_request(deps.table, "u1", body["request_id"])["status"] == "Rejected"
    assert queue_size(deps) == 25  # la rechazada no llegó a la cola
    assert counter(deps.aws, "USER#u1", DAY) == 25


def test_uc004_a2_project_limit_is_reported_apart_from_the_daily_one(deps):
    deps.project_cap = 1
    assert ask(deps, user="a")[0] == 202
    status, body = ask(deps, user="b")
    assert status == 429 and body["code"] == "project_limit"


def test_uc004_enqueue_failure_marks_the_request_failed_and_returns_the_quota(deps):
    deps.sqs = MagicMock(send_message=MagicMock(side_effect=RuntimeError("sqs caído")))
    status, _ = ask(deps)
    assert status == 503
    assert counter(deps.aws, "USER#u1", DAY) == 0  # BR-006: los fallos no consumen cuota
    (item,) = requests_store.user_requests(deps.table, "u1")
    assert item["status"] == "Failed"


def test_uc005_a_follow_up_keeps_the_session_and_a_stranger_cannot_join_it(deps):
    _, first = ask(deps)
    _, follow = ask(deps, session_id=first["session_id"], now=NOW + timedelta(minutes=5))
    assert follow["session_id"] == first["session_id"] and follow["context_expired"] is False
    status, body = ask(deps, user="intruso", session_id=first["session_id"])
    assert status == 404 and body["code"] == "session_not_found"


def test_uc005_a2_context_older_than_24_hours_opens_a_new_session(deps):
    _, first = ask(deps)
    _, later = ask(deps, session_id=first["session_id"], now=NOW + timedelta(hours=25))
    assert later["context_expired"] is True and later["session_id"] != first["session_id"]


def test_uc004_nfr009_a_request_can_only_be_read_by_its_owner_and_never_shows_the_user_id(deps):
    _, body = ask(deps)
    mine = api.get_request(
        event("GET /requests/{request_id}", "u1", path={"request_id": body["request_id"]})
    )
    assert mine["statusCode"] == 200 and "user_id" not in json.loads(mine["body"])
    other = api.get_request(
        event("GET /requests/{request_id}", "u2", path={"request_id": body["request_id"]})
    )
    assert other["statusCode"] == 404


def test_uc006_history_lists_own_sessions_newest_first_and_only_the_users_own(deps):
    _, a = ask(deps, prompt="primera de A")
    _, b = ask(deps, prompt="primera de B", now=NOW + timedelta(hours=1))
    ask(deps, prompt="seguimiento de A", session_id=a["session_id"], now=NOW + timedelta(hours=2))
    ask(deps, prompt="de otra persona", user="u2")
    out = json.loads(api.list_sessions(event("GET /sessions", "u1"))["body"])
    assert [s["session_id"] for s in out["sessions"]] == [a["session_id"], b["session_id"]]
    assert (
        out["sessions"][0]["first_question"] == "primera de A"
        and out["sessions"][0]["questions"] == 2
    )
    assert out["has_more"] is False


def test_uc006_a4_shows_at_most_20_conversations_and_says_there_are_more(deps):
    for i in range(22):
        ask(deps, user="u9", now=NOW + timedelta(hours=i))
    out = json.loads(api.list_sessions(event("GET /sessions", "u9"))["body"])
    assert len(out["sessions"]) == 20 and out["has_more"] is True


def test_uc006_a_session_shows_questions_in_order_and_is_private(deps):
    _, a = ask(deps, prompt="uno")
    ask(deps, prompt="dos", session_id=a["session_id"], now=NOW + timedelta(minutes=1))
    path = {"session_id": a["session_id"]}
    out = json.loads(api.get_session(event("GET /sessions/{session_id}", "u1", path=path))["body"])
    assert [i["prompt"] for i in out["items"]] == ["uno", "dos"]
    assert (
        api.get_session(event("GET /sessions/{session_id}", "u2", path=path))["statusCode"] == 404
    )


def test_uc003_a1_only_the_ponente_can_synchronize(deps):
    denied = api.handler(event("POST /admin/sync", "u1"), None)
    assert denied["statusCode"] == 403 and json.loads(denied["body"])["code"] == "forbidden"
    deps.lambda_client.invoke.assert_not_called()
    ok = api.handler(event("POST /admin/sync", "p1", "[Ponente]"), None)
    assert ok["statusCode"] == 200 and json.loads(ok["body"]) == {"result": "Started"}


def test_uc003_get_asks_for_the_status_instead_of_starting_a_sync(deps):
    api.handler(event("GET /admin/sync", "p1", "[Ponente]"), None)
    sent = json.loads(deps.lambda_client.invoke.call_args.kwargs["Payload"])
    assert sent == {"action": "status"}


def test_unknown_routes_and_unexpected_errors_do_not_leak_details(deps, monkeypatch):
    assert api.handler({"routeKey": "GET /nada"}, None)["statusCode"] == 404
    monkeypatch.setitem(api.ROUTES, "GET /boom", lambda _e: 1 / 0)
    boom = api.handler({"routeKey": "GET /boom"}, None)
    assert boom["statusCode"] == 500 and "division" not in boom["body"]

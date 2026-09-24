"""UC-001 Autenticarse: registro con código de evento (BR-001, BR-002, BR-007)."""

import json
from unittest.mock import MagicMock

import pytest

from spec_to_runtime.auth import pre_signup


@pytest.fixture
def fake_aws(monkeypatch):
    monkeypatch.setenv("EVENT_SECRET_ARN", "arn:secret")
    monkeypatch.setenv("MAX_ACCOUNTS", "100")
    secrets, idp = MagicMock(), MagicMock()
    secrets.get_secret_value.return_value = {
        "SecretString": json.dumps({"event_code": "abc123", "registration_open": True})
    }
    idp.describe_user_pool.return_value = {"UserPool": {"EstimatedNumberOfUsers": 3}}
    monkeypatch.setattr(pre_signup, "_secrets", secrets)
    monkeypatch.setattr(pre_signup, "_idp", idp)
    return secrets, idp


def _event(code="abc123", source="PreSignUp_SignUp"):
    return {
        "triggerSource": source,
        "userPoolId": "pool",
        "request": {"clientMetadata": {"eventCode": code}},
        "response": {},
    }


def test_uc001_valid_code_confirms_account(fake_aws):
    result = pre_signup.handler(_event(), None)
    assert result["response"]["autoConfirmUser"] is True


def test_uc001_invalid_code_is_rejected(fake_aws):
    with pytest.raises(pre_signup.RegistrationError, match="INVALID_EVENT_CODE"):
        pre_signup.handler(_event(code="mal"), None)


def test_uc001_closed_registration_is_rejected(fake_aws):
    secrets, _ = fake_aws
    secrets.get_secret_value.return_value = {
        "SecretString": json.dumps({"event_code": "abc123", "registration_open": False})
    }
    with pytest.raises(pre_signup.RegistrationError, match="REGISTRATION_CLOSED"):
        pre_signup.handler(_event(), None)


def test_uc001_account_limit_is_enforced(fake_aws):
    _, idp = fake_aws
    idp.describe_user_pool.return_value = {"UserPool": {"EstimatedNumberOfUsers": 100}}
    with pytest.raises(pre_signup.RegistrationError, match="ACCOUNT_LIMIT_REACHED"):
        pre_signup.handler(_event(), None)


def test_uc001_other_trigger_sources_pass_through(fake_aws):
    event = _event(source="PreSignUp_AdminCreateUser")
    assert pre_signup.handler(event, None) is event

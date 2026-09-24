"""Pre-sign-up trigger de Cognito (UC-001 Autenticarse).

Solo confirma cuentas nuevas cuando el código del evento es válido, el registro
está abierto y no se superó el máximo de cuentas (UC-001 BR-001, BR-002, BR-007).
"""

import hmac
import json
import os

import boto3


class RegistrationError(Exception):
    """Motivo por el que Cognito rechaza el registro (se muestra al participante)."""


_secrets = boto3.client("secretsmanager")
_idp = boto3.client("cognito-idp")


def _event_config() -> dict:
    raw = _secrets.get_secret_value(SecretId=os.environ["EVENT_SECRET_ARN"])["SecretString"]
    return json.loads(raw)


def handler(event, _context):
    if event.get("triggerSource") != "PreSignUp_SignUp":
        return event

    config = _event_config()
    if not config.get("registration_open", False):
        raise RegistrationError("REGISTRATION_CLOSED")

    sent = (event["request"].get("clientMetadata") or {}).get("eventCode", "")
    if not hmac.compare_digest(sent.encode(), str(config["event_code"]).encode()):
        raise RegistrationError("INVALID_EVENT_CODE")

    pool = _idp.describe_user_pool(UserPoolId=event["userPoolId"])["UserPool"]
    if pool["EstimatedNumberOfUsers"] >= int(os.environ["MAX_ACCOUNTS"]):
        raise RegistrationError("ACCOUNT_LIMIT_REACHED")

    event["response"]["autoConfirmUser"] = True
    event["response"]["autoVerifyEmail"] = True
    return event

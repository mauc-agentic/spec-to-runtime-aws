#!/usr/bin/env python3
"""Prueba del corte automático de presupuesto (NFR-014) con una pregunta real.

Hace lo mismo que haría AWS Budgets al llegar al 90 %: adjunta la política de corte a los roles
del agente y del orquestador, comprueba que las preguntas fallan en menos de un segundo SIN gastar
cuota, la retira y comprueba que todo se recupera. Usa un usuario temporal que borra al terminar.

CUIDADO: durante unos 40 segundos la demo está realmente cortada. No la ejecutes durante la charla.
Si se interrumpiera, retira el corte a mano:
  aws iam detach-role-policy --role-name <rol> --policy-arn $(terraform -chdir=infra output -raw budget_cutoff_policy_arn)

Uso: uv run python scripts/test_budget_cutoff.py
"""

import json
import secrets
import string
import subprocess
import time
import urllib.error
import urllib.request

import boto3

R = "us-east-1"
ROLES = ["spec-to-runtime-agent-runtime", "spec-to-runtime-orchestrator"]
tf = lambda n: subprocess.run(
    ["terraform", "-chdir=infra", "output", "-raw", n], capture_output=True, text=True, check=True
).stdout.strip()
API, POOL, CLIENT = tf("api_url"), tf("user_pool_id"), tf("user_pool_client_id")
POL = tf("budget_cutoff_policy_arn")
iam, idp, db = (
    boto3.client("iam"),
    boto3.client("cognito-idp", region_name=R),
    boto3.resource("dynamodb", region_name=R),
)


def http(method, path, token, body=None):
    req = urllib.request.Request(
        API + path, method=method, data=json.dumps(body).encode() if body is not None else None
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def ask(token, prompt):
    t0 = time.time()
    st, b = http("POST", "/questions", token, {"prompt": prompt, "profile": "General"})
    if st != 202:
        return {"http": st, **b}
    while time.time() - t0 < 100:
        _, r = http("GET", "/requests/" + b["request_id"], token)
        if r["status"] in ("Completed", "Blocked", "Failed", "Rejected"):
            r["seg"] = round(time.time() - t0, 1)
            return r
        time.sleep(0.8)


def quota_used(sub):
    it = (
        db.Table("spec-to-runtime-usage")
        .get_item(
            Key={
                "scope": f"USER#{sub}",
                "usage_date": time.strftime("%Y-%m-%d", time.gmtime(time.time() - 5 * 3600)),
            }
        )
        .get("Item")
    )
    return int(it["request_count"]) if it else 0


email, pw = (
    f"corte-{secrets.token_hex(3)}@example.com",
    "Pw" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10)),
)
idp.admin_create_user(
    UserPoolId=POOL,
    Username=email,
    MessageAction="SUPPRESS",
    UserAttributes=[{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}],
)
idp.admin_set_user_password(UserPoolId=POOL, Username=email, Password=pw, Permanent=True)
sub = next(
    a["Value"]
    for a in idp.admin_get_user(UserPoolId=POOL, Username=email)["UserAttributes"]
    if a["Name"] == "sub"
)
token = idp.initiate_auth(
    ClientId=CLIENT,
    AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={"USERNAME": email, "PASSWORD": pw},
)["AuthenticationResult"]["AccessToken"]
attached = False
try:
    r = ask(token, "¿Qué es AIUP?")
    print(
        f"0. Antes del corte      -> {r['status']} en {r['seg']} s | cuota usada: {quota_used(sub)}"
    )
    for role in ROLES:
        iam.attach_role_policy(RoleName=role, PolicyArn=POL)
    attached = True
    print(
        "   >>> política de corte adjuntada a los dos roles (lo que haría AWS Budgets); espero a que IAM propague"
    )
    time.sleep(20)
    r = ask(token, "¿Qué hace el rol Ponente?")
    print(
        f"1. Con el corte activo  -> {r['status']} en {r['seg']} s | error_code={r.get('error_code')!r} | texto={r.get('text', '')!r} | cuota usada: {quota_used(sub)}"
    )
    r = ask(token, "¿Cuánto cuesta la demo?")
    print(
        f"2. Segundo intento      -> {r['status']} en {r['seg']} s | error_code={r.get('error_code')!r} | cuota usada: {quota_used(sub)}"
    )
finally:
    if attached:
        for role in ROLES:
            iam.detach_role_policy(RoleName=role, PolicyArn=POL)
        print("   >>> política de corte RETIRADA de los dos roles")
print("   (espero a que IAM propague la retirada)")
time.sleep(20)
try:
    r = ask(token, "¿Qué perfiles hay?")
    print(
        f"3. Tras levantar el corte -> {r['status']} en {r['seg']} s | cuota usada: {quota_used(sub)}"
    )
finally:
    from boto3.dynamodb.conditions import Key

    req, use = db.Table("spec-to-runtime-requests"), db.Table("spec-to-runtime-usage")
    used = 0
    for it in req.query(KeyConditionExpression=Key("user_id").eq(sub))["Items"]:
        req.delete_item(Key={"user_id": sub, "request_sk": it["request_sk"]})
    for it in use.query(KeyConditionExpression=Key("scope").eq(f"USER#{sub}"))["Items"]:
        used += int(it["request_count"])
        use.delete_item(Key={"scope": it["scope"], "usage_date": it["usage_date"]})
    if used:
        use.update_item(
            Key={"scope": "GLOBAL", "usage_date": "TOTAL"},
            UpdateExpression="SET request_count = request_count - :n",
            ConditionExpression="request_count >= :n",
            ExpressionAttributeValues={":n": used},
        )
    idp.admin_delete_user(UserPoolId=POOL, Username=email)
    for role in ROLES:
        print(
            f"   políticas adjuntas a {role}: {[p['PolicyName'] for p in iam.list_attached_role_policies(RoleName=role)['AttachedPolicies']]}"
        )
    print("   usuario y datos de la prueba eliminados")

#!/usr/bin/env python3
"""Vacía los datos de ensayo para que la charla arranque limpia.

Borra: las preguntas guardadas (historial y análisis del Ponente), los contadores de cuota y los
eventos de la memoria de AgentCore. Con `--users` borra además las cuentas que no sean del Ponente.
NO borra: la cuenta del Ponente, el código del evento, la Knowledge Base ni los documentos.

Por defecto solo cuenta lo que borraría (simulación). Para borrar de verdad:
  uv run python scripts/reset_event_data.py --yes [--users]

Los spans de las trazas (`aws/spans`) y los logs de CloudWatch no se borran: caducan a los 30 días.
"""

import argparse
import subprocess

import boto3

REGION = "us-east-1"


def tf(name: str) -> str:
    result = subprocess.run(
        ["terraform", "-chdir=infra", "output", "-raw", name],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def clear_table(table, keys: tuple[str, str], execute: bool) -> int:
    count = 0
    kwargs = {
        "ProjectionExpression": ", ".join(f"#k{i}" for i in range(2)),
        "ExpressionAttributeNames": {"#k0": keys[0], "#k1": keys[1]},
    }
    while True:
        page = table.scan(**kwargs)
        for item in page["Items"]:
            count += 1
            if execute:
                table.delete_item(Key={k: item[k] for k in keys})
        if "LastEvaluatedKey" not in page:
            return count
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def clear_memory(memory_id: str, execute: bool) -> tuple[int, int]:
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    actors = events = 0
    for actor in client.list_actors(memoryId=memory_id)["actorSummaries"]:
        actors += 1
        for session in client.list_sessions(memoryId=memory_id, actorId=actor["actorId"])[
            "sessionSummaries"
        ]:
            token = None
            while True:
                extra = {"nextToken": token} if token else {}
                page = client.list_events(
                    memoryId=memory_id,
                    actorId=actor["actorId"],
                    sessionId=session["sessionId"],
                    maxResults=100,
                    **extra,
                )
                for event in page["events"]:
                    events += 1
                    if execute:
                        client.delete_event(
                            memoryId=memory_id,
                            actorId=actor["actorId"],
                            sessionId=session["sessionId"],
                            eventId=event["eventId"],
                        )
                token = page.get("nextToken")
                if not token:
                    break
    return actors, events


def clear_users(pool_id: str, execute: bool) -> int:
    idp = boto3.client("cognito-idp", region_name=REGION)
    speakers = {
        u["Username"]
        for u in idp.list_users_in_group(UserPoolId=pool_id, GroupName="Ponente")["Users"]
    }
    doomed = [
        u["Username"]
        for u in idp.list_users(UserPoolId=pool_id)["Users"]
        if u["Username"] not in speakers
    ]
    if execute:
        for username in doomed:
            idp.admin_delete_user(UserPoolId=pool_id, Username=username)
    return len(doomed)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--yes", action="store_true", help="borrar de verdad (sin esto solo cuenta)"
    )
    parser.add_argument(
        "--users", action="store_true", help="borrar también las cuentas que no son del Ponente"
    )
    args = parser.parse_args()

    db = boto3.resource("dynamodb", region_name=REGION)
    verb = "Borrado" if args.yes else "Se borraría (simulación)"
    requests = clear_table(db.Table(tf("requests_table")), ("user_id", "request_sk"), args.yes)
    usage = clear_table(db.Table(tf("usage_table")), ("scope", "usage_date"), args.yes)
    actors, events = clear_memory(tf("memory_id"), args.yes)
    print(f"{verb}:")
    print(f"  {requests} preguntas guardadas")
    print(f"  {usage} contadores de cuota (usuarios y global)")
    print(f"  {events} eventos de memoria de {actors} actores")
    if args.users:
        print(f"  {clear_users(tf('user_pool_id'), args.yes)} cuentas que no son del Ponente")
    if not args.yes:
        print("\nNo se borró nada. Repite con --yes para borrar.")


if __name__ == "__main__":
    main()

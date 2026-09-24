#!/usr/bin/env python3
"""Calentamiento previo a la charla: deja el sistema listo sin tocar el registro.

Con cuentas temporales (un participante y un Ponente, creadas por la API de administración de
Cognito, sin abrir el registro) hace una pregunta de cada rol para despertar toda la cadena: API,
cola, Lambdas, Runtime del agente, Knowledge Base, guardrails, modelo, Gateway y la Lambda de
herramientas. Después borra las cuentas temporales y sus datos y, si no hay preguntas reales,
vacía los datos de ensayo (`reset_event_data.py --yes`).

A diferencia de `smoke_test.py`, NO abre ni cierra el registro: si ya lo abriste, sigue abierto.
El Runtime libera la sesión tras 5 minutos de inactividad: ejecútalo unos 5 minutos antes.

Uso: PYTHONPATH=src uv run python scripts/warmup.py [--no-reset]
     (requiere credenciales de AWS y terraform)

Salvaguarda: el reseteo borra TODAS las preguntas y cuotas, así que solo se hace si no queda
ninguna pregunta guardada tras borrar las cuentas temporales. Si ya hay participantes reales
preguntando, el script calienta, no borra nada y lo avisa.
"""

import argparse
import json
import secrets
import subprocess
import sys
import time

import smoke_test as s  # scripts/ está en sys.path cuando se ejecuta como script

QUESTIONS = {
    "participante": "¿Qué es AIUP?",
    "ponente": "¿Cuáles fueron las preguntas más frecuentes?",
}


def registration_open() -> bool | None:
    """Estado del registro, solo lectura. None si no se puede leer."""
    try:
        value = s.sm.get_secret_value(SecretId=s.SECRET)["SecretString"]
        return bool(json.loads(value)["registration_open"])
    except Exception:  # noqa: BLE001 - es informativo, no debe tumbar el calentamiento
        return None


def create_user(email: str, group: str | None) -> str:
    """Crea la cuenta por la API de administración (sin registro ni código) y devuelve su token."""
    password = s.new_password()
    s.idp.admin_create_user(
        UserPoolId=s.POOL,
        Username=email,
        MessageAction="SUPPRESS",
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
    )
    s.idp.admin_set_user_password(
        UserPoolId=s.POOL, Username=email, Password=password, Permanent=True
    )
    if group:
        s.idp.admin_add_user_to_group(UserPoolId=s.POOL, Username=email, GroupName=group)
    return s.login(email, password)  # el token se pide después del grupo: lo lleva en el claim


def stored_requests() -> int:
    """Preguntas guardadas en la tabla (cualquier persona)."""
    return s.requests_table.scan(Select="COUNT")["Count"]


def reset(execute: bool) -> str:
    args = [sys.executable, "scripts/reset_event_data.py", *(["--yes"] if execute else [])]
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    return "\n".join(line for line in result.stdout.splitlines() if line.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Calienta el sistema antes de la charla.")
    parser.add_argument("--no-reset", action="store_true", help="no vacía los datos de ensayo")
    args = parser.parse_args()

    started = time.time()
    tag = secrets.token_hex(3)
    emails = [f"calentamiento-part-{tag}@example.com", f"calentamiento-pon-{tag}@example.com"]
    results: dict[str, dict] = {}
    print(f"Registro: {'ABIERTO' if registration_open() else 'cerrado'} (este script no lo cambia)")
    try:
        tokens = {
            "participante": create_user(emails[0], None),
            "ponente": create_user(emails[1], "Ponente"),
        }
        for role in (
            "participante",
            "ponente",
        ):  # el Ponente va después: analiza lo que se preguntó
            results[role] = s.ask(tokens[role], QUESTIONS[role], "General")
    finally:
        s.cleanup(emails)

    ok = {
        role: r.get("status") == "Completed" and bool(r.get("text")) for role, r in results.items()
    }
    print()
    for role in ("participante", "ponente"):
        print(f"  {'OK ' if ok.get(role) else 'FALLA'} {role}: {QUESTIONS[role]}")

    remaining = stored_requests()
    if args.no_reset:
        print("\nNo se vaciaron los datos (--no-reset).")
    elif remaining:
        print(
            f"\nATENCIÓN: hay {remaining} pregunta(s) guardadas que no son del calentamiento "
            "(¿participantes reales?). NO se borró nada."
        )
    else:
        print("\nVaciando datos de ensayo…")
        print(reset(execute=True))
        print("Comprobación (simulación):")
        print(reset(execute=False))

    print(f"\nRegistro: {'ABIERTO' if registration_open() else 'cerrado'}")
    print(
        f"Calentamiento {'correcto' if all(ok.values()) and len(ok) == 2 else 'CON FALLAS'} en {time.time() - started:.0f} s."
    )
    return 0 if len(ok) == 2 and all(ok.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

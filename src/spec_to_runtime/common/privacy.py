"""Enmascarado de datos personales en la pregunta (UC-004 A4 y BR-004).

Usa los mismos marcadores que el guardrail del modelo (`{EMAIL}`, `{PHONE}`), pero se aplica en la
API, antes de guardar y de encolar: así la pregunta nunca se almacena con el dato original.
"""

import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Secuencias de dígitos con separadores; se valida el número de dígitos para no tocar fechas ni años.
PHONE_RE = re.compile(r"(?<![\w-])[+(]?\d[\d\s().-]{6,}\d(?![\w-])")
PHONE_DIGITS = range(9, 16)  # de un móvil colombiano (10) al máximo internacional (15)

NOTICE_MASKED = "personal_data_masked"


def _mask_phone(match: re.Match) -> str:
    digits = sum(c.isdigit() for c in match.group())
    return "{PHONE}" if digits in PHONE_DIGITS else match.group()


def mask_personal_data(text: str) -> tuple[str, bool]:
    """Devuelve el texto enmascarado y si se enmascaró algo."""
    masked = EMAIL_RE.sub("{EMAIL}", text)
    masked = PHONE_RE.sub(_mask_phone, masked)
    return masked, masked != text

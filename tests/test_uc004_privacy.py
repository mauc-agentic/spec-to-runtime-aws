"""UC-004 A4 y BR-004: los datos personales de la pregunta se enmascaran."""

import pytest

from spec_to_runtime.common.privacy import mask_personal_data


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Escríbeme a juan.perez@example.com", "Escríbeme a {EMAIL}"),
        ("Mi celular es 3001234567", "Mi celular es {PHONE}"),
        ("Llámame al +57 300 123 4567 hoy", "Llámame al {PHONE} hoy"),
        ("Fijo (602) 555-1234", "Fijo {PHONE}"),
        ("a@b.co y 300-123-4567", "{EMAIL} y {PHONE}"),
    ],
)
def test_uc004_a4_emails_and_phones_are_masked(text, expected):
    assert mask_personal_data(text) == (expected, True)


@pytest.mark.parametrize(
    "text",
    [
        "¿Qué es AIUP?",
        "La charla es el 2026-09-26 a las 10:00",
        "En 2026 hay 7 UC y 25 preguntas por día",
        "Ver docs/use_cases/UC-004-consultar.md",
    ],
)
def test_uc004_a4_text_without_personal_data_is_left_alone(text):
    assert mask_personal_data(text) == (text, False)

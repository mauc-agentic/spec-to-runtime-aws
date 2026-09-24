"""Lectura incremental del stream de AgentCore Runtime.

`iter_lines` de boto3 lee en bloques de 1 KB y esconde el streaming (parece que todo llega junto):
hay que leer con `read1`, que devuelve lo que haya disponible sin esperar a llenar el bloque.
"""

import json
from collections.abc import Iterator
from typing import Any

CHUNK_BYTES = 65536


def _reader(body):
    raw = getattr(body, "_raw_stream", body)
    return raw.read1 if hasattr(raw, "read1") else raw.read


def iter_events(body) -> Iterator[dict[str, Any]]:
    """Eventos `data: {json}` separados por línea en blanco."""
    read = _reader(body)
    buffer = b""
    while True:
        chunk = read(CHUNK_BYTES)
        if not chunk:
            break
        buffer += chunk
        while b"\n\n" in buffer:
            frame, buffer = buffer.split(b"\n\n", 1)
            if frame.startswith(b"data: "):
                try:
                    yield json.loads(frame[6:])
                except ValueError:
                    continue  # un fragmento dañado no debe tumbar la respuesta entera

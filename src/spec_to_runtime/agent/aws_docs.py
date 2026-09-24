"""Resultado de la búsqueda en la documentación de AWS (target MCP del Gateway, FR-012).

Sin dependencias de Strands. El servidor devuelve JSON con `content.result`: una lista de
fragmentos con `title`, `url` y `context`. Aquí se convierte en texto compacto para el modelo y
en una lista de fuentes verificables que se muestran siempre al final de la respuesta.
"""

import json
from urllib.parse import urlparse

MAX_CONTEXT_CHARS = 1500  # por fragmento
MAX_SOURCES = 6


def _trusted(url: str) -> bool:
    """Solo enlaces https a aws.amazon.com y sus subdominios: nunca se muestra lo demás como enlace."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" and (
        host == "aws.amazon.com" or host.endswith(".aws.amazon.com")
    )


def parse_search(raw: str) -> tuple[str, list[dict]]:
    """(texto para el modelo, fuentes). Si el formato no es el esperado, devuelve el texto tal cual."""
    try:
        results = json.loads(raw)["content"]["result"]
        entries = [r for r in results if isinstance(r, dict)]
    except ValueError, KeyError, TypeError:
        return raw, []
    blocks, sources, seen = [], [], set()
    for i, entry in enumerate(entries[:MAX_SOURCES], start=1):
        title = str(entry.get("title", "")).strip() or "Documentación de AWS"
        url = str(entry.get("url", "")).strip()
        context = str(entry.get("context", "")).strip()[:MAX_CONTEXT_CHARS]
        blocks.append(f"{i}. {title}\n   {url}\n{context}")
        if url and _trusted(url) and url not in seen:
            seen.add(url)
            sources.append({"path": title, "url": url, "excerpt": "", "score": 0.0})
    return "\n\n".join(blocks) or raw, sources

"""Formato final de la respuesta (FR-023, UC-004 BR-009): legible en un celular."""

TRUNCATED_NOTICE = "_(La respuesta se recortó por su longitud.)_"


def final_text(text: str, citations: list[dict], truncated: bool) -> str:
    body = text.strip()
    if truncated:
        body += f"\n\n{TRUNCATED_NOTICE}"
    if citations:
        # Lista determinista con los enlaces exactos, además de las citas en línea del modelo.
        links = "\n".join(f"- [{c['path']}]({c['url']})" for c in citations)
        body += f"\n\n---\n**Fuentes**\n{links}"
    return body

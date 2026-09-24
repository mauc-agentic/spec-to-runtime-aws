"""RAG sobre el repositorio (UC-004 BR-003: las respuestas salen solo de los documentos)."""

from dataclasses import dataclass

EXCERPT_LIMIT = 500


@dataclass(frozen=True)
class Passage:
    source_path: str
    text: str
    score: float


@dataclass(frozen=True)
class Citation:
    path: str
    url: str
    excerpt: str
    score: float


def source_path_from_uri(uri: str) -> str:
    """s3://bucket/docs/vision.md -> docs/vision.md (UC-003 sube cada archivo con su ruta)."""
    without_scheme = uri.removeprefix("s3://")
    return without_scheme.split("/", 1)[1] if "/" in without_scheme else without_scheme


def retrieve(client, knowledge_base_id: str, query: str, top_k: int, min_relevance: float):
    response = client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": top_k}},
    )
    passages = []
    for item in response.get("retrievalResults", []):
        score = float(item.get("score", 0.0))
        uri = item.get("location", {}).get("s3Location", {}).get("uri", "")
        text = item.get("content", {}).get("text", "")
        if uri and text and score >= min_relevance:
            passages.append(Passage(source_path_from_uri(uri), text, score))
    return passages


def build_context(passages: list[Passage], repo_url: str) -> str:
    blocks = [f"[{p.source_path}]({repo_url}/{p.source_path})\n{p.text}" for p in passages]
    return "\n\n---\n\n".join(blocks)


def to_citations(passages: list[Passage], repo_url: str) -> list[Citation]:
    """Un documento se cita una sola vez, con su fragmento más relevante (entity CITATION)."""
    best: dict[str, Passage] = {}
    for p in passages:
        if p.source_path not in best or p.score > best[p.source_path].score:
            best[p.source_path] = p
    ordered = sorted(best.values(), key=lambda p: p.score, reverse=True)
    return [
        Citation(p.source_path, f"{repo_url}/{p.source_path}", p.text[:EXCERPT_LIMIT], p.score)
        for p in ordered
    ]

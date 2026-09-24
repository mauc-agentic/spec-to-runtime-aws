"""Qué archivos del repositorio se cargan a la base de conocimiento (UC-003 BR-001, BR-003)."""

import fnmatch
import posixpath
from dataclasses import dataclass

MAX_BYTES = 500 * 1024  # UC-003 BR-001: archivos de más de 500 KB se omiten

INCLUDED_EXTENSIONS = {
    ".md", ".puml", ".tf", ".py", ".toml", ".yml", ".yaml", ".json", ".txt", ".hcl",
}  # fmt: skip

EXCLUDED_DIRS = {".git", ".venv", "node_modules", ".terraform", "__pycache__", ".build"}

# Pruebas y scripts: repiten el vocabulario de los documentos (nombres de UC, "AIUP", comandos) y
# desplazaban a `docs/vision.md` y `CLAUDE.md` de los pocos fragmentos que recibe el agente. Con ellos
# indexados, "¿Qué es AIUP?" respondía que era una aplicación (pruebas de navegador, 2026-09-24).
NOISE_DIRS = {"tests", "scripts"}

# Archivos de dependencias: son texto, pero no aportan nada a las respuestas.
LOCK_PATTERNS = ["*.lock", "*lock.json", "*.lock.hcl"]

# UC-003 BR-003: nunca se cargan, aunque estuvieran en el repositorio.
SENSITIVE_PATTERNS = [
    ".env", ".env.*", "*.tfvars", "*.tfvars.json", "*.tfstate", "*.tfstate.*",
    "*.pem", "*.key", "id_rsa*", "id_ed25519*", "*.p12", "credentials",
]  # fmt: skip


@dataclass(frozen=True)
class Decision:
    include: bool
    reason: str = ""


def _matches(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def decide(path: str, size: int) -> Decision:
    parts = path.split("/")
    name = posixpath.basename(path)
    if any(part in EXCLUDED_DIRS for part in parts[:-1]):
        return Decision(False, "directory excluded")
    if any(part in NOISE_DIRS for part in parts[:-1]):
        return Decision(False, "tests and scripts are not indexed")
    if _matches(name, SENSITIVE_PATTERNS):
        return Decision(False, "sensitive file")
    if _matches(name, LOCK_PATTERNS):
        return Decision(False, "dependency lock file")
    if posixpath.splitext(name)[1].lower() not in INCLUDED_EXTENSIONS:
        return Decision(False, "unsupported type")
    if size > MAX_BYTES:
        return Decision(False, "too large")
    return Decision(True)

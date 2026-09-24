"""Lectura del repositorio público en GitHub (rama principal, UC-003 BR-002)."""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

TIMEOUT_SECONDS = 20


class RepositoryUnreachableError(Exception):
    """No se pudo leer el repositorio (UC-003 A3)."""


@dataclass(frozen=True)
class RemoteFile:
    path: str
    sha: str
    size: int


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "spec-to-runtime-sync"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read()
    except OSError as error:  # URLError y HTTPError heredan de OSError
        raise RepositoryUnreachableError(str(error)) from error


def list_files(repo: str, branch: str) -> list[RemoteFile]:
    body = _get(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1")
    tree = json.loads(body)
    if tree.get("truncated"):
        raise RepositoryUnreachableError("El listado del repositorio quedó incompleto.")
    return [
        RemoteFile(item["path"], item["sha"], int(item.get("size", 0)))
        for item in tree["tree"]
        if item["type"] == "blob"
    ]


def download(repo: str, branch: str, path: str) -> bytes:
    return _get(f"https://raw.githubusercontent.com/{repo}/{branch}/{urllib.parse.quote(path)}")

"""Lambda de sincronización (UC-003). El rol Ponente se comprueba antes, en la API (UC-003 A1)."""

import functools
import os

import boto3

from spec_to_runtime.sync import github, sync


@functools.cache
def _clients():
    return boto3.client("s3"), boto3.client("bedrock-agent")


def handler(event, _context):
    s3, bedrock_agent = _clients()
    kb_id, ds_id = os.environ["KNOWLEDGE_BASE_ID"], os.environ["DATA_SOURCE_ID"]
    if (event or {}).get("action") == "status":
        return sync.status(bedrock_agent, kb_id, ds_id)

    repo, branch = os.environ["REPO"], os.environ.get("BRANCH", "main")
    return sync.synchronize(
        s3=s3,
        bedrock_agent=bedrock_agent,
        bucket=os.environ["DOCS_BUCKET"],
        kb_id=kb_id,
        ds_id=ds_id,
        list_remote=lambda: github.list_files(repo, branch),
        download=lambda path: github.download(repo, branch, path),
    )

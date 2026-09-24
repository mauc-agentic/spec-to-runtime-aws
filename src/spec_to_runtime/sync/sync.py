"""Sincronización del repositorio con la base de conocimiento (UC-003)."""

from collections.abc import Callable
from dataclasses import dataclass, field

from spec_to_runtime.sync import rules
from spec_to_runtime.sync.github import RemoteFile, RepositoryUnreachableError

SHA_METADATA_KEY = "git-sha"
RUNNING_STATUSES = {"STARTING", "IN_PROGRESS"}


@dataclass
class Plan:
    new: list[RemoteFile] = field(default_factory=list)
    changed: list[RemoteFile] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: int = 0
    skipped: list[dict[str, str]] = field(default_factory=list)


def make_plan(remote: list[RemoteFile], known: dict[str, str]) -> Plan:
    """Compara el repositorio con lo ya cargado (UC-003 BR-004 y BR-005)."""
    plan = Plan()
    wanted: set[str] = set()
    for file in remote:
        decision = rules.decide(file.path, file.size)
        if not decision.include:
            plan.skipped.append({"path": file.path, "reason": decision.reason})
            continue
        wanted.add(file.path)
        if file.path not in known:
            plan.new.append(file)
        elif known[file.path] != file.sha:
            plan.changed.append(file)
        else:
            plan.unchanged += 1
    plan.removed = sorted(set(known) - wanted)
    return plan


def known_documents(s3, bucket: str) -> dict[str, str]:
    """Rutas ya cargadas y su versión (sha de git) guardada como metadato del objeto."""
    known: dict[str, str] = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for item in page.get("Contents", []):
            head = s3.head_object(Bucket=bucket, Key=item["Key"])
            known[item["Key"]] = head["Metadata"].get(SHA_METADATA_KEY, "")
    return known


def latest_job(bedrock_agent, kb_id: str, ds_id: str) -> dict | None:
    jobs = bedrock_agent.list_ingestion_jobs(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
        sortBy={"attribute": "STARTED_AT", "order": "DESCENDING"},
        maxResults=1,
    )["ingestionJobSummaries"]
    return jobs[0] if jobs else None


def job_summary(job: dict) -> dict:
    stats = job.get("statistics", {})
    return {
        "ingestion_job_id": job["ingestionJobId"],
        "status": job["status"],
        "documents_scanned": stats.get("numberOfDocumentsScanned", 0),
        "documents_failed": stats.get("numberOfDocumentsFailed", 0),
        "started_at": str(job.get("startedAt", "")),
        "updated_at": str(job.get("updatedAt", "")),
    }


def status(bedrock_agent, kb_id: str, ds_id: str) -> dict:
    """Progreso de la última sincronización (UC-003 paso 6 y A2)."""
    job = latest_job(bedrock_agent, kb_id, ds_id)
    return job_summary(job) if job else {"status": "NeverRun"}


def synchronize(
    *,
    s3,
    bedrock_agent,
    bucket: str,
    kb_id: str,
    ds_id: str,
    list_remote: Callable[[], list[RemoteFile]],
    download: Callable[[str], bytes],
) -> dict:
    # A2 / BR-007: una sincronización a la vez.
    running = latest_job(bedrock_agent, kb_id, ds_id)
    if running and running["status"] in RUNNING_STATUSES:
        return {"result": "AlreadyRunning", **job_summary(running)}

    try:
        remote = list_remote()
    except RepositoryUnreachableError as error:  # A3: el conocimiento no cambia
        return {"result": "Failed", "reason": str(error), "knowledge_changed": False}

    plan = make_plan(remote, known_documents(s3, bucket))
    summary = {
        "examined": len(remote),
        "new": len(plan.new),
        "changed": len(plan.changed),
        "removed": len(plan.removed),
        "unchanged": plan.unchanged,
        "skipped": plan.skipped,  # A5
    }
    if not (plan.new or plan.changed or plan.removed):
        return {"result": "NoChanges", **summary}  # A4

    failed: list[dict[str, str]] = []
    for file in [*plan.new, *plan.changed]:
        try:
            s3.put_object(
                Bucket=bucket,
                Key=file.path,
                Body=download(file.path),
                Metadata={SHA_METADATA_KEY: file.sha},
            )
        except Exception as error:  # noqa: BLE001 - A6: se sigue con los demás documentos
            failed.append({"path": file.path, "reason": type(error).__name__})
    for path in plan.removed:
        s3.delete_object(Bucket=bucket, Key=path)

    job = bedrock_agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)[
        "ingestionJob"
    ]
    return {
        "result": "Started",
        **summary,
        "failed": failed,
        "ingestion_job_id": job["ingestionJobId"],
    }

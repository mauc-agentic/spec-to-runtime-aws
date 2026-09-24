"""UC-003 Sincronizar documentos del repositorio (sin AWS ni red)."""

from unittest.mock import MagicMock

import pytest

from spec_to_runtime.sync import handler, rules, sync
from spec_to_runtime.sync.github import RemoteFile, RepositoryUnreachableError


def rf(path, sha="a", size=100):
    return RemoteFile(path, sha, size)


class FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})  # key -> sha
        self.puts, self.deletes = [], []

    def get_paginator(self, _name):
        outer = self

        class Paginator:
            def paginate(self, **_kw):
                return [{"Contents": [{"Key": k} for k in outer.objects]}]

        return Paginator()

    def head_object(self, Bucket, Key):
        return {"Metadata": {sync.SHA_METADATA_KEY: self.objects[Key]}}

    def put_object(self, **kw):
        if kw["Key"].endswith("roto.md"):
            raise OSError("fallo")
        self.puts.append(kw["Key"])
        self.bodies = {**getattr(self, "bodies", {}), kw["Key"]: kw["Body"]}
        self.objects[kw["Key"]] = kw["Metadata"][sync.SHA_METADATA_KEY]

    def delete_object(self, Bucket, Key):
        self.deletes.append(Key)
        self.objects.pop(Key, None)


def fake_agent(job_status=None):
    agent = MagicMock()
    jobs = [{"ingestionJobId": "J0", "status": job_status}] if job_status else []
    agent.list_ingestion_jobs.return_value = {"ingestionJobSummaries": jobs}
    agent.start_ingestion_job.return_value = {"ingestionJob": {"ingestionJobId": "J1"}}
    return agent


def run(remote, s3=None, agent=None, download=lambda _p: b"x"):
    s3, agent = s3 or FakeS3(), agent or fake_agent()
    result = sync.synchronize(
        s3=s3, bedrock_agent=agent, bucket="b", kb_id="kb", ds_id="ds",
        list_remote=lambda: remote, download=download,
    )  # fmt: skip
    return result, s3, agent


def test_uc003_br001_includes_text_files_and_skips_the_rest():
    assert rules.decide("docs/vision.md", 10).include
    assert rules.decide("infra/main.tf", 10).include
    assert rules.decide("src/spec_to_runtime/agent/app.py", 10).include
    assert not rules.decide("logo.png", 10).include  # tipo no soportado
    assert not rules.decide("uv.lock", 10).include  # dependencias
    assert not rules.decide("infra/.terraform.lock.hcl", 10).include
    assert rules.decide("big.md", rules.MAX_BYTES).include
    assert rules.decide("big.md", rules.MAX_BYTES + 1).reason == "too large"


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        "infra/prod.tfvars",
        "infra/terraform.tfstate",
        "infra/x.tfstate.backup",
        "k/id_rsa",
        "a/cert.pem",
    ],
)
def test_uc003_br003_sensitive_files_are_never_loaded(path):
    decision = rules.decide(path, 10)
    assert not decision.include and decision.reason == "sensitive file"


@pytest.mark.parametrize(
    "path",
    ["tests/test_uc004_api.py", "scripts/smoke_test.py", "web/tests/data.json", "scripts/x.md"],
)
def test_uc003_br001_tests_and_scripts_are_not_indexed(path):
    decision = rules.decide(path, 10)
    assert not decision.include and decision.reason == "tests and scripts are not indexed"


@pytest.mark.parametrize(
    "path",
    [
        "docs/test_cases/TC-001-x.md",
        "docs/use_cases/UC-001-x.md",
        "CLAUDE.md",
        "README.md",
        "src/spec_to_runtime/agent/app.py",
    ],
)
def test_uc003_br001_documents_and_application_code_stay_indexed(path):
    assert rules.decide(path, 10).include


def test_uc003_br001_directories_of_dependencies_and_state_are_excluded():
    assert not rules.decide(".venv/lib/x.py", 10).include
    assert not rules.decide("infra/.terraform/providers/a.json", 10).include


def test_uc003_main_flow_loads_new_and_changed_and_removes_deleted():
    s3 = FakeS3({"docs/a.md": "old", "docs/b.md": "same", "docs/gone.md": "x"})
    remote = [
        rf("docs/a.md", "new"),
        rf("docs/b.md", "same"),
        rf("docs/c.md", "c1"),
        rf("logo.png"),
    ]
    result, s3, agent = run(remote, s3)
    assert result["result"] == "Started"
    assert (result["new"], result["changed"], result["removed"], result["unchanged"]) == (
        1,
        1,
        1,
        1,
    )
    assert sorted(s3.puts) == ["docs/a.md", "docs/c.md"]
    assert s3.deletes == ["docs/gone.md"]  # BR-005
    assert result["ingestion_job_id"] == "J1"
    agent.start_ingestion_job.assert_called_once()


def test_uc003_br004_unchanged_documents_are_not_loaded_again():
    s3 = FakeS3({"docs/a.md": "same"})
    result, s3, agent = run([rf("docs/a.md", "same")], s3)
    assert s3.puts == []
    assert result["result"] == "NoChanges"  # A4
    agent.start_ingestion_job.assert_not_called()


def test_uc003_a5_unsupported_files_are_listed_as_skipped():
    result, _, _ = run([rf("docs/a.md"), rf("img/logo.png"), rf("infra/x.tfvars")])
    reasons = {s["path"]: s["reason"] for s in result["skipped"]}
    assert reasons == {"img/logo.png": "unsupported type", "infra/x.tfvars": "sensitive file"}


def test_uc003_a6_a_failing_document_does_not_stop_the_others():
    result, s3, _ = run([rf("docs/roto.md"), rf("docs/ok.md")])
    assert s3.puts == ["docs/ok.md"]
    assert result["failed"] == [{"path": "docs/roto.md", "reason": "OSError"}]
    assert result["result"] == "Started"


def test_uc003_a3_unreachable_repository_leaves_the_knowledge_untouched():
    def boom():
        raise RepositoryUnreachableError("sin red")

    s3, agent = FakeS3({"docs/a.md": "x"}), fake_agent()
    result = sync.synchronize(
        s3=s3, bedrock_agent=agent, bucket="b", kb_id="kb", ds_id="ds", list_remote=boom, download=lambda _p: b""
    )  # fmt: skip
    assert result == {"result": "Failed", "reason": "sin red", "knowledge_changed": False}
    assert s3.puts == [] and s3.deletes == []
    agent.start_ingestion_job.assert_not_called()


@pytest.mark.parametrize("running", ["STARTING", "IN_PROGRESS"])
def test_uc003_a2_br007_only_one_synchronization_at_a_time(running):
    result, s3, agent = run([rf("docs/a.md")], agent=fake_agent(running))
    assert result["result"] == "AlreadyRunning" and result["status"] == running
    assert s3.puts == []
    agent.start_ingestion_job.assert_not_called()


def test_uc003_br008_status_reports_documents_scanned_and_failed():
    agent = MagicMock()
    agent.list_ingestion_jobs.return_value = {
        "ingestionJobSummaries": [
            {
                "ingestionJobId": "J9",
                "status": "COMPLETE",
                "statistics": {"numberOfDocumentsScanned": 40, "numberOfDocumentsFailed": 1},
            }
        ]
    }
    summary = sync.status(agent, "kb", "ds")
    assert summary["documents_scanned"] == 40 and summary["documents_failed"] == 1
    agent.list_ingestion_jobs.return_value = {"ingestionJobSummaries": []}
    assert sync.status(agent, "kb", "ds") == {"status": "NeverRun"}


def test_uc003_handler_dispatches_status_and_sync(monkeypatch):
    for key, value in {
        "KNOWLEDGE_BASE_ID": "kb",
        "DATA_SOURCE_ID": "ds",
        "DOCS_BUCKET": "b",
        "REPO": "o/r",
    }.items():
        monkeypatch.setenv(key, value)
    s3, agent = FakeS3(), fake_agent()
    monkeypatch.setattr(handler, "_clients", lambda: (s3, agent))
    monkeypatch.setattr(handler.github, "list_files", lambda _r, _b: [rf("docs/a.md", "s1")])
    monkeypatch.setattr(handler.github, "download", lambda _r, _b, _p: b"contenido")
    assert handler.handler({"action": "status"}, None) == {"status": "NeverRun"}
    assert handler.handler({}, None)["result"] == "Started"
    assert s3.puts == ["docs/a.md"]


def test_uc003_a6_python_files_with_a_shebang_are_uploaded_without_it():
    # Bedrock rechaza estos archivos con "formato no soportado"; sin la primera línea se indexan.
    s3 = FakeS3()
    scripts = {
        "tools/a.py": b'#!/usr/bin/env python3\n"""Doc."""\nprint(1)\n',
        "src/b.py": b'"""Doc."""\nprint(2)\n',
        "tools/c.sh.md": b"#!/no-es-python\ntexto\n",
    }
    run([rf(path) for path in scripts], s3=s3, download=lambda p: scripts[p])
    assert s3.bodies["tools/a.py"] == b'"""Doc."""\nprint(1)\n'
    assert s3.bodies["src/b.py"] == scripts["src/b.py"]  # sin shebang: intacto
    assert s3.bodies["tools/c.sh.md"] == scripts["tools/c.sh.md"]  # solo se toca .py


@pytest.mark.parametrize(("body", "expected"), [(b"#!/usr/bin/env python3", b""), (b"", b"")])
def test_uc003_a6_a_python_file_that_is_only_a_shebang_becomes_empty(body, expected):
    assert sync.prepare_body("x.py", body) == expected

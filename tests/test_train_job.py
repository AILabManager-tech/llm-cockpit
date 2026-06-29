"""Tests V8 : cycle de vie d'un job (runner mocké, jamais d'entraînement réel)."""

import asyncio
import sys

import pytest

from app import config
from app.db import store
from app.training import job as training_job
from app.training.job import JobError
from app.training.runner import build_runner_argv


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))
    monkeypatch.setattr(config, "ADAPTERS_DIR", str(tmp_path / "adapters"))


def _valid_dataset() -> int:
    return store.insert_dataset(
        ts="2026-06-28T10:00:00+00:00", name="d", path="/x/d.jsonl", rows=3,
        status="valid", detail=None,
    )


class _FakeProc:
    def __init__(self, returncode: int, output: bytes):
        self.returncode = returncode
        self._output = output
        self.terminated = False

    async def communicate(self):
        return (self._output, None)

    def terminate(self):
        self.terminated = True


# --- argv : liste, jamais de shell --------------------------------------


def test_build_runner_argv_is_a_list_no_shell():
    argv = build_runner_argv("my_runner", "/data/d.jsonl", "qwen", "lora", "/out")
    assert isinstance(argv, list)
    assert argv[0] == sys.executable
    assert argv[1] == "-m"
    assert argv[2] == "my_runner"
    assert "--dataset" in argv and "/data/d.jsonl" in argv
    # aucun élément n'est une commande shell composite
    assert all(";" not in a and "&&" not in a for a in argv)


# --- validation de création ---------------------------------------------


def test_create_job_rejects_bad_method(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "TRAIN_BASE_MODEL", "qwen2.5:7b")
    ds_id = _valid_dataset()
    with pytest.raises(JobError):
        asyncio.run(training_job.create_job(ds_id, None, "fullfinetune"))


def test_create_job_rejects_empty_base_model(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "TRAIN_BASE_MODEL", "")
    ds_id = _valid_dataset()
    with pytest.raises(JobError):
        asyncio.run(training_job.create_job(ds_id, None, "lora"))


def test_create_job_rejects_unknown_dataset(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    with pytest.raises(JobError):
        asyncio.run(training_job.create_job(999, "qwen2.5:7b", "lora"))


# --- dry-run : aucun runner configuré -----------------------------------


def test_run_job_dry_run(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "TRAIN_RUNNER", "")           # → dry-run
    ds_id = _valid_dataset()
    job = asyncio.run(training_job.create_job(ds_id, "qwen2.5:7b", "lora"))
    result = asyncio.run(training_job.run_job(job["id"]))
    assert result["status"] == "dry_run"
    assert "dry-run" in result["log_tail"]
    assert result["version_id"] is None
    # Aucune version créée en dry-run.
    assert store.list_model_versions() == []


# --- runner mocké : succès → version créée ------------------------------


def test_run_job_success_creates_version(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "TRAIN_RUNNER", "fake_runner")
    ds_id = _valid_dataset()
    job = asyncio.run(training_job.create_job(ds_id, "qwen2.5:7b", "lora"))

    captured = {}

    async def fake_spawn(*argv, stdout=None, stderr=None):
        captured["argv"] = argv
        return _FakeProc(0, b"epoch 1 ok\ndone")

    result = asyncio.run(training_job.run_job(job["id"], spawn=fake_spawn))
    assert result["status"] == "done"
    assert result["version_id"] is not None
    # argv passé en liste, module allowlisté, jamais de shell.
    assert captured["argv"][0] == sys.executable
    assert "fake_runner" in captured["argv"]

    versions = store.list_model_versions()
    # baseline + candidat.
    statuses = {v["status"] for v in versions}
    assert "baseline" in statuses
    assert "candidate" in statuses


def test_run_job_failure_keeps_baseline(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "TRAIN_RUNNER", "fake_runner")
    ds_id = _valid_dataset()
    job = asyncio.run(training_job.create_job(ds_id, "qwen2.5:7b", "lora"))

    async def fake_spawn(*argv, stdout=None, stderr=None):
        return _FakeProc(1, b"CUDA error")

    result = asyncio.run(training_job.run_job(job["id"], spawn=fake_spawn))
    assert result["status"] == "failed"
    assert result["version_id"] is None
    # Aucun candidat enregistré sur échec.
    assert all(not v["status"] == "candidate" for v in store.list_model_versions())


def test_cancel_job(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    ds_id = _valid_dataset()
    job = asyncio.run(training_job.create_job(ds_id, "qwen2.5:7b", "lora"))
    result = asyncio.run(training_job.cancel_job(job["id"]))
    assert result["status"] == "cancelled"

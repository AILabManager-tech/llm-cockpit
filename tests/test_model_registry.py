"""Tests V8 : versions de modèle, promotion gatée, rollback."""

import pytest

from app import config
from app.db import store
from app.training import registry
from app.training.registry import PromotionError, RegistryError

BASE = "qwen2.5:7b"


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))


def _eval_run(passed: int, total: int) -> int:
    """Crée un run V6 avec un (passed/total) connu."""
    run_id = store.insert_eval_run(
        ts="2026-06-28T10:00:00+00:00", suite="s", role="chat",
        models=["m"], status="completed", total_cases=1,
    )
    store.insert_eval_result(run_id, "s", "chat", {
        "case": "c", "model": "m", "status": "ok", "latency_ms": 1.0,
        "passed": passed, "total": total, "score": passed / total,
        "checks": [], "error": None, "response_preview": None,
    })
    return run_id


def test_ensure_baseline_is_active(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    baseline = registry.ensure_baseline(BASE)
    assert baseline["is_baseline"] is True
    assert baseline["active"] is True
    # idempotent
    again = registry.ensure_baseline(BASE)
    assert again["id"] == baseline["id"]


def test_promote_refused_without_eval(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    vid = registry.register_candidate(
        base_model=BASE, method="lora", adapter_path="/x", job_id=1
    )
    with pytest.raises(PromotionError):
        registry.promote(vid)


def test_promote_refused_when_not_better(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    vid = registry.register_candidate(
        base_model=BASE, method="lora", adapter_path="/x", job_id=1
    )
    baseline = store.get_baseline(BASE)
    registry.attach_eval(baseline["id"], _eval_run(8, 10))   # baseline 0.8
    registry.attach_eval(vid, _eval_run(6, 10))              # candidat 0.6
    with pytest.raises(PromotionError):
        registry.promote(vid)
    # baseline reste actif.
    assert store.get_baseline(BASE)["active"] is True


def test_promote_succeeds_when_better(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    vid = registry.register_candidate(
        base_model=BASE, method="lora", adapter_path="/x", job_id=1
    )
    baseline = store.get_baseline(BASE)
    registry.attach_eval(baseline["id"], _eval_run(5, 10))   # baseline 0.5
    registry.attach_eval(vid, _eval_run(9, 10))              # candidat 0.9

    promoted = registry.promote(vid)
    assert promoted.active is True
    assert store.get_model_version(baseline["id"])["active"] is False


def test_rollback_restores_baseline(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    vid = registry.register_candidate(
        base_model=BASE, method="lora", adapter_path="/x", job_id=1
    )
    baseline = store.get_baseline(BASE)
    registry.attach_eval(baseline["id"], _eval_run(5, 10))
    registry.attach_eval(vid, _eval_run(9, 10))
    registry.promote(vid)
    assert store.get_model_version(vid)["active"] is True

    restored = registry.rollback(vid)
    assert restored.is_baseline is True
    assert restored.active is True
    assert store.get_model_version(vid)["active"] is False


def test_attach_eval_unknown_version(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    with pytest.raises(RegistryError):
        registry.attach_eval(999, _eval_run(1, 1))


def test_serving_status_is_honest(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    vid = registry.register_candidate(
        base_model=BASE, method="lora", adapter_path="/x", job_id=1
    )
    versions = {v.id: v for v in registry.list_versions()}
    baseline = store.get_baseline(BASE)

    # Le candidat n'est jamais présenté comme servi par le gateway.
    assert versions[vid].serving_status == "not_served"
    assert "pas servi" in versions[vid].serving_note
    # Le baseline = le modèle réellement servi par le gateway.
    assert versions[baseline["id"]].serving_status == "served_as_base"


def test_promotion_does_not_make_candidate_served(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    vid = registry.register_candidate(
        base_model=BASE, method="lora", adapter_path="/x", job_id=1
    )
    baseline = store.get_baseline(BASE)
    registry.attach_eval(baseline["id"], _eval_run(5, 10))
    registry.attach_eval(vid, _eval_run(9, 10))

    promoted = registry.promote(vid)
    # Actif dans le registry, MAIS toujours "not_served".
    assert promoted.active is True
    assert promoted.serving_status == "not_served"

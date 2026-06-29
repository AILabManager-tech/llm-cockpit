import json

from app import config
from app.services import action_log


def _use_tmp_log(tmp_path, monkeypatch):
    path = tmp_path / "actions.jsonl"
    monkeypatch.setattr(config, "ACTION_LOG_PATH", str(path))
    return path


def test_append_writes_one_json_line(tmp_path, monkeypatch):
    path = _use_tmp_log(tmp_path, monkeypatch)
    entry = action_log.append_entry(
        action="load", model="a:latest", status="ok", detail="modèle chargé"
    )
    assert entry.action == "load"
    assert path.exists()
    line = path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)  # une vraie ligne JSON
    assert payload["model"] == "a:latest"
    assert payload["status"] == "ok"
    assert payload["provider"] == "ollama"
    assert payload["ts"]


def test_append_is_append_only(tmp_path, monkeypatch):
    path = _use_tmp_log(tmp_path, monkeypatch)
    action_log.append_entry(action="load", model="a:latest", status="ok")
    action_log.append_entry(action="unload", model="a:latest", status="ok")
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(lines) == 2  # rien n'est réécrit


def test_read_limit_newest_first(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    for i in range(5):
        action_log.append_entry(action="test", model=f"m{i}", status="ok")
    entries = action_log.read_entries(limit=2)
    assert len(entries) == 2
    assert entries[0].model == "m4"  # ordre chronologique inverse
    assert entries[1].model == "m3"


def test_read_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ACTION_LOG_PATH", str(tmp_path / "absent.jsonl"))
    assert action_log.read_entries() == []

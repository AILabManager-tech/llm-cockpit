"""Tests V8 : validation de dataset d'adaptation."""

import pytest

from app import config
from app.training import dataset as ds
from app.training.dataset import DatasetError


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))
    d = tmp_path / "datasets"
    d.mkdir()
    monkeypatch.setattr(config, "DATASETS_DIR", str(d))
    monkeypatch.setattr(config, "TRAIN_MIN_ROWS", 1)
    return d


def _write(d, name, content):
    (d / name).write_text(content, encoding="utf-8")


def test_validate_accepts_known_shapes(tmp_path, monkeypatch):
    d = _use_tmp(tmp_path, monkeypatch)
    _write(
        d, "ok.jsonl",
        '{"prompt": "a", "response": "b"}\n'
        '{"instruction": "i", "output": "o"}\n'
        '{"messages": [{"role": "user", "content": "x"}]}\n',
    )
    dataset = ds.create_dataset("mix", "ok.jsonl")
    assert dataset.rows == 3
    assert dataset.status == "valid"


def test_invalid_json_line(tmp_path, monkeypatch):
    d = _use_tmp(tmp_path, monkeypatch)
    _write(d, "bad.jsonl", '{"prompt": "a", "response": "b"}\n{not json}\n')
    with pytest.raises(DatasetError):
        ds.create_dataset("bad", "bad.jsonl")


def test_missing_fields(tmp_path, monkeypatch):
    d = _use_tmp(tmp_path, monkeypatch)
    _write(d, "miss.jsonl", '{"prompt": "a"}\n')
    with pytest.raises(DatasetError):
        ds.create_dataset("miss", "miss.jsonl")


def test_too_small(tmp_path, monkeypatch):
    d = _use_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "TRAIN_MIN_ROWS", 5)
    _write(d, "small.jsonl", '{"prompt": "a", "response": "b"}\n')
    with pytest.raises(DatasetError):
        ds.create_dataset("small", "small.jsonl")


def test_traversal_blocked(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    (tmp_path / "secret.jsonl").write_text(
        '{"prompt": "a", "response": "b"}', encoding="utf-8"
    )
    with pytest.raises(DatasetError):
        ds.create_dataset("x", "../secret.jsonl")

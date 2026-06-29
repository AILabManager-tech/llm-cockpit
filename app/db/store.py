"""Accès SQLite local (seul point d'accès DB). V5 : logs gateway.

Best-effort : un échec d'écriture de log ne doit jamais faire échouer une
requête gateway (erreurs avalées proprement). WAL pour les écritures/lectures
concurrentes. Schéma idempotent appliqué à chaque connexion.
"""

import json
import logging
import sqlite3
from pathlib import Path

from app import config

logger = logging.getLogger("llm_cockpit.db")

_SCHEMA_SQL = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")

_COLUMNS = [
    "ts", "route", "app", "requested", "resolved_role", "provider", "model",
    "status", "http_status", "latency_ms", "prompt_tokens", "completion_tokens",
    "error", "prompt",
]


def connect() -> sqlite3.Connection:
    path = config.DB_PATH
    parent = Path(path).parent
    if str(parent):
        parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA_SQL)
    return conn


def insert_request_log(row: dict) -> None:
    """Insère une ligne de log. Best-effort : avale toute erreur DB."""
    try:
        conn = connect()
        cols = ", ".join(_COLUMNS)
        placeholders = ", ".join("?" for _ in _COLUMNS)
        with conn:
            conn.execute(
                f"INSERT INTO request_log ({cols}) VALUES ({placeholders})",
                [row.get(c) for c in _COLUMNS],
            )
        conn.close()
    except sqlite3.Error as exc:
        logger.warning("log gateway non écrit (best-effort) : %s", exc)


def query_logs(
    *,
    limit: int = 100,
    model: str | None = None,
    provider: str | None = None,
    app: str | None = None,
    status: str | None = None,
) -> list[dict]:
    conn = connect()
    sql = "SELECT * FROM request_log WHERE 1=1"
    params: list = []
    if model:
        sql += " AND model = ?"
        params.append(model)
    if provider:
        sql += " AND provider = ?"
        params.append(provider)
    if app:
        sql += " AND app = ?"
        params.append(app)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_for_stats(cutoff_iso: str | None = None) -> list[dict]:
    """Lignes utiles aux stats (fenêtre optionnelle via cutoff ISO8601)."""
    conn = connect()
    cols = "status, latency_ms, model, provider, app"
    if cutoff_iso:
        rows = conn.execute(
            f"SELECT {cols} FROM request_log WHERE ts >= ?", (cutoff_iso,)
        ).fetchall()
    else:
        rows = conn.execute(f"SELECT {cols} FROM request_log").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- V6 : évaluations (runs + résultats) --------------------------------


def insert_eval_run(
    *, ts: str, suite: str, role: str | None, models: list[str],
    status: str, total_cases: int,
) -> int:
    conn = connect()
    with conn:
        cur = conn.execute(
            "INSERT INTO eval_run (ts, suite, role, models, status, total_cases) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, suite, role, json.dumps(models), status, total_cases),
        )
        run_id = cur.lastrowid
    conn.close()
    return run_id


def insert_eval_result(run_id: int, suite: str, role: str | None, r: dict) -> None:
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO eval_result (run_id, suite, role, case_name, model, "
            "status, latency_ms, passed, total, score, checks, error, "
            "response_preview) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, suite, role, r["case"], r["model"], r["status"],
                r.get("latency_ms"), r["passed"], r["total"], r["score"],
                json.dumps(r.get("checks", [])), r.get("error"),
                r.get("response_preview"),
            ),
        )
    conn.close()


def query_eval_runs(limit: int = 50) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM eval_run ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    out = []
    for row in rows:
        d = dict(row)
        d["models"] = json.loads(d["models"])
        out.append(d)
    return out


def get_eval_run(run_id: int) -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM eval_run WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["models"] = json.loads(d["models"])
    return d


def get_eval_results(run_id: int) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM eval_result WHERE run_id = ? ORDER BY id ASC", (run_id,)
    ).fetchall()
    conn.close()
    out = []
    for row in rows:
        d = dict(row)
        d["case"] = d.pop("case_name")
        d["checks"] = json.loads(d["checks"]) if d.get("checks") else []
        out.append(d)
    return out


def fetch_eval_results(role: str | None = None) -> list[dict]:
    """Lignes brutes pour le scoreboard (agrégation faite en Python)."""
    conn = connect()
    cols = "run_id, role, model, status, latency_ms, passed, total"
    if role:
        rows = conn.execute(
            f"SELECT {cols} FROM eval_result WHERE role = ?", (role,)
        ).fetchall()
    else:
        rows = conn.execute(f"SELECT {cols} FROM eval_result").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- V8 : datasets / jobs / versions ------------------------------------


def insert_dataset(
    *, ts: str, name: str, path: str, rows: int, status: str, detail: str | None
) -> int:
    conn = connect()
    with conn:
        cur = conn.execute(
            "INSERT INTO dataset (ts, name, path, rows, status, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, name, path, rows, status, detail),
        )
        dataset_id = cur.lastrowid
    conn.close()
    return dataset_id


def list_datasets() -> list[dict]:
    conn = connect()
    rows = conn.execute("SELECT * FROM dataset ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dataset(dataset_id: int) -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM dataset WHERE id = ?", (dataset_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def insert_train_job(
    *, ts: str, dataset_id: int, base_model: str, method: str, status: str
) -> int:
    conn = connect()
    with conn:
        cur = conn.execute(
            "INSERT INTO train_job (ts, dataset_id, base_model, method, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, dataset_id, base_model, method, status),
        )
        job_id = cur.lastrowid
    conn.close()
    return job_id


def update_train_job(
    job_id: int, *, status: str | None = None, version_id: int | None = None,
    log_tail: str | None = None,
) -> None:
    sets, params = [], []
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if version_id is not None:
        sets.append("version_id = ?")
        params.append(version_id)
    if log_tail is not None:
        sets.append("log_tail = ?")
        params.append(log_tail)
    if not sets:
        return
    params.append(job_id)
    conn = connect()
    with conn:
        conn.execute(
            f"UPDATE train_job SET {', '.join(sets)} WHERE id = ?", params
        )
    conn.close()


def get_train_job(job_id: int) -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM train_job WHERE id = ?", (job_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_train_jobs() -> list[dict]:
    conn = connect()
    rows = conn.execute("SELECT * FROM train_job ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_model_version(
    *, ts: str, base_model: str, method: str | None, adapter_path: str | None,
    status: str, is_baseline: bool, active: bool, job_id: int | None,
) -> int:
    conn = connect()
    with conn:
        cur = conn.execute(
            "INSERT INTO model_version (ts, base_model, method, adapter_path, "
            "status, is_baseline, active, job_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, base_model, method, adapter_path, status,
             int(is_baseline), int(active), job_id),
        )
        version_id = cur.lastrowid
    conn.close()
    return version_id


def get_model_version(version_id: int) -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM model_version WHERE id = ?", (version_id,)
    ).fetchone()
    conn.close()
    return _version_dict(row) if row else None


def list_model_versions() -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM model_version ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [_version_dict(r) for r in rows]


def get_baseline(base_model: str) -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM model_version WHERE base_model = ? AND is_baseline = 1 "
        "ORDER BY id ASC LIMIT 1",
        (base_model,),
    ).fetchone()
    conn.close()
    return _version_dict(row) if row else None


def set_version_eval(version_id: int, eval_run_id: int, pass_rate: float) -> None:
    conn = connect()
    with conn:
        conn.execute(
            "UPDATE model_version SET eval_run_id = ?, pass_rate = ? WHERE id = ?",
            (eval_run_id, pass_rate, version_id),
        )
    conn.close()


def set_active_version(base_model: str, version_id: int) -> None:
    """Active exactement une version pour ce base_model (les autres désactivées)."""
    conn = connect()
    with conn:
        conn.execute(
            "UPDATE model_version SET active = 0 WHERE base_model = ?",
            (base_model,),
        )
        conn.execute(
            "UPDATE model_version SET active = 1 WHERE id = ?", (version_id,)
        )
    conn.close()


def _version_dict(row) -> dict:
    d = dict(row)
    d["is_baseline"] = bool(d["is_baseline"])
    d["active"] = bool(d["active"])
    return d

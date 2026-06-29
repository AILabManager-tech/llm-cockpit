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

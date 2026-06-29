"""Accès SQLite local (seul point d'accès DB). V5 : logs gateway.

Best-effort : un échec d'écriture de log ne doit jamais faire échouer une
requête gateway (erreurs avalées proprement). WAL pour les écritures/lectures
concurrentes. Schéma idempotent appliqué à chaque connexion.
"""

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

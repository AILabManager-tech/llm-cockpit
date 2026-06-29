"""Store vectoriel local (SQLite, embeddings en JSON). Local-first.

Réutilise la connexion/le schéma centralisés de `app.db.store`. Aucune base
vectorielle serveur : la similarité (cosinus) est calculée en Python lors du
retrieval (cf. query.py), adapté à un cockpit local.
"""

import json

from app.db.store import connect


def insert_document(
    *, ts: str, path: str, name: str, chunks: int, embed_model: str,
    dim: int | None,
) -> int:
    conn = connect()
    with conn:
        cur = conn.execute(
            "INSERT INTO rag_document (ts, path, name, chunks, embed_model, dim) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, path, name, chunks, embed_model, dim),
        )
        doc_id = cur.lastrowid
    conn.close()
    return doc_id


def insert_chunk(
    doc_id: int, ordinal: int, text: str, embedding: list[float]
) -> None:
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO rag_chunk (doc_id, ordinal, text, embedding) "
            "VALUES (?, ?, ?, ?)",
            (doc_id, ordinal, text, json.dumps(embedding)),
        )
    conn.close()


def list_documents() -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM rag_document ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document(doc_id: int) -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM rag_document WHERE id = ?", (doc_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_document(doc_id: int) -> bool:
    conn = connect()
    with conn:
        cur = conn.execute("DELETE FROM rag_document WHERE id = ?", (doc_id,))
        removed = cur.rowcount > 0
        conn.execute("DELETE FROM rag_chunk WHERE doc_id = ?", (doc_id,))
    conn.close()
    return removed


def all_chunks() -> list[dict]:
    """Tous les chunks avec leur embedding décodé et le nom du document."""
    conn = connect()
    rows = conn.execute(
        "SELECT c.id, c.doc_id, c.ordinal, c.text, c.embedding, d.name AS doc_name "
        "FROM rag_chunk c JOIN rag_document d ON d.id = c.doc_id"
    ).fetchall()
    conn.close()
    out = []
    for row in rows:
        d = dict(row)
        d["embedding"] = json.loads(d["embedding"])
        out.append(d)
    return out


def count_chunks() -> int:
    conn = connect()
    n = conn.execute("SELECT COUNT(*) FROM rag_chunk").fetchone()[0]
    conn.close()
    return int(n)

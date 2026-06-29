-- Schéma SQLite V5 (observabilité gateway). Idempotent : CREATE IF NOT EXISTS.
-- Une ligne = une requête gateway /v1/chat/completions (succès, refus ou erreur).

CREATE TABLE IF NOT EXISTS request_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT    NOT NULL,         -- ISO8601 UTC
    route             TEXT    NOT NULL,
    app               TEXT,                     -- en-tête X-Cockpit-App, si fourni
    requested         TEXT,                     -- model demandé (rôle ou modèle réel)
    resolved_role     TEXT,
    provider          TEXT,
    model             TEXT,
    status            TEXT    NOT NULL,         -- "ok" | "error" | "refused"
    http_status       INTEGER NOT NULL,
    latency_ms        REAL,
    prompt_tokens     INTEGER,                  -- NULL si le provider ne les fournit pas
    completion_tokens INTEGER,                  -- NULL si non fournis
    error             TEXT,
    prompt            TEXT                      -- NULL sauf si LOG_PROMPTS=1 (tronqué)
);

CREATE INDEX IF NOT EXISTS idx_request_log_ts ON request_log(ts);
CREATE INDEX IF NOT EXISTS idx_request_log_model ON request_log(model);
CREATE INDEX IF NOT EXISTS idx_request_log_provider ON request_log(provider);

-- V6 : évaluations comparatives. Un run = une suite jouée sur N modèles ;
-- un résultat = un (cas, modèle) avec ses checks déterministes.

CREATE TABLE IF NOT EXISTS eval_run (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    suite       TEXT    NOT NULL,
    role        TEXT,
    models      TEXT    NOT NULL,     -- JSON array des modèles comparés
    status      TEXT    NOT NULL,     -- "completed" | "error"
    total_cases INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS eval_result (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           INTEGER NOT NULL,
    suite            TEXT    NOT NULL,
    role             TEXT,
    case_name        TEXT    NOT NULL,
    model            TEXT    NOT NULL,
    status           TEXT    NOT NULL,   -- "ok" (exécuté) | "error"
    latency_ms       REAL,
    passed           INTEGER NOT NULL,   -- nb de checks réussis
    total            INTEGER NOT NULL,   -- nb de checks
    score            REAL    NOT NULL,   -- passed/total
    checks           TEXT,               -- JSON des résultats de checks
    error            TEXT,
    response_preview TEXT,               -- réponse tronquée (preuve)
    FOREIGN KEY (run_id) REFERENCES eval_run(id)
);

CREATE INDEX IF NOT EXISTS idx_eval_result_run ON eval_result(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_result_role_model ON eval_result(role, model);

-- V7 : RAG local. Store vectoriel local (embeddings JSON, cosinus en Python ;
-- aucune base vectorielle serveur). Documents ingérés depuis data/rag/docs.

CREATE TABLE IF NOT EXISTS rag_document (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    path        TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    chunks      INTEGER NOT NULL,
    embed_model TEXT    NOT NULL,
    dim         INTEGER
);

CREATE TABLE IF NOT EXISTS rag_chunk (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id    INTEGER NOT NULL,
    ordinal   INTEGER NOT NULL,
    text      TEXT    NOT NULL,
    embedding TEXT    NOT NULL,    -- JSON array de floats
    FOREIGN KEY (doc_id) REFERENCES rag_document(id)
);

CREATE INDEX IF NOT EXISTS idx_rag_chunk_doc ON rag_chunk(doc_id);

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

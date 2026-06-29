import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# --- V1 : contrôle sécurisé minimal -------------------------------------
ACTIONS_ENABLED = os.getenv("ACTIONS_ENABLED", "1") not in {"0", "false", "False"}
ACTION_ALLOWLIST = {"load", "unload", "test"}      # figé, jamais élargi
ACTION_TIMEOUT_S = float(os.getenv("ACTION_TIMEOUT_S", "60"))
DATA_DIR = os.getenv("DATA_DIR", "data")
ACTION_LOG_PATH = os.path.join(DATA_DIR, "actions.jsonl")

# --- V2 : rôles locaux (préférence déclarée, mono-provider Ollama) ------
ROLES = ("chat", "code", "vision", "embedding", "fast", "quality", "experimental")
ROLES_CONFIG_PATH = os.getenv("ROLES_CONFIG_PATH", os.path.join(DATA_DIR, "roles.json"))

# --- V3 : registry multi-provider (JSON local, Ollama par défaut) -------
PROVIDERS_CONFIG_PATH = os.getenv(
    "PROVIDERS_CONFIG_PATH", os.path.join(DATA_DIR, "providers.json")
)

# --- V4 : gateway OpenAI-compatible (local uniquement) ------------------
GATEWAY_ENABLED = os.getenv("GATEWAY_ENABLED", "1") not in {"0", "false", "False"}
GATEWAY_DEFAULT_ROLE = os.getenv("GATEWAY_DEFAULT_ROLE", "chat")

# --- V5 : observabilité gateway (SQLite local) --------------------------
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "cockpit.db"))
# Par défaut on NE stocke PAS le contenu des prompts (PII).
LOG_PROMPTS = os.getenv("LOG_PROMPTS", "0") not in {"0", "false", "False"}
LOG_PROMPT_MAX_CHARS = int(os.getenv("LOG_PROMPT_MAX_CHARS", "500"))

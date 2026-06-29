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

# --- V6 : évaluations comparatives locales ------------------------------
# Suites livrées dans le paquet (versionnées) ; surchargeable via EVALS_DIR.
# (data/ étant gitignored, les suites d'exemple vivent dans le paquet.)
EVALS_DIR = os.getenv(
    "EVALS_DIR", os.path.join(os.path.dirname(__file__), "evals", "suites")
)
EVAL_RESPONSE_PREVIEW_MAX = int(os.getenv("EVAL_RESPONSE_PREVIEW_MAX", "500"))

# --- V7 : RAG local mesuré ----------------------------------------------
# Documents ingérés = locaux, gitignored, jamais committés (PII).
RAG_DOCS_DIR = os.getenv("RAG_DOCS_DIR", os.path.join(DATA_DIR, "rag", "docs"))
RAG_EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "nomic-embed-text")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
RAG_SOURCE_PREVIEW_MAX = int(os.getenv("RAG_SOURCE_PREVIEW_MAX", "240"))

# --- V8 : orchestration d'adaptation LoRA/QLoRA -------------------------
# Datasets et adaptateurs = locaux, gitignored, jamais committés.
DATASETS_DIR = os.getenv("DATASETS_DIR", os.path.join(DATA_DIR, "datasets"))
ADAPTERS_DIR = os.getenv("ADAPTERS_DIR", os.path.join(DATA_DIR, "adapters"))
# Modèle de base : vide → refus (jamais d'invention).
TRAIN_BASE_MODEL = os.getenv("TRAIN_BASE_MODEL", "")
# Runner externe allowlisté (module python). Vide → dry-run uniquement.
TRAIN_RUNNER = os.getenv("TRAIN_RUNNER", "")
TRAIN_ALLOWED_METHODS = {"lora", "qlora"}
TRAIN_MIN_ROWS = int(os.getenv("TRAIN_MIN_ROWS", "1"))
TRAIN_LOG_TAIL_MAX = int(os.getenv("TRAIN_LOG_TAIL_MAX", "2000"))

from typing import Any

from pydantic import BaseModel, field_validator


class ModelInfo(BaseModel):
    name: str
    normalized_name: str
    provider: str = "ollama"
    installed: bool = True
    loaded: bool = False
    source: str = "tags"            # "tags" | "ps" | "ps_only"
    size: int | None = None
    size_vram: int | None = None
    digest: str | None = None
    modified_at: str | None = None
    expires_at: str | None = None
    family: str | None = None
    quantization: str | None = None
    raw: dict[str, Any] | None = None   # payload Ollama brut conservé


class ProviderHealth(BaseModel):
    provider: str
    base_url: str
    reachable: bool
    error: str | None = None


# --- V1 : contrôle sécurisé minimal (load / unload / test) --------------


class GenerateRequest(BaseModel):
    model: str
    prompt: str
    options: dict[str, Any] | None = None


class GenerateResult(BaseModel):
    model: str
    response: str
    done: bool
    total_duration_ms: float | None = None
    eval_count: int | None = None
    error: str | None = None


class ActionResult(BaseModel):
    action: str            # "load" | "unload" | "test"
    model: str
    provider: str = "ollama"
    status: str            # "ok" | "error" | "unsupported"
    detail: str | None = None
    duration_ms: float | None = None


class ActionLogEntry(BaseModel):
    ts: str
    action: str
    model: str
    provider: str = "ollama"
    status: str            # "ok" | "error" | "refused" | "unsupported"
    detail: str | None = None


# Corps de requête des endpoints d'action (HTTP body).
class ActionRequest(BaseModel):
    model: str


class TestRequest(BaseModel):
    model: str
    prompt: str | None = None


# --- V2 : rôles locaux de modèles ---------------------------------------


class RoleAssignment(BaseModel):
    role: str
    provider: str = "ollama"
    model: str | None = None        # None = rôle déclaré mais non assigné
    updated_at: str | None = None


# Corps de requête des endpoints de rôle (HTTP body).
class RoleAssignRequest(BaseModel):
    model: str


class RoleTestRequest(BaseModel):
    prompt: str | None = None


# --- V3 : registry multi-provider ---------------------------------------


class ProviderConfig(BaseModel):
    id: str
    kind: str                # "ollama" | "openai_compat"
    base_url: str
    enabled: bool = True


class ProviderCapabilities(BaseModel):
    list_installed: bool = False
    list_loaded: bool = False
    load: bool = False
    unload: bool = False
    generate: bool = False


class ProviderStatus(BaseModel):
    id: str
    kind: str
    base_url: str
    enabled: bool
    reachable: bool
    error: str | None = None
    capabilities: ProviderCapabilities
    model_count: int = 0


class RegistryDrift(BaseModel):
    provider_id: str
    base_url: str
    enabled: bool
    reachable: bool
    drift: bool
    detail: str | None = None


# Corps de requête de l'enregistrement d'un provider (HTTP body).
class ProviderRegisterRequest(BaseModel):
    id: str
    kind: str
    base_url: str
    enabled: bool = True


# --- V4 : gateway OpenAI-compatible (chat + routage) --------------------


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    # `model` peut être un nom de rôle ("code", "role:code") ou un modèle réel.
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool = False            # streaming hors scope V4 : ignoré


class ChatResult(BaseModel):
    model: str
    message: ChatMessage
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None


class RouteDecision(BaseModel):
    requested: str
    resolved_role: str | None = None
    provider: str | None = None
    model: str | None = None
    ok: bool
    reason: str


# --- V5 : observabilité (logs gateway + stats) --------------------------


class RequestLog(BaseModel):
    id: int
    ts: str
    route: str
    app: str | None = None
    requested: str | None = None
    resolved_role: str | None = None
    provider: str | None = None
    model: str | None = None
    status: str                       # "ok" | "error" | "refused"
    http_status: int
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error: str | None = None
    # NB : le contenu du prompt n'est jamais exposé via l'API (champ omis).


class StatsBucket(BaseModel):
    key: str
    count: int
    error_count: int


class StatsSummary(BaseModel):
    window_seconds: int | None = None
    total: int
    errors: int
    error_rate: float
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    by_model: list[StatsBucket] = []
    by_provider: list[StatsBucket] = []
    by_app: list[StatsBucket] = []


# --- V6 : évaluations comparatives --------------------------------------


class EvalCheckResult(BaseModel):
    check: str                      # spec brut, ex. "json_valid", "contains:ok"
    passed: bool
    detail: str | None = None


class EvalCaseResult(BaseModel):
    case: str
    model: str
    status: str                     # "ok" (exécuté) | "error"
    latency_ms: float | None = None
    passed: int                     # checks réussis
    total: int                      # checks au total
    score: float                    # passed / total
    checks: list[EvalCheckResult] = []
    error: str | None = None
    response_preview: str | None = None


class EvalRunSummary(BaseModel):
    id: int
    ts: str
    suite: str
    role: str | None = None
    models: list[str]
    status: str                     # "completed" | "error"
    total_cases: int
    results: list[EvalCaseResult] = []


class ScoreboardRow(BaseModel):
    role: str | None = None
    model: str
    runs: int
    cases: int
    checks_passed: int
    checks_total: int
    pass_rate: float
    avg_latency_ms: float | None = None
    errors: int


def _csv_to_list(value):
    # Accepte une liste OU une chaîne "a, b" (pratique pour l'UI HTMX).
    if isinstance(value, str):
        return [m.strip() for m in value.split(",") if m.strip()]
    return value


class EvalRunRequest(BaseModel):
    suite: str
    models: list[str]

    @field_validator("models", mode="before")
    @classmethod
    def _split_csv(cls, value):
        return _csv_to_list(value)


# --- V7 : RAG local mesuré ----------------------------------------------


class RagDocument(BaseModel):
    id: int
    ts: str
    path: str
    name: str
    chunks: int
    embed_model: str
    dim: int | None = None


class RagSource(BaseModel):
    doc_id: int
    doc_name: str
    ordinal: int
    score: float
    preview: str


class RagAnswer(BaseModel):
    query: str
    answer: str
    used_rag: bool
    model: str | None = None
    sources: list[RagSource] = []
    error: str | None = None


class RagIngestRequest(BaseModel):
    path: str


class RagQueryRequest(BaseModel):
    query: str
    role: str | None = None


class RagEvalRequest(BaseModel):
    suite: str
    with_rag: bool = True
    models: list[str]

    @field_validator("models", mode="before")
    @classmethod
    def _split_csv(cls, value):
        return _csv_to_list(value)


# --- V8 : orchestration d'adaptation LoRA/QLoRA -------------------------


class Dataset(BaseModel):
    id: int
    ts: str
    name: str
    path: str
    rows: int
    status: str
    detail: str | None = None


class TrainJob(BaseModel):
    id: int
    ts: str
    dataset_id: int
    base_model: str
    method: str
    status: str            # pending|running|done|failed|cancelled|dry_run
    version_id: int | None = None
    log_tail: str | None = None


class ModelVersion(BaseModel):
    id: int
    ts: str
    base_model: str
    method: str | None = None
    adapter_path: str | None = None
    status: str            # "baseline" | "candidate"
    is_baseline: bool = False
    active: bool = False    # actif DANS LE REGISTRY ≠ servi par le gateway
    eval_run_id: int | None = None
    pass_rate: float | None = None
    job_id: int | None = None
    # V8 : état de serving explicite (anti-trompeur).
    # "served_as_base" (baseline = modèle réellement servi) | "not_served".
    serving_status: str = "not_served"
    serving_note: str = ""


# Corps de requête V8.
class DatasetCreateRequest(BaseModel):
    name: str
    path: str


class TrainRequest(BaseModel):
    dataset_id: int
    base_model: str | None = None
    method: str = "lora"


class VersionEvalRequest(BaseModel):
    eval_run_id: int


class PromoteRequest(BaseModel):
    version_id: int


class RollbackRequest(BaseModel):
    version_id: int

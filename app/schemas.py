from typing import Any

from pydantic import BaseModel


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

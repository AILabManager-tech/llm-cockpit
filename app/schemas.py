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

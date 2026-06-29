from abc import ABC, abstractmethod

from app.schemas import (
    ActionResult,
    GenerateRequest,
    GenerateResult,
    ModelInfo,
    ProviderCapabilities,
    ProviderHealth,
)


class ProviderAdapter(ABC):
    @abstractmethod
    async def healthcheck(self) -> ProviderHealth: ...

    @abstractmethod
    async def list_installed(self) -> list[ModelInfo]: ...

    @abstractmethod
    async def list_loaded(self) -> list[ModelInfo]: ...

    # --- V1 : contrôle (load / unload / test) ---------------------------

    @abstractmethod
    async def load(self, model: str, keep_alive: str = "5m") -> ActionResult: ...

    @abstractmethod
    async def unload(self, model: str) -> ActionResult: ...

    @abstractmethod
    async def generate(self, req: GenerateRequest) -> GenerateResult: ...

    # --- V3 : capacités déclaratives (sync) -----------------------------

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

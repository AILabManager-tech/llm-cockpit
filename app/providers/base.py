from abc import ABC, abstractmethod

from app.schemas import ModelInfo, ProviderHealth


class ProviderAdapter(ABC):
    @abstractmethod
    async def healthcheck(self) -> ProviderHealth: ...

    @abstractmethod
    async def list_installed(self) -> list[ModelInfo]: ...

    @abstractmethod
    async def list_loaded(self) -> list[ModelInfo]: ...

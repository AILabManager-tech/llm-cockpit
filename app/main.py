from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config
from app.providers.ollama import OllamaAdapter
from app.schemas import ModelInfo, ProviderHealth
from app.services.inventory import InventoryService

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="LLM Cockpit V0", description="Inventaire Ollama, lecture seule.")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def get_adapter() -> OllamaAdapter:
    return OllamaAdapter(base_url=config.OLLAMA_BASE_URL)


def get_inventory() -> InventoryService:
    return InventoryService(get_adapter())


# --- JSON ---------------------------------------------------------------


@app.get("/api/health", response_model=ProviderHealth)
async def api_health() -> ProviderHealth:
    return await get_adapter().healthcheck()


@app.get("/api/models", response_model=list[ModelInfo])
async def api_models() -> list[ModelInfo]:
    return await get_inventory().get_inventory()


@app.get("/api/models/installed", response_model=list[ModelInfo])
async def api_models_installed() -> list[ModelInfo]:
    return await get_adapter().list_installed()


@app.get("/api/models/loaded", response_model=list[ModelInfo])
async def api_models_loaded() -> list[ModelInfo]:
    return await get_adapter().list_loaded()


# --- HTML (HTMX) --------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    health = await get_adapter().healthcheck()
    models = await get_inventory().get_inventory()
    return templates.TemplateResponse(
        request,
        "inventory.html",
        {"health": health, "models": models},
    )


@app.get("/partials/models", response_class=HTMLResponse)
async def partials_models(request: Request) -> HTMLResponse:
    health = await get_adapter().healthcheck()
    models = await get_inventory().get_inventory()
    return templates.TemplateResponse(
        request,
        "partials/models_table.html",
        {"health": health, "models": models},
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()

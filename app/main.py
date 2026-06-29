from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config
from app.providers.ollama import OllamaAdapter
from app.schemas import (
    ActionLogEntry,
    ActionRequest,
    ActionResult,
    ModelInfo,
    ProviderHealth,
    TestRequest,
)
from app.services import action_log
from app.services.actions import ActionService
from app.services.inventory import InventoryService

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="LLM Cockpit V0", description="Inventaire Ollama, lecture seule.")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def get_adapter() -> OllamaAdapter:
    return OllamaAdapter(base_url=config.OLLAMA_BASE_URL)


def get_inventory() -> InventoryService:
    return InventoryService(get_adapter())


def get_action_service() -> ActionService:
    adapter = get_adapter()
    return ActionService(adapter, InventoryService(adapter))


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


# --- V1 : actions de contrôle (load / unload / test) --------------------


@app.post("/api/actions/load", response_model=ActionResult)
async def action_load(payload: ActionRequest, response: Response) -> ActionResult:
    result, status_code = await get_action_service().run("load", payload.model)
    response.status_code = status_code
    return result


@app.post("/api/actions/unload", response_model=ActionResult)
async def action_unload(payload: ActionRequest, response: Response) -> ActionResult:
    result, status_code = await get_action_service().run("unload", payload.model)
    response.status_code = status_code
    return result


@app.post("/api/actions/test", response_model=ActionResult)
async def action_test(payload: TestRequest, response: Response) -> ActionResult:
    result, status_code = await get_action_service().run(
        "test", payload.model, prompt=payload.prompt
    )
    response.status_code = status_code
    return result


@app.get("/api/actions/log", response_model=list[ActionLogEntry])
async def actions_log(limit: int | None = None) -> list[ActionLogEntry]:
    return action_log.read_entries(limit=limit)


# --- HTML (HTMX) --------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    health = await get_adapter().healthcheck()
    models = await get_inventory().get_inventory()
    return templates.TemplateResponse(
        request,
        "inventory.html",
        {
            "health": health,
            "models": models,
            "actions_enabled": config.ACTIONS_ENABLED,
            "entries": action_log.read_entries(limit=50),
        },
    )


@app.get("/partials/models", response_class=HTMLResponse)
async def partials_models(request: Request) -> HTMLResponse:
    health = await get_adapter().healthcheck()
    models = await get_inventory().get_inventory()
    return templates.TemplateResponse(
        request,
        "partials/models_table.html",
        {
            "health": health,
            "models": models,
            "actions_enabled": config.ACTIONS_ENABLED,
        },
    )


@app.get("/partials/actions", response_class=HTMLResponse)
async def partials_actions(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/actions_panel.html",
        {
            "entries": action_log.read_entries(limit=50),
            "actions_enabled": config.ACTIONS_ENABLED,
        },
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()

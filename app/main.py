from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
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
    RoleAssignment,
    RoleAssignRequest,
    RoleTestRequest,
    TestRequest,
)
from app.services import action_log
from app.services.actions import ActionService
from app.services.inventory import InventoryService
from app.services.roles import (
    ModelNotInstalledError,
    RoleNotAssignedError,
    RoleService,
    RolesConfigError,
    UnknownRoleError,
)

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


def get_role_service() -> RoleService:
    adapter = get_adapter()
    inventory = InventoryService(adapter)
    return RoleService(inventory, ActionService(adapter, inventory))


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


# --- V2 : rôles locaux (assignation + test de rôle) ---------------------


@app.get("/api/roles", response_model=list[RoleAssignment])
async def api_roles() -> list[RoleAssignment]:
    try:
        return await get_role_service().list_roles()
    except RolesConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/roles/{role}", response_model=RoleAssignment)
async def api_set_role(role: str, payload: RoleAssignRequest) -> RoleAssignment:
    try:
        return await get_role_service().set_role(role, payload.model)
    except UnknownRoleError as exc:
        raise HTTPException(status_code=400, detail=f"rôle inconnu : {exc}") from exc
    except ModelNotInstalledError as exc:
        raise HTTPException(
            status_code=400, detail=f"modèle non installé : {exc}"
        ) from exc
    except RolesConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/roles/{role}/test", response_model=ActionResult)
async def api_test_role(
    role: str, response: Response, payload: RoleTestRequest | None = None
) -> ActionResult:
    prompt = payload.prompt if payload else None
    try:
        result, status_code = await get_role_service().test_role(role, prompt=prompt)
    except UnknownRoleError as exc:
        raise HTTPException(status_code=400, detail=f"rôle inconnu : {exc}") from exc
    except RoleNotAssignedError as exc:
        raise HTTPException(
            status_code=400, detail=f"rôle non assigné : {exc}"
        ) from exc
    except RolesConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response.status_code = status_code
    return result


# --- HTML (HTMX) --------------------------------------------------------


async def _roles_view() -> tuple[list[RoleAssignment], str | None]:
    """Retourne (rôles, message d'erreur). N'explose jamais l'UI si corrompu."""
    try:
        return await get_role_service().list_roles(), None
    except RolesConfigError as exc:
        return [], str(exc)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    health = await get_adapter().healthcheck()
    models = await get_inventory().get_inventory()
    roles, roles_error = await _roles_view()
    return templates.TemplateResponse(
        request,
        "inventory.html",
        {
            "health": health,
            "models": models,
            "actions_enabled": config.ACTIONS_ENABLED,
            "entries": action_log.read_entries(limit=50),
            "roles": roles,
            "roles_error": roles_error,
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


@app.get("/partials/roles", response_class=HTMLResponse)
async def partials_roles(request: Request) -> HTMLResponse:
    models = await get_inventory().get_inventory()
    roles, roles_error = await _roles_view()
    return templates.TemplateResponse(
        request,
        "partials/roles_panel.html",
        {"models": models, "roles": roles, "roles_error": roles_error},
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()

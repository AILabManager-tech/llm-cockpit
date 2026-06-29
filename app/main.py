from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config
from app.db import store
from app.evals import scoreboard as scoreboard_service
from app.evals.runner import (
    EvalRunner,
    EvalValidationError,
    SuiteError,
    list_suites,
)
from app.gateway.openai import router as gateway_router
from app.providers.ollama import OllamaAdapter
from app.rag import eval_bridge
from app.rag import query as rag_query
from app.rag import store as rag_store
from app.rag.embed import EmbeddingError, EmbeddingModelMissing
from app.rag.ingest import IngestError, ingest_document
from app.schemas import (
    ActionLogEntry,
    ActionRequest,
    ActionResult,
    EvalRunRequest,
    EvalRunSummary,
    ModelInfo,
    ProviderConfig,
    ProviderHealth,
    ProviderRegisterRequest,
    ProviderStatus,
    RagAnswer,
    RagDocument,
    RagEvalRequest,
    RagIngestRequest,
    RagQueryRequest,
    RegistryDrift,
    RequestLog,
    RoleAssignment,
    RoleAssignRequest,
    RoleTestRequest,
    RouteDecision,
    ScoreboardRow,
    StatsSummary,
    TestRequest,
)
from app.services import action_log, stats
from app.services.actions import ActionService
from app.services.inventory import InventoryService
from app.services.registry import (
    DuplicateProviderError,
    RegistryConfigError,
    RegistryService,
    UnknownProviderError,
    UnknownProviderKindError,
)
from app.services.roles import (
    ModelNotInstalledError,
    RoleNotAssignedError,
    RoleService,
    RolesConfigError,
    UnknownRoleError,
)
from app.services.routing import RoutingService

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="LLM Cockpit", description="Cockpit local-first multi-LLM.")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# V4 : gateway OpenAI-compatible (routes /v1/*), local uniquement.
app.include_router(gateway_router)


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


def get_registry() -> RegistryService:
    return RegistryService()


def get_routing() -> RoutingService:
    return RoutingService(get_registry())


def get_eval_runner() -> EvalRunner:
    return EvalRunner(get_registry(), get_routing())


# --- JSON ---------------------------------------------------------------


@app.get("/api/health", response_model=ProviderHealth)
async def api_health() -> ProviderHealth:
    return await get_adapter().healthcheck()


@app.get("/api/models", response_model=list[ModelInfo])
async def api_models() -> list[ModelInfo]:
    # V3 : inventaire agrégé multi-provider (forme list[ModelInfo] inchangée).
    try:
        return await get_registry().aggregate_inventory()
    except RegistryConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


# --- V3 : registry multi-provider ---------------------------------------


@app.get("/api/providers", response_model=list[ProviderStatus])
async def api_providers() -> list[ProviderStatus]:
    try:
        return await get_registry().provider_statuses()
    except RegistryConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/providers", response_model=ProviderConfig)
async def api_register_provider(
    payload: ProviderRegisterRequest, response: Response
) -> ProviderConfig:
    pc = ProviderConfig(
        id=payload.id,
        kind=payload.kind,
        base_url=payload.base_url,
        enabled=payload.enabled,
    )
    try:
        registered = get_registry().register(pc)
    except UnknownProviderKindError as exc:
        raise HTTPException(
            status_code=400, detail=f"kind de provider inconnu : {exc}"
        ) from exc
    except DuplicateProviderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RegistryConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response.status_code = 201
    return registered


@app.delete("/api/providers/{provider_id}")
async def api_remove_provider(provider_id: str) -> dict:
    try:
        get_registry().remove(provider_id)
    except UnknownProviderError as exc:
        raise HTTPException(
            status_code=404, detail=f"provider inconnu : {exc}"
        ) from exc
    except RegistryConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"removed": provider_id}


@app.get("/api/registry/drift", response_model=list[RegistryDrift])
async def api_registry_drift() -> list[RegistryDrift]:
    try:
        return await get_registry().compute_drift()
    except RegistryConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- V4 : table de routage (résolution rôle → provider/modèle) ----------


@app.get("/api/routes", response_model=list[RouteDecision])
async def api_routes() -> list[RouteDecision]:
    try:
        return await get_routing().routing_table()
    except (RegistryConfigError, RolesConfigError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- V5 : observabilité (logs gateway + stats) --------------------------


@app.get("/api/logs", response_model=list[RequestLog])
async def api_logs(
    limit: int = 100,
    model: str | None = None,
    provider: str | None = None,
    app_filter: str | None = Query(None, alias="app"),
    status: str | None = None,
) -> list[RequestLog]:
    return store.query_logs(
        limit=limit, model=model, provider=provider, app=app_filter, status=status
    )


@app.get("/api/stats", response_model=StatsSummary)
async def api_stats(window: int | None = None) -> StatsSummary:
    return stats.compute_stats(window_seconds=window)


# --- V6 : évaluations comparatives --------------------------------------


@app.post("/api/evals/run", response_model=EvalRunSummary)
async def api_eval_run(payload: EvalRunRequest) -> EvalRunSummary:
    try:
        return await get_eval_runner().run(payload.suite, payload.models)
    except SuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EvalValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/evals", response_model=list[EvalRunSummary])
async def api_evals(limit: int = 50) -> list[EvalRunSummary]:
    return store.query_eval_runs(limit=limit)


@app.get("/api/evals/{run_id}", response_model=EvalRunSummary)
async def api_eval_detail(run_id: int) -> EvalRunSummary:
    run = store.get_eval_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run inconnu : {run_id}")
    return {**run, "results": store.get_eval_results(run_id)}


@app.get("/api/scoreboard", response_model=list[ScoreboardRow])
async def api_scoreboard(role: str | None = None) -> list[ScoreboardRow]:
    return scoreboard_service.compute_scoreboard(role=role)


# --- V7 : RAG local mesuré ----------------------------------------------


@app.post("/api/rag/ingest", response_model=RagDocument)
async def api_rag_ingest(payload: RagIngestRequest) -> RagDocument:
    try:
        return await ingest_document(payload.path)
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmbeddingModelMissing as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/rag/documents", response_model=list[RagDocument])
async def api_rag_documents() -> list[RagDocument]:
    return rag_store.list_documents()


@app.delete("/api/rag/documents/{doc_id}")
async def api_rag_delete(doc_id: int) -> dict:
    if not rag_store.delete_document(doc_id):
        raise HTTPException(status_code=404, detail=f"document inconnu : {doc_id}")
    return {"removed": doc_id}


@app.post("/api/rag/query", response_model=RagAnswer)
async def api_rag_query(payload: RagQueryRequest) -> RagAnswer:
    try:
        return await rag_query.answer(payload.query, role=payload.role)
    except EmbeddingModelMissing as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/rag/eval", response_model=EvalRunSummary)
async def api_rag_eval(payload: RagEvalRequest) -> EvalRunSummary:
    try:
        return await eval_bridge.run_eval(
            get_eval_runner(), payload.suite, payload.with_rag, payload.models
        )
    except (SuiteError, EvalValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmbeddingModelMissing as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# --- HTML (HTMX) --------------------------------------------------------


async def _gateway_view() -> tuple[list[RouteDecision], str | None]:
    """(table de routage, message d'erreur). N'explose jamais l'UI."""
    try:
        return await get_routing().routing_table(), None
    except (RegistryConfigError, RolesConfigError) as exc:
        return [], str(exc)


async def _providers_view() -> tuple[
    list[ProviderStatus], list[RegistryDrift], str | None
]:
    """(statuts, drift, message d'erreur). N'explose jamais l'UI si corrompu."""
    registry = get_registry()
    try:
        statuses = await registry.provider_statuses()
        drift = await registry.compute_drift()
        return statuses, drift, None
    except RegistryConfigError as exc:
        return [], [], str(exc)


async def _roles_view() -> tuple[list[RoleAssignment], str | None]:
    """Retourne (rôles, message d'erreur). N'explose jamais l'UI si corrompu."""
    try:
        return await get_role_service().list_roles(), None
    except RolesConfigError as exc:
        return [], str(exc)


async def _aggregate_models() -> list[ModelInfo]:
    """Inventaire agrégé multi-provider ; [] si registry corrompu (UI robuste)."""
    try:
        return await get_registry().aggregate_inventory()
    except RegistryConfigError:
        return []


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    health = await get_adapter().healthcheck()
    models = await _aggregate_models()
    roles, roles_error = await _roles_view()
    providers, drift, providers_error = await _providers_view()
    routes, gateway_error = await _gateway_view()
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
            "providers": providers,
            "drift": drift,
            "providers_error": providers_error,
            "routes": routes,
            "gateway_error": gateway_error,
            "gateway_enabled": config.GATEWAY_ENABLED,
        },
    )


@app.get("/partials/models", response_class=HTMLResponse)
async def partials_models(request: Request) -> HTMLResponse:
    health = await get_adapter().healthcheck()
    models = await _aggregate_models()
    return templates.TemplateResponse(
        request,
        "partials/models_table.html",
        {
            "health": health,
            "models": models,
            "actions_enabled": config.ACTIONS_ENABLED,
        },
    )


@app.get("/partials/providers", response_class=HTMLResponse)
async def partials_providers(request: Request) -> HTMLResponse:
    providers, drift, providers_error = await _providers_view()
    return templates.TemplateResponse(
        request,
        "partials/providers_panel.html",
        {"providers": providers, "drift": drift, "providers_error": providers_error},
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


@app.get("/partials/gateway", response_class=HTMLResponse)
async def partials_gateway(request: Request) -> HTMLResponse:
    routes, gateway_error = await _gateway_view()
    return templates.TemplateResponse(
        request,
        "partials/gateway_panel.html",
        {
            "routes": routes,
            "gateway_error": gateway_error,
            "gateway_enabled": config.GATEWAY_ENABLED,
        },
    )


# --- V5 : dashboard d'observabilité -------------------------------------


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "summary": stats.compute_stats(),
            "logs": store.query_logs(limit=50),
            # Contexte des panneaux inclus en ligne (scoreboard V6, RAG V7).
            "scoreboard": scoreboard_service.compute_scoreboard(),
            "runs": store.query_eval_runs(limit=10),
            "suites": list_suites(),
            "documents": rag_store.list_documents(),
            "embed_model": config.RAG_EMBED_MODEL,
            "answer": None,
        },
    )


@app.get("/partials/dashboard", response_class=HTMLResponse)
async def partials_dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/dashboard.html",
        {
            "summary": stats.compute_stats(),
            "logs": store.query_logs(limit=50),
        },
    )


@app.get("/partials/scoreboard", response_class=HTMLResponse)
async def partials_scoreboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/scoreboard.html",
        {
            "scoreboard": scoreboard_service.compute_scoreboard(),
            "runs": store.query_eval_runs(limit=10),
            "suites": list_suites(),
        },
    )


@app.get("/partials/rag", response_class=HTMLResponse)
async def partials_rag(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/rag_panel.html",
        {
            "documents": rag_store.list_documents(),
            "embed_model": config.RAG_EMBED_MODEL,
            "answer": None,
        },
    )


@app.post("/partials/rag/query", response_class=HTMLResponse)
async def partials_rag_query(
    request: Request, payload: RagQueryRequest
) -> HTMLResponse:
    answer: RagAnswer | None = None
    error: str | None = None
    try:
        answer = await rag_query.answer(payload.query, role=payload.role)
    except (EmbeddingModelMissing, EmbeddingError) as exc:
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "partials/rag_answer.html",
        {"answer": answer, "error": error},
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()

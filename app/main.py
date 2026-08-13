import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime

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
    Dataset,
    DatasetCreateRequest,
    EvalRunRequest,
    EvalRunSummary,
    GpuMemory,
    ModelInfo,
    ModelVersion,
    PromoteRequest,
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
    RollbackRequest,
    RouteDecision,
    ScoreboardRow,
    StatsSummary,
    TestRequest,
    TrainJob,
    TrainRequest,
    VersionEvalRequest,
)
from app.services import action_log, stats
from app.services.actions import ActionService
from app.services.inventory import InventoryService
from app.training import job as training_job
from app.training import registry as model_registry
from app.training.dataset import DatasetError, create_dataset
from app.training.job import JobError
from app.training.registry import PromotionError, RegistryError
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
from app.services import gpu as gpu_service
from app.services.routing import RoutingService

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="LLM Cockpit", description="Cockpit local-first multi-LLM.")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _short_timestamp(value: str | None) -> str:
    """ISO timestamps are unreadable in a table: keep minutes, drop the rest."""
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return value


templates.env.filters["short_ts"] = _short_timestamp
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


@app.get("/api/gpu", response_model=GpuMemory | None)
async def api_gpu() -> GpuMemory | None:
    """Current GPU memory, or null when no GPU can be read."""
    return gpu_service.read_memory()


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
        raise HTTPException(status_code=400, detail=f"unknown role: {exc}") from exc
    except ModelNotInstalledError as exc:
        raise HTTPException(
            status_code=400, detail=f"model not installed: {exc}"
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
        raise HTTPException(status_code=400, detail=f"unknown role: {exc}") from exc
    except RoleNotAssignedError as exc:
        raise HTTPException(
            status_code=400, detail=f"role not assigned: {exc}"
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


# --- V8 : orchestration d'adaptation LoRA/QLoRA -------------------------


@app.post("/api/datasets", response_model=Dataset)
async def api_create_dataset(payload: DatasetCreateRequest) -> Dataset:
    try:
        return create_dataset(payload.name, payload.path)
    except DatasetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/datasets", response_model=list[Dataset])
async def api_datasets() -> list[Dataset]:
    return store.list_datasets()


@app.post("/api/train", response_model=TrainJob)
async def api_train(payload: TrainRequest) -> TrainJob:
    try:
        job = await training_job.create_job(
            payload.dataset_id, payload.base_model, payload.method
        )
    except JobError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Supervision en arrière-plan : la requête ne bloque pas (dry-run ou runner).
    asyncio.create_task(training_job.run_job(job["id"]))
    return job


@app.get("/api/train/{job_id}", response_model=TrainJob)
async def api_train_status(job_id: int) -> TrainJob:
    job = store.get_train_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job inconnu : {job_id}")
    return job


@app.post("/api/train/{job_id}/cancel", response_model=TrainJob)
async def api_train_cancel(job_id: int) -> TrainJob:
    try:
        return await training_job.cancel_job(job_id)
    except JobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/models/versions", response_model=list[ModelVersion])
async def api_model_versions() -> list[ModelVersion]:
    return model_registry.list_versions()


@app.post("/api/models/versions/{version_id}/eval", response_model=ModelVersion)
async def api_version_attach_eval(
    version_id: int, payload: VersionEvalRequest
) -> ModelVersion:
    try:
        return model_registry.attach_eval(version_id, payload.eval_run_id)
    except RegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/models/promote", response_model=ModelVersion)
async def api_model_promote(payload: PromoteRequest) -> ModelVersion:
    try:
        return model_registry.promote(payload.version_id)
    except RegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PromotionError as exc:
        # Gating par la preuve V6 : refus explicite.
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/models/rollback", response_model=ModelVersion)
async def api_model_rollback(payload: RollbackRequest) -> ModelVersion:
    try:
        return model_registry.rollback(payload.version_id)
    except RegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
async def page_models(request: Request) -> HTMLResponse:
    """What is installed, what is loaded, what you act on daily."""
    health = await get_adapter().healthcheck()
    models = await _aggregate_models()
    return templates.TemplateResponse(
        request,
        "models.html",
        {
            "active_tab": "/",
            "health": health,
            "models": models,
            "gpu": gpu_service.read_memory(),
            "fit": gpu_service.fit_verdict,
            "actions_enabled": config.ACTIONS_ENABLED,
            "entries": action_log.read_entries(limit=50),
        },
    )


@app.get("/routing", response_class=HTMLResponse)
async def page_routing(request: Request) -> HTMLResponse:
    """Which model answers for which role, and through which provider."""
    models = await _aggregate_models()
    roles, roles_error = await _roles_view()
    providers, drift, providers_error = await _providers_view()
    routes, gateway_error = await _gateway_view()
    return templates.TemplateResponse(
        request,
        "routing.html",
        {
            "active_tab": "/routing",
            "models": models,
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


@app.get("/traffic", response_class=HTMLResponse)
async def page_traffic(request: Request) -> HTMLResponse:
    """What actually went through the gateway."""
    return templates.TemplateResponse(
        request,
        "traffic.html",
        {
            "active_tab": "/traffic",
            "summary": stats.compute_stats(),
            "logs": store.query_logs(limit=50),
        },
    )


@app.get("/lab", response_class=HTMLResponse)
async def page_lab(request: Request) -> HTMLResponse:
    """Evaluations, RAG and adaptation — one loop, one tab."""
    return templates.TemplateResponse(
        request,
        "lab.html",
        {
            "active_tab": "/lab",
            "scoreboard": scoreboard_service.compute_scoreboard(),
            "runs": store.query_eval_runs(limit=10),
            "suites": list_suites(),
            "documents": rag_store.list_documents(),
            "embed_model": config.RAG_EMBED_MODEL,
            "answer": None,
            **_training_context(),
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def page_dashboard_redirect() -> RedirectResponse:
    """The dashboard became Traffic; old links keep working."""
    return RedirectResponse("/traffic", status_code=308)


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
            "gpu": gpu_service.read_memory(),
            "fit": gpu_service.fit_verdict,
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


# --- V5 : observabilité (page Traffic) ----------------------------------


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


def _training_context() -> dict:
    return {
        "datasets": store.list_datasets(),
        "jobs": store.list_train_jobs(),
        # Versions enrichies du serving_status (anti-trompeur).
        "versions": model_registry.list_versions(),
        "runner_configured": bool(config.TRAIN_RUNNER),
        "base_model": config.TRAIN_BASE_MODEL,
    }


@app.get("/partials/training", response_class=HTMLResponse)
async def partials_training(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "partials/training_panel.html", _training_context()
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()

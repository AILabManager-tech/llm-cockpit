"""Runner d'évaluations V6 : joue une suite locale sur N modèles.

Réutilise le routage réel V4 (RoutingService + adapter.chat) — donc le même
chemin que le gateway — et persiste les résultats en SQLite V5. Job in-process
(asyncio). Aucun code généré par un modèle n'est jamais exécuté.
"""

import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app import config
from app.db import store
from app.evals import checks
from app.schemas import ChatMessage, ChatRequest, EvalCaseResult, EvalRunSummary
from app.services.registry import RegistryService
from app.services.routing import RoutingService


class SuiteError(Exception):
    """Suite introuvable ou YAML invalide."""


class EvalValidationError(Exception):
    """Suite mal formée, check inconnu, ou aucun modèle fourni."""


def _suite_path(name: str) -> Path:
    return Path(config.EVALS_DIR) / f"{name}.yaml"


def list_suites() -> list[str]:
    directory = Path(config.EVALS_DIR)
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml"))


def load_suite(name: str) -> dict:
    path = _suite_path(name)
    if not path.exists():
        raise SuiteError(f"suite introuvable : {name}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SuiteError(f"suite YAML invalide ({name}) : {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise EvalValidationError(f"suite mal formée : {name}")
    for case in data["cases"]:
        if not isinstance(case, dict) or "prompt" not in case:
            raise EvalValidationError(f"cas invalide dans {name} : {case!r}")
        for spec in case.get("checks", []):
            try:
                checks.validate_spec(spec)
            except checks.CheckError as exc:
                raise EvalValidationError(str(exc)) from exc
    return data


class EvalRunner:
    def __init__(self, registry: RegistryService, routing: RoutingService) -> None:
        self.registry = registry
        self.routing = routing

    async def run(self, suite_name: str, models: list[str]) -> EvalRunSummary:
        suite = load_suite(suite_name)               # SuiteError/ValidationError
        if not models:
            raise EvalValidationError("aucun modèle fourni")
        role = suite.get("role")
        cases = suite["cases"]

        results: list[EvalCaseResult] = []
        for case in cases:
            for model in models:
                results.append(await self._run_case(case, model))

        ts = datetime.now(timezone.utc).isoformat()
        run_id = store.insert_eval_run(
            ts=ts, suite=suite_name, role=role, models=models,
            status="completed", total_cases=len(cases),
        )
        for r in results:
            store.insert_eval_result(run_id, suite_name, role, r.model_dump())

        return EvalRunSummary(
            id=run_id, ts=ts, suite=suite_name, role=role, models=models,
            status="completed", total_cases=len(cases), results=results,
        )

    async def _run_case(self, case: dict, model: str) -> EvalCaseResult:
        name = case.get("name", "case")
        prompt = case["prompt"]
        specs = case.get("checks", [])

        decision = await self.routing.resolve(model)
        if not decision.ok:
            return EvalCaseResult(
                case=name, model=model, status="error", latency_ms=None,
                passed=0, total=len(specs), score=0.0, checks=[],
                error=decision.reason,
            )

        adapter = self.registry.adapter_for(decision.provider)
        if adapter is None:
            return EvalCaseResult(
                case=name, model=decision.model or model, status="error",
                latency_ms=None, passed=0, total=len(specs), score=0.0,
                checks=[], error=f"provider indisponible : {decision.provider}",
            )

        started = time.perf_counter()
        result = await adapter.chat(
            ChatRequest(
                model=decision.model,
                messages=[ChatMessage(role="user", content=prompt)],
            )
        )
        latency_ms = (time.perf_counter() - started) * 1000.0

        if result.error:
            return EvalCaseResult(
                case=name, model=decision.model or model, status="error",
                latency_ms=latency_ms, passed=0, total=len(specs), score=0.0,
                checks=[], error=result.error,
            )

        response = result.message.content
        check_results = [checks.run_check(s, response, latency_ms) for s in specs]
        passed = sum(1 for c in check_results if c.passed)
        total = len(check_results)
        score = (passed / total) if total else 0.0
        preview = (response or "")[: config.EVAL_RESPONSE_PREVIEW_MAX]

        return EvalCaseResult(
            case=name, model=decision.model or model, status="ok",
            latency_ms=latency_ms, passed=passed, total=total, score=score,
            checks=check_results, response_preview=preview,
        )

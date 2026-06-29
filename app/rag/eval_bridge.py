"""Branche le RAG dans le harness d'évaluation V6 (réutilisé tel quel).

Mesure RAG vs non-RAG : on joue la MÊME suite, soit telle quelle (non-RAG),
soit avec chaque prompt augmenté du contexte récupéré (RAG). Aucune nouvelle
infra d'éval : on réutilise `EvalRunner.run_loaded`. Comparer = lancer les deux.
"""

from app import config
from app.evals.runner import EvalRunner, load_suite
from app.rag import query as rag_query
from app.schemas import EvalRunSummary


async def run_eval(
    runner: EvalRunner, suite_name: str, with_rag: bool, models: list[str]
) -> EvalRunSummary:
    suite = load_suite(suite_name)               # SuiteError/ValidationError

    if not with_rag:
        return await runner.run_loaded(suite, suite_name, models)

    # Mode RAG : augmente chaque prompt avec le contexte récupéré localement.
    augmented_cases = []
    for case in suite["cases"]:
        scored = await rag_query._retrieve_scored(case["prompt"], config.RAG_TOP_K)
        context = rag_query.build_context(scored)
        new_case = dict(case)
        new_case["prompt"] = rag_query.build_rag_prompt(case["prompt"], context)
        augmented_cases.append(new_case)

    base_role = suite.get("role") or "default"
    rag_suite = {**suite, "cases": augmented_cases, "role": f"{base_role}+rag"}
    # Suffixe "+rag" → distinct dans /api/evals et le scoreboard (par rôle).
    return await runner.run_loaded(rag_suite, f"{suite_name}+rag", models)

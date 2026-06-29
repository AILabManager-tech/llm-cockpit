"""Scoreboard V6 : agrège les résultats d'eval par (rôle, modèle).

Lit les lignes via le store (seul point d'accès DB) et agrège en Python.
Trié par rôle puis par taux de réussite décroissant : « quel modèle est
meilleur pour quel usage », avec le nombre de preuves derrière.
"""

from app.db import store
from app.schemas import ScoreboardRow


def compute_scoreboard(role: str | None = None) -> list[ScoreboardRow]:
    rows = store.fetch_eval_results(role=role)

    agg: dict[tuple, dict] = {}
    for r in rows:
        key = (r.get("role"), r["model"])
        a = agg.setdefault(
            key,
            {
                "runs": set(), "cases": 0, "passed": 0, "total": 0,
                "latency_sum": 0.0, "latency_n": 0, "errors": 0,
            },
        )
        a["runs"].add(r["run_id"])
        a["cases"] += 1
        a["passed"] += r["passed"]
        a["total"] += r["total"]
        if r["status"] != "ok":
            a["errors"] += 1
        if r.get("latency_ms") is not None:
            a["latency_sum"] += r["latency_ms"]
            a["latency_n"] += 1

    out: list[ScoreboardRow] = []
    for (role_key, model), a in agg.items():
        pass_rate = (a["passed"] / a["total"]) if a["total"] else 0.0
        avg_latency = (
            a["latency_sum"] / a["latency_n"] if a["latency_n"] else None
        )
        out.append(
            ScoreboardRow(
                role=role_key, model=model, runs=len(a["runs"]),
                cases=a["cases"], checks_passed=a["passed"],
                checks_total=a["total"], pass_rate=pass_rate,
                avg_latency_ms=avg_latency, errors=a["errors"],
            )
        )

    out.sort(key=lambda r: (r.role or "", -r.pass_rate))
    return out

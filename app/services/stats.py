"""Agrégations sur les logs gateway (volume, taux d'erreur, percentiles).

Local-first : tout est calculé en Python à partir des lignes SQLite. Fenêtre
vide → zéros francs, percentiles None, jamais d'erreur.
"""

import math
from collections import Counter
from datetime import datetime, timedelta, timezone

from app.db import store
from app.schemas import StatsBucket, StatsSummary


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    """Nearest-rank. `sorted_values` doit être trié croissant."""
    if not sorted_values:
        return None
    rank = math.ceil(pct / 100.0 * len(sorted_values))
    idx = min(max(rank - 1, 0), len(sorted_values) - 1)
    return sorted_values[idx]


def _buckets(rows: list[dict], field: str) -> list[StatsBucket]:
    totals: Counter = Counter()
    errors: Counter = Counter()
    for row in rows:
        key = row.get(field) or "—"
        totals[key] += 1
        if row.get("status") != "ok":
            errors[key] += 1
    return [
        StatsBucket(key=key, count=count, error_count=errors.get(key, 0))
        for key, count in totals.most_common()
    ]


def compute_stats(window_seconds: int | None = None) -> StatsSummary:
    cutoff_iso = None
    if window_seconds:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        cutoff_iso = cutoff.isoformat()

    rows = store.fetch_for_stats(cutoff_iso)
    total = len(rows)
    errors = sum(1 for r in rows if r.get("status") != "ok")
    error_rate = (errors / total) if total else 0.0

    latencies = sorted(
        r["latency_ms"] for r in rows if r.get("latency_ms") is not None
    )

    return StatsSummary(
        window_seconds=window_seconds,
        total=total,
        errors=errors,
        error_rate=error_rate,
        latency_p50_ms=_percentile(latencies, 50),
        latency_p95_ms=_percentile(latencies, 95),
        by_model=_buckets(rows, "model"),
        by_provider=_buckets(rows, "provider"),
        by_app=_buckets(rows, "app"),
    )

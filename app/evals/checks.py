"""Checks déterministes et inspectables pour les évaluations V6.

Un check est une chaîne : `nom` ou `nom:argument` (ex. `json_valid`,
`contains:ok`, `latency_lt:2000`). Tous les checks sont déterministes — aucun
juge LLM, aucun appel réseau, aucune exécution du code généré par un modèle.
"""

import json
import re

from app.schemas import EvalCheckResult


class CheckError(Exception):
    """Spec de check invalide (nom inconnu ou argument manquant/illégal)."""


def _non_empty(arg, response, latency_ms):
    ok = bool(response and response.strip())
    return ok, "non-empty" if ok else "empty response"


def _json_valid(arg, response, latency_ms):
    try:
        json.loads(response)
        return True, "valid JSON"
    except (ValueError, TypeError):
        return False, "invalid JSON"


def _contains(arg, response, latency_ms):
    ok = arg in (response or "")
    return ok, (f"contains '{arg}'" if ok else f"does not contain '{arg}'")


def _regex(arg, response, latency_ms):
    ok = re.search(arg, response or "") is not None
    return ok, (f"match /{arg}/" if ok else f"no match /{arg}/")


def _equals(arg, response, latency_ms):
    ok = (response or "").strip() == arg.strip()
    return ok, "equal" if ok else "different"


def _min_length(arg, response, latency_ms):
    n = len(response or "")
    ok = n >= int(arg)
    return ok, f"length {n} (min {arg})"


def _max_length(arg, response, latency_ms):
    n = len(response or "")
    ok = n <= int(arg)
    return ok, f"length {n} (max {arg})"


def _latency_lt(arg, response, latency_ms):
    threshold = float(arg)
    if latency_ms is None:
        return False, "unknown latency"
    ok = latency_ms < threshold
    return ok, f"{latency_ms:.0f}ms {'<' if ok else '>='} {threshold:.0f}ms"


# nom → (fonction, requiert un argument, argument numérique)
_REGISTRY = {
    "non_empty": (_non_empty, False, False),
    "json_valid": (_json_valid, False, False),
    "contains": (_contains, True, False),
    "regex": (_regex, True, False),
    "equals": (_equals, True, False),
    "min_length": (_min_length, True, True),
    "max_length": (_max_length, True, True),
    "latency_lt": (_latency_lt, True, True),
}


def parse_spec(spec: str) -> tuple[str, str | None]:
    if ":" in spec:
        name, arg = spec.split(":", 1)
        return name.strip(), arg
    return spec.strip(), None


def validate_spec(spec: str) -> None:
    """Lève CheckError si le check est inconnu ou mal formé. Pas d'exécution."""
    name, arg = parse_spec(spec)
    if name not in _REGISTRY:
        raise CheckError(f"unknown check: {name}")
    _fn, needs_arg, numeric = _REGISTRY[name]
    if needs_arg and (arg is None or arg == ""):
        raise CheckError(f"check '{name}' requires an argument")
    if numeric and arg is not None:
        try:
            float(arg)
        except ValueError as exc:
            raise CheckError(
                f"check '{name}' requires a numeric argument: {arg!r}"
            ) from exc


def run_check(
    spec: str, response: str | None, latency_ms: float | None
) -> EvalCheckResult:
    validate_spec(spec)
    name, arg = parse_spec(spec)
    fn, _needs, _num = _REGISTRY[name]
    passed, detail = fn(arg, response, latency_ms)
    return EvalCheckResult(check=spec, passed=bool(passed), detail=detail)

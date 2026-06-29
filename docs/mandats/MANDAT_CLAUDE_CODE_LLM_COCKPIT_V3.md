# MANDAT CLAUDE CODE — LLM COCKPIT V3

```text
STATUT : DRAFT — NE PAS EXÉCUTER SANS VALIDATION HUMAINE.
Ce mandat dépend de l'état réel produit par la phase précédente.
```

> DRAFT structuré, **non verrouillé**. Détails « à figer » dépendants de l'état réel de V2.
> Précondition : V2 terminée, taguée `v2`, `ruff` + `pytest` verts.

---

## MISSION

Préparer l'arrivée de **plusieurs moteurs d'exécution** sans casser le cœur : centraliser les providers, brancher un nouveau provider via **adapter**, détecter le **drift** entre le registry déclaré et la réalité observée, garder un inventaire cohérent multi-provider. Ollama reste le provider principal au départ.

---

## MÉTHODE D'EXÉCUTION (terminal)

1. `git checkout -b v3` depuis `v2`. Baseline verte.
2. Étendre `app/providers/base.py` (capabilities) → `app/providers/openai_compat.py` (nouvel adapter) → `app/services/registry.py` → `app/main.py` → templates. Tests en parallèle.
3. ruff + pytest (tout reste vert). README. `git tag v3`.

---

## PÉRIMÈTRE

Racine `llm-cockpit-v0`. Branche `v3`. Inspecter avant de modifier. Jamais de dossier voisin.

---

## CONTEXTE GLOBAL GELÉ

| Phase | Rôle |
|---|---|
| V0 | inventaire | V1 | contrôle | V2 | rôles |
| **V3** | registry multi-provider ← **TU ES ICI** |
| V4 | gateway | V5 | logs | V6 | evals | V7 | RAG | V8 | LoRA |

---

## ACQUIS V2 — NE PAS RÉÉCRIRE

Inventaire, contrôle, rôles. `ProviderAdapter` abstrait (V0+V1 : healthcheck/list_installed/list_loaded/load/unload/generate). `OllamaAdapter` est aujourd'hui le seul adapter et le seul à parler à un moteur. V3 généralise sans casser ce contrat.

---

## INTERDICTIONS ABSOLUES POUR V3

- Pas de gateway exposé aux applications (V4) : V3 centralise l'inventaire et le registry, il n'expose pas encore `/v1/chat/completions`.
- Pas de SQLite (registry en **JSON local**).
- Ne pas inventer un provider non configuré ni un modèle non détecté. Provider injoignable → état clair, pas de faux positif.
- Pas de système de plugins générique : un adapter = une classe concrète implémentant `ProviderAdapter`, pas un framework d'extension dynamique.
- Ne pas préparer V4+.

---

## STACK / DÉPENDANCES

Aucune nouvelle dépendance. L'adapter OpenAI-compatible parle **HTTP brut** via `httpx` (pas le SDK `openai`).

---

## SÉCURITÉ ET INVARIANTS

Bind `127.0.0.1`. Chaque provider a un `base_url` explicite, jamais deviné. Un provider injoignable n'invalide pas les autres. `load`/`unload` non supportés hors Ollama → `ActionResult(status="unsupported")`, jamais d'exception. Tout appel HTTP à un provider reste dans son module adapter dédié.

---

## RÉFÉRENCE API (providers OpenAI-compatible)

```
GET  /v1/models            → { "data": [ { "id": "..." }, ... ] }
POST /v1/chat/completions  → complétion (utilisé surtout en V4 ; en V3 pour healthcheck/generate)
```

Cibles : LM Studio, llama.cpp server, tout endpoint OpenAI-compatible. `list_loaded` peut être non disponible chez certains → `capabilities` le déclare.

---

## FONCTIONNALITÉ V3 ATTENDUE

1. Registry centralisé de providers (id, kind, base_url, enabled).
2. Ajouter / désactiver un provider.
3. Inventaire **agrégé multi-provider** (chaque `ModelInfo` connaît son `provider`).
4. Détection de drift : ce que le registry déclare vs ce que le provider expose réellement.
5. UI : panneau « Providers » avec statut de chaque provider et drift visible.

---

## DIRECTION D'ARCHITECTURE (esquisse indicative, à figer)

- `app/providers/base.py` gagne `capabilities() -> ProviderCapabilities` (sync, déclaratif).
- `app/providers/openai_compat.py` implémente le contrat via `/v1/*`. `load`/`unload` → `unsupported`.
- `app/services/registry.py` charge `data/providers.json`, instancie les adapters, agrège l'inventaire, calcule le drift.
- L'inventaire V0 devient une **agrégation** sur tous les providers actifs, sans casser la forme `list[ModelInfo]`. `ModelInfo.provider` déjà présent depuis V0 → on l'exploite enfin.
- Schémas indicatifs : `ProviderConfig`, `ProviderCapabilities`, `RegistryDrift`. **Champs exacts à confirmer** contre les schémas réels V0–V2.

---

## ENDPOINTS (proposés)

```
GET    /api/providers           → providers déclarés + statut
POST   /api/providers           → enregistrer un provider
DELETE /api/providers/{id}      → retirer/désactiver
GET    /api/registry/drift      → drift registry ↔ réalité
GET    /partials/providers      → fragment HTMX
```

`/api/models` (V0) renvoie désormais l'inventaire **agrégé**. Forme inchangée.

---

## STRUCTURE DE FICHIERS (delta proposé)

Nouveaux : `app/providers/openai_compat.py`, `app/services/registry.py`, `app/templates/partials/providers_panel.html`, `tests/test_registry.py`, `tests/test_openai_compat_adapter.py`. Étendus : `base.py`, `inventory.py` (agrégation), `config.py`, `schemas.py`, `main.py`. Pas de dossier de phase future.

---

## CONFIGURATION (proposé)

```
PROVIDERS_CONFIG_PATH = env("PROVIDERS_CONFIG_PATH", DATA_DIR + "/providers.json")
```

Au démarrage : si `providers.json` absent → un seul provider Ollama par défaut (depuis `OLLAMA_BASE_URL`), jamais d'invention d'un second provider.

---

## CAS LIMITES

Provider injoignable → marqué unreachable, exclu de l'agrégat sans casser les autres. Drift (modèle déclaré absent / présent inattendu) → exposé, jamais masqué. Provider dupliqué (même base_url) → refus ou dédup clair. `providers.json` corrompu → erreur claire.

---

## TESTS ATTENDUS (direction)

Parsing réel de `/v1/models` (transport mocké) dans `openai_compat` ; agrégation multi-provider ; drift calculé correctement ; provider injoignable isolé ; `load` hors Ollama → `unsupported` ; V0–V2 verts ; ruff + pytest verts.

---

## DEFINITION OF DONE

ruff + pytest verts ; ≥ 2 kinds d'adapter (`ollama`, `openai_compat`) ; inventaire agrégé cohérent ; drift détecté ; aucun gateway exposé ; aucune SQLite ; aucun fichier de phase future ; `git tag v3`.

---

## README ATTENDU (bloc invariants)

```text
V3 centralise plusieurs providers mais n'expose pas encore de gateway.
V3 n'invente jamais un provider ou un modèle non détecté.
V3 ne supporte load/unload que là où le provider le permet (Ollama).
V3 n'introduit aucune base de données (registry en JSON local).
```

---

## POINTS À FIGER AU MANDAT D'EXÉCUTION (dépend de V2)

- Comment les rôles V2 s'étendent au multi-provider : un rôle pointe-t-il vers `(provider, model)` ou seulement `model` ? (probablement le couple — à confirmer contre `RoleAssignment` réel).
- Faut-il migrer `roles.json` pour inclure le provider.
- Granularité réelle de `capabilities` selon les providers effectivement branchés.

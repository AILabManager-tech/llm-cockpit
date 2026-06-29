# MANDAT CLAUDE CODE — LLM COCKPIT V4

```text
STATUT : DRAFT — NE PAS EXÉCUTER SANS VALIDATION HUMAINE.
Ce mandat dépend de l'état réel produit par la phase précédente.
```

> DRAFT structuré, **non verrouillé**. Détails « à figer » dépendants de l'état réel de V3.
> Précondition : V3 terminée, taguée `v3`, `ruff` + `pytest` verts.

---

## MISSION

Faire passer les applications par un **point d'entrée unique** : exposer un endpoint local **compatible OpenAI minimal**, router une requête vers le bon modèle selon le **rôle**, masquer la complexité provider/modèle aux applications. Les apps ne parlent plus à Ollama : elles parlent au cockpit.

---

## MÉTHODE D'EXÉCUTION (terminal)

1. `git checkout -b v4` depuis `v3`. Baseline verte.
2. `app/providers/base.py` (méthode `chat`) → adapters (`chat` Ollama/openai_compat) → `app/services/routing.py` → `app/gateway/openai.py` (routes `/v1/*`) → `app/main.py` (montage) → templates. Tests en parallèle.
3. ruff + pytest verts. README. `git tag v4`.

---

## PÉRIMÈTRE

Racine `llm-cockpit-v0`. Branche `v4`. Inspecter avant de modifier.

---

## CONTEXTE GLOBAL GELÉ

| Phase | Rôle |
|---|---|
| V0 inventaire | V1 contrôle | V2 rôles | V3 registry |
| **V4** | gateway OpenAI-compatible ← **TU ES ICI** |
| V5 logs | V6 evals | V7 RAG | V8 LoRA |

---

## ACQUIS V3 — NE PAS RÉÉCRIRE

Inventaire agrégé multi-provider, registry (`data/providers.json`), rôles (`data/roles.json`), adapters `ollama` + `openai_compat`, `ProviderAdapter` (avec `generate`, `capabilities`). V4 ajoute `chat` au contrat et un **routeur** qui résout rôle → (provider, modèle) → adapter.

---

## INTERDICTIONS ABSOLUES POUR V4

- Pas d'observabilité riche / dashboard (V5) : V4 route, il ne mesure pas encore (un log minimal suffit, la vraie observabilité = V5).
- Pas de RAG, pas d'evals, pas de training.
- Subset OpenAI **minimal** : `/v1/chat/completions` (+ `/v1/models`). Pas d'embeddings exposés, pas de fonctions/outils, pas de vision, sauf nécessité prouvée (alors documenter et limiter).
- Streaming : hors scope par défaut (`stream:false`) sauf décision explicite au mandat d'exécution.
- Bind toujours `127.0.0.1` : le gateway reste **local**, jamais exposé au réseau par défaut.
- Ne pas préparer V5+.

---

## STACK / DÉPENDANCES

Aucune nouvelle dépendance.

---

## SÉCURITÉ ET INVARIANTS

Gateway local uniquement (`127.0.0.1`), pas de CORS wildcard. Un rôle non assigné / un modèle injoignable → erreur OpenAI-compatible claire (objet `error`), jamais de stacktrace. Le routage ne contourne jamais la validation : il ne route que vers des modèles réellement présents chez un provider joignable.

---

## RÉFÉRENCE API

- Exposé par le cockpit : `POST /v1/chat/completions`, `GET /v1/models` (subset OpenAI).
- En interne : route vers `adapter.chat()`, traduit vers Ollama (`/api/chat` ou `/v1/chat/completions` natif) ou openai_compat (`/v1/chat/completions`).

---

## FONCTIONNALITÉ V4 ATTENDUE

1. `POST /v1/chat/completions` : si `model` est un nom de rôle (ex. `role:code` ou `code`), résoudre via la config rôles V2/V3 ; sinon traiter comme modèle réel.
2. Réponse au format OpenAI minimal (`choices[].message`, `usage` si disponible).
3. `GET /v1/models` : liste exposée (modèles réels + alias de rôles).
4. Table de routage consultable (`/api/routes`) : ce qu'une requête résoudrait.
5. UI : panneau « Gateway » montrant la résolution rôle → provider/modèle.

Exemple : une app appelle `/v1/chat/completions` avec `model:"code"` → le cockpit choisit le modèle assigné au rôle `code` chez le provider correspondant → le provider réel reste derrière.

---

## DIRECTION D'ARCHITECTURE (esquisse indicative, à figer)

- `app/services/routing.py` : `resolve(model_or_role) -> RouteDecision{requested, resolved_role, provider, model, reason}`. Réutilise rôles (V2) + registry (V3).
- `app/gateway/openai.py` : routes `/v1/*`, mappe `ChatRequest` (subset) → `adapter.chat` → `ChatResult`.
- `ProviderAdapter.chat(req) -> ChatResult` ajouté en V4, implémenté par les deux adapters.
- Schémas indicatifs : `ChatMessage`, `ChatRequest`, `ChatResult`, `RouteDecision`. **Champs exacts à confirmer** contre la forme réelle des rôles/registry V2–V3.

---

## ENDPOINTS (proposés)

```
POST /v1/chat/completions   → complétion (subset OpenAI), routée par rôle ou modèle
GET  /v1/models             → modèles + alias de rôles exposés
GET  /api/routes            → table de routage résolue
GET  /partials/gateway      → fragment HTMX
```

Endpoints V0–V3 inchangés.

---

## STRUCTURE DE FICHIERS (delta proposé)

Nouveaux : `app/gateway/__init__.py`, `app/gateway/openai.py`, `app/services/routing.py`, `app/templates/partials/gateway_panel.html`, `tests/test_gateway.py`, `tests/test_routing.py`. Étendus : `base.py`, adapters, `schemas.py`, `config.py`, `main.py`. **Pas de dossier `gateway/` top-level hors `app/`.**

---

## CONFIGURATION (proposé)

```
GATEWAY_ENABLED      = env_bool("GATEWAY_ENABLED", True)
GATEWAY_DEFAULT_ROLE = env("GATEWAY_DEFAULT_ROLE", "chat")
```

---

## CAS LIMITES

Rôle non assigné → erreur OpenAI claire. Modèle inexistant → erreur. Provider injoignable → erreur, pas de fallback silencieux vers un autre modèle (sauf politique de fallback explicitement décidée). `GATEWAY_ENABLED=0` → `/v1/*` en 404/403.

---

## TESTS ATTENDUS (direction)

Résolution rôle → (provider, modèle) ; appel `/v1/chat/completions` routé correctement (transport mocké) ; format de réponse OpenAI minimal ; rôle non assigné → erreur ; provider down → erreur ; V0–V3 verts ; ruff + pytest verts.

---

## DEFINITION OF DONE

ruff + pytest verts ; une app peut appeler `/v1/chat/completions` et obtenir une réponse routée par rôle ; `/v1/models` cohérent ; gateway local uniquement ; aucune observabilité riche, aucun RAG/eval ; aucun fichier de phase future ; `git tag v4`.

---

## README ATTENDU (bloc invariants)

```text
V4 expose un gateway OpenAI minimal, local uniquement.
V4 route par rôle ; il ne mesure pas encore (observabilité = V5).
V4 ne fait ni RAG, ni évaluation, ni fine-tuning.
V4 ne s'expose pas au réseau par défaut (127.0.0.1).
```

---

## POINTS À FIGER AU MANDAT D'EXÉCUTION (dépend de V3)

- Forme réelle de `RoleAssignment` (rôle → `model` seul ou `(provider, model)`).
- Politique de fallback si le provider/modèle d'un rôle est down (échec net vs bascule — décision produit).
- Faut-il un streaming SSE minimal selon les apps clientes réelles.
- Traduction exacte vers `/api/chat` Ollama vs `/v1/chat/completions` natif.

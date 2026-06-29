# MANDAT CLAUDE CODE — LLM COCKPIT V1

```text
STATUT : DRAFT — NE PAS EXÉCUTER SANS VALIDATION HUMAINE.
Ce mandat dépend de l'état réel produit par la phase précédente.
```

> Document d'exécution. Lis-le en entier avant d'écrire une ligne.
> Tu implémentes **V1 uniquement**. La vision complète est fournie comme contexte gelé, pas comme permission.
> Précondition : V0 est terminée, taguée `v0`, `ruff` et `pytest` verts. Si ce n'est pas le cas, **arrête-toi** et signale-le.

---

## MISSION

Ajouter à LLM Cockpit un **contrôle sécurisé minimal** : depuis le cockpit, tu peux **tester** un modèle avec un prompt court, **charger** (warmup/load) un modèle, et le **décharger** (unload) — rien d'autre. Chaque action est journalisée. Toute action hors allowlist est refusée.

V0 reste intact : l'inventaire lecture seule continue de fonctionner exactement comme avant. V1 est une **couche additive** sur le même dépôt.

---

## MÉTHODE D'EXÉCUTION (terminal)

Procède dans cet ordre strict. Ne saute pas d'étape.

1. `git checkout -b v1` depuis `v0`. Vérifie `uv run pytest` vert AVANT de toucher quoi que ce soit (baseline).
2. Étends, dans cet ordre : `app/config.py` (vars actions) → `app/schemas.py` (nouveaux schémas) → `app/providers/base.py` (méthodes abstraites) → `app/providers/ollama.py` (implémentation native) → `app/services/action_log.py` → `app/services/actions.py` → `app/main.py` (nouvelles routes) → templates (panneau actions) → `app/static/app.css` (si besoin).
3. Écris les tests **en parallèle** de chaque module, pas à la fin.
4. `uv run ruff check .` puis `uv run pytest`. Corrige jusqu'au vert. Les tests V0 doivent **rester verts**.
5. Mets à jour `README.md` (section V1).
6. `git tag v1` seulement à l'atteinte du DoD. Produis le rapport final imposé.

Ne « prépare » pas V2+. Pas de rôles, pas de registry, pas de gateway. Pas de dossiers vides.

---

## PÉRIMÈTRE DE TRAVAIL (filesystem)

- **Racine unique** : `/home/gear-code/02_projects/llm-cockpit/llm-cockpit-v0` (le dépôt V0 réel ; le nom du dossier est historique, on ne le renomme pas).
- Tout le code vit directement sous cette racine. **Inspecter avant de modifier.** Ne rien écraser à l'aveugle.
- **Ne jamais écrire hors de ce périmètre.** Aucun fichier ailleurs, aucune config globale.
- Versionnement par git : branche `v1`, `git tag v1` au DoD. Jamais de dossier voisin `llm-cockpit-v1`.

---

## CONTEXTE GLOBAL GELÉ (lecture seule — n'exécute pas)

| Phase | Rôle |
|---|---|
| V0 | inventaire lecture seule |
| **V1** | contrôle sécurisé minimal (test / load / unload) ← **TU ES ICI** |
| V2 | rôles et sélection de modèles |
| V3 | registry multi-provider |
| V4 | gateway OpenAI-compatible (subset minimal) |
| V5 | logs structurés et observabilité |
| V6 | évaluations comparatives |
| V7 | RAG local mesuré |
| V8 | adaptation LoRA/QLoRA orchestrée, comparée au baseline |

Tu livres **V1 seulement**. Le reste sert à comprendre pourquoi l'architecture V1 doit rester propre et extensible.

---

## ACQUIS V0 — NE PAS RÉÉCRIRE

Existent déjà et doivent rester fonctionnels :

- `ModelInfo`, `ProviderHealth` dans `app/schemas.py`.
- `ProviderAdapter` (abstrait) : `healthcheck`, `list_installed`, `list_loaded`.
- `OllamaAdapter` (`app/providers/ollama.py`) : seul fichier autorisé à parler à Ollama, appelle `/api/tags` et `/api/ps`.
- `app/services/inventory.py` : fusion + normalisation des noms (clé = nom normalisé, digest = validation secondaire).
- Endpoints V0 : `GET /api/health`, `/api/models`, `/api/models/installed`, `/api/models/loaded`, `GET /`, `GET /partials/models`.
- Config : `OLLAMA_BASE_URL`, `HOST`, `PORT`.

Tu **étends** ces fichiers. Tu ne réécris ni la fusion, ni la normalisation, ni les schémas existants.

---

## INTERDICTIONS ABSOLUES POUR V1

Tu ne dois pas :

- implémenter `pull` / `delete` de modèles ;
- implémenter start / stop / restart de services système ; appeler `systemctl` ;
- implémenter un gateway, du routing, des rôles, un registry, du RAG, du fine-tuning ;
- créer un système d'agents, des microservices, une queue, un système de plugins générique ;
- créer une infrastructure de jobs background (même « pour plus tard ») ;
- introduire SQLite ou une base de données (le journal V1 est un **JSONL append-only**, point) ;
- exécuter une commande système libre ; utiliser `shell=True` ;
- élargir l'allowlist d'actions au-delà de `{load, unload, test}` ;
- hardcoder les modèles présents ; inventer un provider ou un modèle.

**Toute action hors allowlist → refus explicite (HTTP 400/403), jamais d'exécution silencieuse.**

---

## STACK / DÉPENDANCES

Inchangée vs V0. **Aucune nouvelle dépendance.** `httpx` suffit pour appeler `/api/generate`. Le journal utilise `json` + écriture fichier stdlib.

---

## SÉCURITÉ ET INVARIANTS

L'application doit :

- continuer à binder `127.0.0.1` par défaut (jamais `0.0.0.0`) ; pas de CORS wildcard ;
- n'exécuter **que** les actions de l'allowlist `{load, unload, test}`, et uniquement contre Ollama ;
- ne jamais utiliser `shell=True`, ne jamais appeler `systemctl`, ne jamais exécuter de commande système ;
- valider le nom de modèle reçu : il doit correspondre à un modèle **réellement présent** dans l'inventaire (`/api/tags`) avant un `load`/`test`, ou réellement chargé (`/api/ps`) avant un `unload` ; sinon → erreur claire, pas d'appel ;
- retourner une erreur contrôlée si Ollama est injoignable (jamais de stacktrace brute) ;
- journaliser chaque tentative d'action (réussie ou refusée) avant de répondre ;
- rester strictement non destructive : `load`/`unload`/`test` ne suppriment ni ne modifient aucun modèle sur disque.

Tout appel HTTP à Ollama reste **exclusivement** dans `app/providers/ollama.py`.

---

## RÉFÉRENCE API OLLAMA (VÉRIFIÉE — shapes exacts, API native)

V1 utilise l'API **native** Ollama, PAS l'OpenAI-compatible.

```
POST /api/generate   → charge / décharge / génère selon le body
```

### Charger un modèle (warmup/load)

```json
// requête
{ "model": "llama3.2:latest", "keep_alive": "5m" }
// (aucun "prompt") → Ollama charge le modèle en mémoire
```

### Décharger un modèle (unload)

```json
// requête
{ "model": "llama3.2:latest", "keep_alive": 0 }
// → Ollama décharge le modèle de la mémoire
```

### Tester un modèle (prompt court, non-stream)

```json
// requête
{ "model": "llama3.2:latest", "prompt": "Réponds OK.", "stream": false }
// réponse (extrait)
{
  "model": "llama3.2:latest",
  "response": "OK",
  "done": true,
  "total_duration": 1234567890,   // nanosecondes → convertir en ms
  "eval_count": 3
}
```

**Faits à connaître :**

- Les `*_duration` sont en **nanosecondes**. Convertir en ms (`/ 1_000_000`) pour les schémas.
- `stream: false` est obligatoire en V1 (pas de streaming SSE en V1, ça reste simple).
- Un `load` réussi ne renvoie pas de `response` utile ; vérifier `done`/HTTP 200, puis confirmer via `/api/ps` si besoin côté UI.

---

## FONCTIONNALITÉ V1 ATTENDUE

1. **Tester** un modèle : bouton/onglet « Tester », champ prompt court (défaut fourni), bouton → `POST /api/actions/test`. Affiche la réponse, la latence, le statut.
2. **Charger** un modèle : action `load` depuis la ligne d'un modèle installé non chargé.
3. **Décharger** un modèle : action `unload` depuis la ligne d'un modèle chargé.
4. **Journal d'actions** : chaque action est ajoutée à `data/actions.jsonl` (append-only) et consultable via `GET /api/actions/log` + un fragment `/partials/actions`.
5. **Refus hors allowlist** : toute action non listée → 400/403, journalisée comme `status="refused"`, jamais exécutée.
6. **UI** : les actions s'intègrent au tableau d'inventaire existant (boutons contrôlés, pas de bouton destructif). Le statut « loaded » de V0 se met à jour après une action (refresh HTMX).

---

## LOGIQUE / ALGORITHME IMPOSÉ (cœur anti-bug)

### Validation d'action (avant tout appel Ollama)

```text
fonction valider_action(action, model):
    si action not in ACTION_ALLOWLIST:        # {"load","unload","test"}
        journaliser(action, model, status="refused", detail="hors allowlist")
        -> 400, erreur claire, AUCUN appel Ollama

    inventaire = inventory.list_models()       # réutilise la fusion V0
    si action in {"load","test"}:
        si model not in noms_installés(inventaire):
            journaliser(..., status="refused", detail="modèle non installé")
            -> 400
    si action == "unload":
        si model not in noms_chargés(inventaire):
            journaliser(..., status="refused", detail="modèle non chargé")
            -> 400
    -> OK, on peut appeler l'adapter
```

- Comparaison sur le **nom normalisé** (réutiliser la normalisation V0). Jamais sur le digest.
- La validation se fait **dans `app/services/actions.py`**, pas dans l'adapter. L'adapter exécute, le service décide.

### Journalisation (append-only JSONL)

```text
chaque action (réussie, en erreur, ou refusée) ->
  append une ligne JSON à data/actions.jsonl :
  { "ts": ISO8601, "action", "model", "provider":"ollama", "status", "detail" }
status ∈ {"ok","error","refused","unsupported"}
```

- Écriture append (`open(..., "a")`), une ligne JSON par action, jamais de réécriture du fichier.
- `data/` créé si absent. `data/` est **gitignored** (ajouter au `.gitignore`).
- Pas de SQLite. Pas de rotation complexe. Un fichier JSONL, point. (La vraie observabilité, c'est V5.)

---

## CONTRATS TECHNIQUES FIGÉS

`app/providers/base.py` — méthodes **ajoutées** (l'existant reste) :

```python
async def load(self, model: str, keep_alive: str = "5m") -> ActionResult: ...
async def unload(self, model: str) -> ActionResult: ...
async def generate(self, req: GenerateRequest) -> GenerateResult: ...
```

`app/providers/ollama.py` implémente ces trois méthodes via `POST /api/generate` (shapes ci-dessus). **Seul fichier autorisé à parler à Ollama.** Conversion ns→ms ici.

`app/services/actions.py` : orchestre validation → appel adapter → journalisation. Ne parle jamais à Ollama directement.
`app/services/action_log.py` : append + lecture du JSONL.

---

## MODÈLES DE DONNÉES (`app/schemas.py` — ajouts)

```python
class GenerateRequest(BaseModel):
    model: str
    prompt: str
    options: dict[str, Any] | None = None

class GenerateResult(BaseModel):
    model: str
    response: str
    done: bool
    total_duration_ms: float | None = None
    eval_count: int | None = None
    error: str | None = None

class ActionResult(BaseModel):
    action: str            # "load" | "unload" | "test"
    model: str
    provider: str = "ollama"
    status: str            # "ok" | "error" | "unsupported"
    detail: str | None = None
    duration_ms: float | None = None

class ActionLogEntry(BaseModel):
    ts: str
    action: str
    model: str
    provider: str = "ollama"
    status: str            # "ok" | "error" | "refused" | "unsupported"
    detail: str | None = None
```

Les schémas V0 (`ModelInfo`, `ProviderHealth`) restent **inchangés**.

---

## ENDPOINTS (ajouts)

**JSON :**

```
POST /api/actions/load     body {model}            → ActionResult
POST /api/actions/unload   body {model}            → ActionResult
POST /api/actions/test     body {model, prompt?}   → ActionResult (+ réponse dans detail) ou GenerateResult
GET  /api/actions/log      ?limit=N                → list[ActionLogEntry] (les N dernières)
```

**HTML (HTMX) :**

```
GET /partials/actions  → fragment du journal d'actions (dernières lignes)
```

Les endpoints V0 restent inchangés. N'ajoute **aucun** autre endpoint.

---

## STRUCTURE DE FICHIERS (delta V1)

Fichiers **nouveaux** :

```text
app/services/action_log.py
app/services/actions.py
app/templates/partials/actions_panel.html
tests/test_actions.py
tests/test_action_log.py
```

Fichiers **étendus** (pas réécrits) : `app/config.py`, `app/schemas.py`, `app/providers/base.py`, `app/providers/ollama.py`, `app/main.py`, `app/templates/inventory.html`, `.gitignore` (ajout `data/`).

**Ne crée pas** : `actions/` (dossier top-level), `gateway/`, `roles/`, ni aucun dossier de phase future. Le code d'actions vit dans `app/services/`.

---

## CONFIGURATION (`app/config.py` — ajouts)

```python
ACTIONS_ENABLED = os.getenv("ACTIONS_ENABLED", "1") not in {"0", "false", "False"}
ACTION_ALLOWLIST = {"load", "unload", "test"}      # figé
ACTION_TIMEOUT_S = float(os.getenv("ACTION_TIMEOUT_S", "60"))
DATA_DIR = os.getenv("DATA_DIR", "data")
ACTION_LOG_PATH = os.path.join(DATA_DIR, "actions.jsonl")
```

Si `ACTIONS_ENABLED` est faux → les endpoints d'action renvoient 403 « actions désactivées », et l'UI masque les boutons. Aucun autre provider.

---

## COMPORTEMENT CAS LIMITES

- **Ollama injoignable** : `/api/actions/*` → `ActionResult(status="error", detail="provider injoignable")`, HTTP 200 avec corps d'erreur clair OU 502 contrôlé (choisir et documenter) ; journalisé ; jamais de stacktrace.
- **Modèle inconnu** : refus 400, journalisé `status="refused"`, aucun appel Ollama.
- **Action hors allowlist** : 400/403, journalisé `status="refused"`.
- **`ACTIONS_ENABLED=0`** : 403, UI sans boutons d'action.
- **`data/` non inscriptible** : erreur claire au démarrage ou à la première écriture, jamais de crash silencieux.
- **Timeout Ollama** (test long) : coupé à `ACTION_TIMEOUT_S`, `status="error", detail="timeout"`.

---

## TESTS OBLIGATOIRES

**Règle de mock (critique) :** on intercepte le **transport HTTP** (respx/pytest-httpx) sur `/api/generate`. On teste le vrai parsing/conversion ns→ms dans `OllamaAdapter`, et la vraie logique de validation/journalisation dans les services. Ne mocke pas les méthodes d'adapter directement.

**Liste minimale :**

1. `load` d'un modèle installé → `ActionResult(status="ok")`, ligne ajoutée au JSONL.
2. `unload` d'un modèle chargé → `status="ok"`, ligne ajoutée.
3. `test` d'un modèle installé → réponse parsée, `total_duration_ms` calculé (ns→ms correct).
4. `load` d'un modèle **non installé** → 400, `status="refused"`, **aucun** appel HTTP à Ollama (vérifier via le mock que la route n'est pas touchée).
5. `unload` d'un modèle **non chargé** → 400, `status="refused"`.
6. Action hors allowlist (ex. `"delete"`) → 400/403, `status="refused"`.
7. Ollama injoignable pendant `test` → `status="error"`, journalisé, pas de stacktrace.
8. `GET /api/actions/log?limit=N` → renvoie les N dernières entrées, ordre chronologique inverse cohérent.
9. `ACTIONS_ENABLED=0` → endpoints d'action en 403.
10. Les tests V0 (`test_health`, `test_inventory`, `test_ollama_adapter`) restent **verts**.
11. `uv run ruff check .` passe.
12. `uv run pytest` passe.

---

## DEFINITION OF DONE

V1 est terminée **uniquement si** :

- `uv run ruff check .` et `uv run pytest` passent (V0 inclus, toujours verts) ;
- l'app démarre, bind `127.0.0.1`, l'inventaire V0 fonctionne toujours ;
- `load`, `unload`, `test` fonctionnent contre un modèle réellement présent, et sont **refusés** sinon ;
- toute action hors `{load, unload, test}` est refusée et journalisée ;
- chaque action est tracée dans `data/actions.jsonl` (append-only, aucune base) ;
- `GET /api/actions/log` et `/partials/actions` exposent le journal ;
- **aucune** introduction de SQLite, de queue, de job background, de rôles/registry/gateway ;
- **aucune** action destructive (`pull`/`delete`/`systemctl`), **aucun** `shell=True` ;
- **aucun** fichier de phase future ; `git tag v1` posé.

---

## README ATTENDU (section V1)

Ajouter au README V0 : objectif V1 ; nouveaux endpoints ; allowlist d'actions ; format du journal `data/actions.jsonl` ; variables `ACTIONS_ENABLED` / `ACTION_TIMEOUT_S` / `DATA_DIR` ; rappel que `data/` est gitignored.

Bloc obligatoire, tel quel :

```text
V1 contrôle uniquement load / unload / test.
V1 ne supprime aucun modèle.
V1 ne fait aucun pull.
V1 ne démarre ni n'arrête aucun service système.
V1 n'introduit aucune base de données (journal JSONL uniquement).
```

---

## COMMANDES FINALES

```bash
uv run ruff check .
uv run pytest
```

Puis rapporte, factuellement : fichiers créés/modifiés (arbre réel) ; endpoints créés ; sortie exacte de `ruff` et `pytest` (pas de paraphrase) ; limites restantes ; TODO réels constatés à l'exécution. Jamais d'invention.

# MANDAT CLAUDE CODE — LLM COCKPIT V0

> Document d'exécution. Lis-le en entier avant d'écrire une ligne.
> Tu implémentes **V0 uniquement**. La vision complète est fournie comme contexte gelé, pas comme permission.

---

## MISSION

Implémenter la **V0** du projet **LLM Cockpit** : un cockpit local-first, **lecture seule**, qui affiche les modèles Ollama **installés** et les modèles **actuellement chargés en mémoire**, avec un état `loaded` fiable par modèle.

Aucune action de contrôle. Aucune phase future. Lecture seule, point.

---

## MÉTHODE D'EXÉCUTION (terminal)

Procède dans cet ordre strict. Ne saute pas d'étape.

1. `git init` (si absent) puis `uv init` du projet + `pyproject.toml` (dépendances de la section Stack).
2. `app/config.py` → `app/schemas.py` → `app/providers/base.py` → `app/providers/ollama.py` → `app/services/inventory.py` → `app/main.py` (routes) → templates → `static/app.css`.
3. Écris les tests **en parallèle** de chaque module, pas à la fin.
4. Lance `uv run ruff check .` puis `uv run pytest`. Corrige jusqu'au vert.
5. Rédige le `README.md`.
6. Produis le rapport final (format imposé plus bas). Ne déclare **rien** « fonctionnel » sans test vert à l'appui.

Ne « prépare » pas les phases futures. Pas de dossiers vides, pas d'abstraction spéculative.

---

## PÉRIMÈTRE DE TRAVAIL (filesystem)

**Racine unique du projet** : `/home/gear-code/02_projects/llm-cockpit`

- Tout le code vit **directement** sous cette racine. Le nœud `llm-cockpit/` de la section Structure **désigne cette racine** : `app/`, `tests/`, `pyproject.toml`, `.gitignore` s'y placent directement. **Ne PAS créer un sous-dossier `llm-cockpit/` à l'intérieur** (pas de double imbrication).
- Si la racine existe déjà : **inspecter avant de modifier**, ne rien écraser à l'aveugle.
- **Ne jamais écrire hors de ce périmètre.** Aucun fichier ailleurs sur le système, aucune modification de config globale.
- **Versionnement par git, pas par dossiers** : à l'atteinte du DoD, `git tag v0`. V1 sera une évolution du **même dépôt** (branche), jamais un dossier `llm-cockpit-v1` voisin. C'est ça, le « cœur qui ne se réécrit jamais ».

---

## CONTEXTE GLOBAL GELÉ (lecture seule — n'exécute pas)

Cible finale du projet : cockpit local-first d'orchestration multi-LLM. Trajectoire :

| Phase | Rôle |
|---|---|
| **V0** | inventaire lecture seule ← **TU ES ICI** |
| V1 | contrôle sécurisé minimal (test / load / unload) |
| V2 | rôles et sélection de modèles |
| V3 | registry multi-provider |
| V4 | gateway OpenAI-compatible (subset minimal) |
| V5 | logs structurés et observabilité |
| V6 | évaluations comparatives |
| V7 | RAG local mesuré |
| V8 | adaptation LoRA/QLoRA orchestrée, comparée au baseline |

Tu livres **V0 seulement**. Le reste sert à comprendre pourquoi l'architecture V0 doit rester propre et extensible.

---

## INTERDICTIONS ABSOLUES POUR V0

Tu ne dois pas :

- implémenter start / stop / restart de services ;
- implémenter load / unload de modèles ;
- implémenter pull / delete de modèles ;
- implémenter un gateway, du routing, du RAG, du fine-tuning, du LoRA/QLoRA ;
- créer un système d'agents, des microservices, une queue, un système de plugins générique ;
- créer une infrastructure de jobs background (même « pour plus tard ») ;
- ajouter des abstractions non utilisées en V0 ;
- exécuter une commande système libre ; utiliser `shell=True` ; appeler `systemctl` ;
- hardcoder les modèles présents sur la machine ;
- inventer un provider ou un modèle si non détecté.

**V0 est lecture seule.** Aucun écrit, aucun effet de bord système.

---

## STACK IMPOSÉE

- Python 3.12
- `uv`
- FastAPI
- Jinja2
- HTMX
- Pydantic v2
- `httpx` (client async pour appeler Ollama)
- `pytest`
- `respx` **ou** `pytest-httpx` (mock du transport HTTP)
- `ruff`

Architecture : **un seul process web**. Aucun job background. Aucun microservice.

---

## SÉCURITÉ ET INVARIANTS

L'application doit :

- binder par défaut sur `127.0.0.1` (jamais `0.0.0.0` en V0) ;
- ne pas exposer de CORS wildcard ;
- ne jamais exécuter de commande libre ni utiliser `shell=True` ;
- ne jamais supposer l'existence d'un modèle ni d'un GPU ;
- ne jamais inventer de données si Ollama est absent ou injoignable ;
- retourner une erreur claire et contrôlée si Ollama est injoignable (jamais de stacktrace brute exposée) ;
- rester locale et strictement non destructive.

Provider ou modèle inconnu / non détecté → **erreur claire ou TODO explicite**, jamais d'invention, jamais de faux positif.

Tout accès à un provider passe par l'interface `ProviderAdapter`. Aucun appel HTTP à Ollama hors de `app/providers/ollama.py`.

---

## RÉFÉRENCE API OLLAMA (VÉRIFIÉE — utilise ces shapes exacts)

Endpoints utilisés en V0 (lecture seule) :

```
GET /api/tags   → modèles installés
GET /api/ps     → modèles chargés en mémoire
```

**N'utilise PAS l'API OpenAI-compatible en V0.**

### Shape réel de `GET /api/tags`

```json
{
  "models": [
    {
      "name": "llama3.2:latest",
      "model": "llama3.2:latest",
      "modified_at": "2025-05-04T17:37:44.706015396-07:00",
      "size": 2019393189,
      "digest": "a80c4f17acd5...",
      "details": {
        "format": "gguf",
        "family": "llama",
        "families": ["llama"],
        "parameter_size": "3.2B",
        "quantization_level": "Q4_K_M"
      }
    }
  ]
}
```

### Shape réel de `GET /api/ps`

```json
{
  "models": [
    {
      "name": "mistral:latest",
      "model": "mistral:latest",
      "size": 5137025024,
      "digest": "2ae6f6dd7a3d...",
      "details": {
        "format": "gguf",
        "family": "llama",
        "families": ["llama"],
        "parameter_size": "7.2B",
        "quantization_level": "Q4_0"
      },
      "expires_at": "2024-06-04T14:38:31.83753-07:00",
      "size_vram": 5137025024
    }
  ]
}
```

**Faits à connaître (déterminent la logique de fusion) :**

- Les deux endpoints renvoient le **nom pleinement qualifié avec tag explicite** (`llama3.2:latest`). Ils sortent du même module de nommage → un même modèle a **le même nom** des deux côtés.
- `/api/ps` **inclut** `digest`, `size_vram` et `expires_at`. `digest` est donc présent des deux côtés.
- `/api/tags` **n'a pas** `size_vram` ni `expires_at` (modèle non chargé).
- `family` et `quantization_level` vivent dans `details`.

---

## FONCTIONNALITÉ V0 ATTENDUE

L'application affiche :

1. **Statut du provider Ollama** : reachable / unreachable, base URL utilisée, message d'erreur clair si injoignable.
2. **Modèles installés** (via `/api/tags`) : nom, taille, digest, date de modification, `family`, `quantization`, détails bruts conservés.
3. **Modèles chargés** (via `/api/ps`) : nom, taille, digest, `size_vram`, `expires_at`, détails bruts conservés.
4. **Fusion installés + chargés** : un seul jeu de modèles, chacun avec un booléen `loaded`. Algorithme imposé ci-dessous.
5. **Interface web** : page `/`, tableau/cartes, statut visuel loaded / not loaded, badge `source=ps_only` si applicable, rafraîchissement HTMX périodique ou bouton refresh, **aucun bouton d'action destructive**.
6. **API JSON** + **fragment HTML** (voir Endpoints).

---

## LOGIQUE DE FUSION (algorithme imposé — c'est le cœur anti-bug)

### Normalisation du nom

```python
def normalize_name(entry: dict) -> str:
    raw = (entry.get("model") or entry.get("name") or "").strip()
    if not raw:
        return ""              # vide → l'appelant décide, ne pas inventer
    if ":" not in raw:
        raw = f"{raw}:latest"  # tag implicite → latest
    return raw
```

### Fusion

```text
installed = adapter.list_installed()   # source="tags", loaded=False
loaded    = adapter.list_loaded()      # source="ps" (provenant de /api/ps)

index = { m.normalized_name: m for m in installed }

pour chaque L dans loaded:
    key = L.normalized_name
    si key dans index:
        index[key].loaded     = True
        index[key].size_vram  = L.size_vram
        index[key].expires_at = L.expires_at
        # validation secondaire (NON bloquante) :
        si index[key].digest et L.digest et index[key].digest != L.digest:
            warning via le module standard `logging` ; garder l'entrée "tags" ; NE PAS masquer
            # PAS de système de logs applicatif, PAS de SQLite en V0 (ça, c'est V5)
    sinon:
        L.loaded     = True
        L.installed  = True
        L.source     = "ps_only"
        index[key]   = L        # chargé mais absent de tags → on l'expose quand même

retourner list(index.values())
```

**Règles dures :**

- Clé de jointure primaire = **nom normalisé**. `digest` sert **seulement** de validation secondaire si présent des deux côtés.
- Convention `source` : `list_installed()` → `"tags"` ; `list_loaded()` → `"ps"` ; après fusion, un modèle présent dans `/api/tags` garde `"tags"` ; un modèle chargé absent de `/api/tags` devient `"ps_only"`.
- Ne **jamais** masquer un modèle chargé sous prétexte que la jointure est imparfaite (cas `ps_only`).
- Ne jamais utiliser `digest` comme clé primaire.
- Incohérence de digest → `logging.warning` standard uniquement. **Aucun** système de logs applicatif, **aucune** SQLite en V0.

---

## CONVENTION `/api/health`

`GET /api/health` retourne **toujours HTTP 200** si l'application FastAPI tourne.

Si Ollama est injoignable :

- HTTP **200** ;
- `reachable: false` ;
- `error` avec un message clair ;
- **jamais** 503 en V0.

Raison : le cockpit est vivant même si le provider est down.

---

## CONTRATS TECHNIQUES FIGÉS

`app/providers/base.py` :

```python
from abc import ABC, abstractmethod
from app.schemas import ModelInfo, ProviderHealth


class ProviderAdapter(ABC):
    @abstractmethod
    async def healthcheck(self) -> ProviderHealth: ...

    @abstractmethod
    async def list_installed(self) -> list[ModelInfo]: ...

    @abstractmethod
    async def list_loaded(self) -> list[ModelInfo]: ...
```

`app/providers/ollama.py` : implémente `ProviderAdapter` en appelant `GET /api/tags` et `GET /api/ps` via `httpx.AsyncClient`. **Seul fichier autorisé à parler à Ollama.**

---

## MODÈLES DE DONNÉES (`app/schemas.py`)

```python
from typing import Any

from pydantic import BaseModel


class ModelInfo(BaseModel):
    name: str
    normalized_name: str
    provider: str = "ollama"
    installed: bool = True
    loaded: bool = False
    source: str = "tags"            # "tags" | "ps" | "ps_only"
    size: int | None = None
    size_vram: int | None = None
    digest: str | None = None
    modified_at: str | None = None
    expires_at: str | None = None
    family: str | None = None
    quantization: str | None = None
    raw: dict[str, Any] | None = None   # payload Ollama brut conservé


class ProviderHealth(BaseModel):
    provider: str
    base_url: str
    reachable: bool
    error: str | None = None
```

---

## ENDPOINTS

**JSON :**

```
GET /api/health             → ProviderHealth (toujours 200)
GET /api/models             → list[ModelInfo] fusionnée
GET /api/models/installed   → list[ModelInfo] (tags)
GET /api/models/loaded      → list[ModelInfo] (ps)
```

**HTML (pour HTMX — obligatoire, sinon le refresh ne marche pas) :**

```
GET /                 → page complète (base.html + inventory.html), rend l'état initial
GET /partials/models  → fragment HTML (partials/models_table.html) pour le polling HTMX ;
                        combine inventaire + health côté serveur ; doit distinguer
                        visuellement « Ollama injoignable » de « aucun modèle installé »
                        (les deux donnent une liste vide, mais ce sont deux états différents)
```

Le tableau utilise `hx-get="/partials/models" hx-trigger="every 5s"` (ou un bouton refresh). HTMX swappe du **HTML**, pas du JSON — d'où l'endpoint fragment dédié. N'ajoute **aucun** autre endpoint.

---

## STRUCTURE DE FICHIERS

```text
llm-cockpit/                       # = la racine du périmètre (cf. PÉRIMÈTRE), PAS un sous-dossier à imbriquer
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ config.py
│  ├─ schemas.py
│  ├─ services/
│  │  ├─ __init__.py
│  │  └─ inventory.py          # porte la fusion + normalisation
│  ├─ providers/
│  │  ├─ __init__.py
│  │  ├─ base.py
│  │  └─ ollama.py
│  ├─ templates/
│  │  ├─ base.html
│  │  ├─ inventory.html
│  │  └─ partials/
│  │     └─ models_table.html
│  └─ static/
│     └─ app.css
├─ tests/
│  ├─ test_health.py
│  ├─ test_inventory.py
│  └─ test_ollama_adapter.py
├─ pyproject.toml
├─ README.md
└─ .gitignore
```

**Ne crée pas** : `rag/`, `evals/`, `gateway/`, `actions/`, `training/`, ni aucun dossier « future » ou vide. Aucun fichier pour V1–V8.

---

## CONFIGURATION (`app/config.py`)

```python
import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
```

Aucun autre provider configuré en V0.

---

## COMPORTEMENT SI OLLAMA EST ABSENT

**Contrat strict des endpoints quand Ollama est injoignable :**

- `/api/health` → HTTP 200, `reachable: false`, `error` renseigné.
- `/api/models` → `[]` **seulement**. Aucune enveloppe `{error, models}`. Le schéma reste `list[ModelInfo]`, inchangé.
- `/api/models/installed` → `[]` seulement.
- `/api/models/loaded` → `[]` seulement.
- `/partials/models` → rend le message d'erreur en combinant health + models côté serveur ; distingue « Ollama injoignable » de « aucun modèle installé ».

Jamais de stacktrace exposée. **Ne change pas le schéma de `/api/models`** : c'est une liste de modèles, pas un conteneur d'erreur. L'erreur provider vit dans `/api/health` et dans l'UI.

Les tests couvrent ce cas. Ne tente **pas** d'installer Ollama. Ne tente **pas** de le démarrer. N'appelle **pas** `systemctl`.

---

## TESTS OBLIGATOIRES

**Règle de mock (critique) :** les mocks interceptent le **transport HTTP brut** (réponses de `/api/tags` et `/api/ps`). Tu testes le **parsing réel** dans `OllamaAdapter`. Ne mocke **pas** `ProviderAdapter.list_installed()` / `list_loaded()` directement — sinon le parsing, seul vrai risque de V0, n'est pas testé.

**Fixtures :**

- Tests #3 et #4 → utilise les **shapes réels** de la section Référence API (avec tag explicite, `details`, etc.).
- Tests #8 et #9 → utilise des **fixtures synthétiques fabriquées à la main**. Le vrai Ollama renvoie toujours un nom taggé et liste généralement un modèle chargé dans `tags` ; ces chemins ne se déclenchent donc qu'avec des inputs construits exprès. Un test #8/#9 nourri d'un échantillon réaliste passerait **sans rien valider** — c'est interdit.

**Liste minimale :**

1. `GET /api/health` → 200, `reachable = true` si Ollama mocké joignable.
2. `GET /api/health` → 200, `reachable = false` si Ollama injoignable.
3. `GET /api/models/installed` parse correctement un payload brut `/api/tags` (shape réel).
4. `GET /api/models/loaded` parse correctement un payload brut `/api/ps` (shape réel).
5. `GET /api/models` fusionne installed + loaded.
6. Modèle installé non chargé → `loaded = false`.
7. Modèle installé et chargé → `loaded = true`, `size_vram` et `expires_at` repris de `/api/ps`.
8. **(fixture synthétique)** Nom sans tag → normalisé en `:latest`.
9. **(fixture synthétique)** Modèle présent dans `/api/ps` mais absent de `/api/tags` → exposé avec `source = "ps_only"` et `loaded = true`.
10. Aucun test ne dépend d'un vrai Ollama local.
11. `uv run ruff check .` passe.
12. `uv run pytest` passe.

---

## DEFINITION OF DONE

V0 est terminée **uniquement si** :

- `uv run ruff check .` passe ;
- `uv run pytest` passe ;
- l'app démarre localement et bind sur `127.0.0.1` ;
- `GET /api/health` retourne 200 même si Ollama est down, avec `reachable: false` ;
- `GET /api/models` retourne un JSON conforme à `ModelInfo` ;
- la fusion utilise le **nom normalisé** comme clé primaire, `digest` en validation secondaire seulement ;
- les cas `:latest` implicite (#8) et `ps_only` (#9) sont testés avec fixtures synthétiques ;
- `GET /partials/models` renvoie un fragment HTML exploité par HTMX ;
- l'UI `/` affiche les modèles, ou un message clair si Ollama est absent ;
- **aucun** fichier de phase future créé ;
- **aucune** action destructive ou système ;
- **aucun** modèle hardcodé ;
- **aucune** commande libre exécutable.

---

## README ATTENDU

Doit contenir : objectif V0 ; installation avec `uv` ; commande de lancement ; variables `OLLAMA_BASE_URL` / `HOST` / `PORT` ; liste des endpoints ; convention `/api/health` ; logique de fusion installés + chargés ; limites explicites et hors-scope.

Bloc obligatoire, tel quel :

```text
V0 est lecture seule.
V0 ne démarre pas Ollama.
V0 ne stoppe aucun service.
V0 ne charge ni décharge aucun modèle.
V0 ne supprime rien.
```

---

## COMMANDES FINALES

```bash
uv run ruff check .
uv run pytest
```

Puis rapporte, factuellement :

- fichiers créés (arborescence réelle produite) ;
- endpoints créés ;
- résultat exact de `ruff` et `pytest` (sortie, pas paraphrase) ;
- limites restantes ;
- TODO **réels**, uniquement s'ils sont constatés à l'exécution.

Gestion des champs API :

- **Champ Ollama inconnu / inattendu** → le conserver dans `raw` ou l'ignorer proprement. **Ne pas halt** : un nouveau champ d'une future version d'Ollama ne doit jamais casser l'inventaire.
- **Champ obligatoire d'identification manquant** (ni `name` ni `model` → modèle non identifiable) → exclure cette entrée de la liste et émettre un TODO/warning. Ne pas fabriquer d'identité, ne pas faire planter tout l'inventaire pour une seule entrée malformée.

Jamais d'invention.

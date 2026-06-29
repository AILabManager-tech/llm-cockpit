# LLM Cockpit — V0

Cockpit local-first, **lecture seule**, qui affiche les modèles Ollama
**installés** (`/api/tags`) et **chargés en mémoire** (`/api/ps`), fusionnés en
un seul inventaire avec un booléen `loaded` fiable par modèle.

V0 est un inventaire. Rien d'autre.

```text
V0 est lecture seule.
V0 ne démarre pas Ollama.
V0 ne stoppe aucun service.
V0 ne charge ni décharge aucun modèle.
V0 ne supprime rien.
```

## Objectif V0

- Afficher le statut du provider Ollama (joignable / injoignable, base URL, erreur claire).
- Lister les modèles installés et les modèles chargés.
- Fusionner les deux en un inventaire unique, chaque modèle portant `loaded`.
- Servir une UI web (HTMX) qui se rafraîchit, **sans aucune action destructive**.

## Installation

Pré-requis : Python 3.12 et [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Lancement

```bash
uv run python -m app.main
# ou
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

L'app bind par défaut sur `127.0.0.1:8000`. Ouvrir <http://127.0.0.1:8000/>.

## Variables d'environnement

| Variable          | Défaut                     | Rôle                          |
|-------------------|----------------------------|-------------------------------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434`   | URL de l'API Ollama           |
| `HOST`            | `127.0.0.1`                | Interface d'écoute de l'app   |
| `PORT`            | `8000`                     | Port d'écoute de l'app        |

## Endpoints

**JSON**

| Méthode / route             | Réponse                                  |
|-----------------------------|------------------------------------------|
| `GET /api/health`           | `ProviderHealth` (toujours **200**)      |
| `GET /api/models`           | `list[ModelInfo]` fusionnée              |
| `GET /api/models/installed` | `list[ModelInfo]` (source `tags`)        |
| `GET /api/models/loaded`    | `list[ModelInfo]` (source `ps`)          |

**HTML (HTMX)**

| Méthode / route        | Réponse                                              |
|------------------------|-----------------------------------------------------|
| `GET /`                | Page complète (`base.html` + `inventory.html`)      |
| `GET /partials/models` | Fragment HTML pour le polling HTMX (`every 5s`)     |

## Convention `/api/health`

`GET /api/health` retourne **toujours HTTP 200** tant que l'app FastAPI tourne.
Si Ollama est injoignable : HTTP 200, `reachable: false`, `error` renseigné.
**Jamais de 503 en V0** — le cockpit est vivant même si le provider est down.

Quand Ollama est injoignable, `/api/models` (et `/installed`, `/loaded`)
renvoient `[]` **strictement** : le schéma reste `list[ModelInfo]`, aucune
enveloppe `{error, models}`. L'erreur provider vit dans `/api/health` et l'UI.

## Logique de fusion (installés + chargés)

1. **Normalisation du nom** : `model` ou `name`, trimé ; un tag implicite
   devient `:latest` (`llama3.2` → `llama3.2:latest`). Nom vide → entrée exclue.
2. **Clé de jointure primaire = nom normalisé.** `digest` ne sert que de
   validation secondaire (non bloquante) quand il est présent des deux côtés.
3. Pour chaque modèle de `/api/ps` :
   - s'il existe dans l'index `/api/tags` → `loaded = true`, on reprend
     `size_vram` et `expires_at` ; la source reste `tags` ;
   - s'il est **absent** de `/api/tags` → on l'expose quand même avec
     `source = "ps_only"`, `loaded = true`, `installed = true`.
4. Incohérence de `digest` entre les deux côtés → `logging.warning` standard,
   l'entrée `tags` est conservée (jamais masquée). **Pas** de système de logs
   applicatif, **pas** de SQLite en V0.

L'UI distingue visuellement « Ollama injoignable » de « aucun modèle installé »
(les deux donnent une liste vide, mais ce sont deux états différents).

## Limites explicites / hors-scope V0

- Aucune action de contrôle : pas de load / unload / pull / delete / start / stop.
- Pas de gateway, routing, RAG, fine-tuning, LoRA/QLoRA, agents, queue, plugins.
- Pas de job background : **un seul process web**.
- Un seul provider : Ollama. Aucun autre provider configuré.
- Tout accès Ollama passe par `app/providers/ollama.py` (seul fichier qui parle
  HTTP à Ollama), derrière l'interface `ProviderAdapter`.

---

# LLM Cockpit — V1 (contrôle sécurisé minimal)

V1 ajoute une **couche additive** sur le même dépôt : depuis le cockpit on peut
**tester**, **charger** et **décharger** un modèle. Rien d'autre. L'inventaire V0
reste intact et fonctionne exactement comme avant.

```text
V1 contrôle uniquement load / unload / test.
V1 ne supprime aucun modèle.
V1 ne fait aucun pull.
V1 ne démarre ni n'arrête aucun service système.
V1 n'introduit aucune base de données (journal JSONL uniquement).
```

## Objectif V1

- **Tester** un modèle installé avec un prompt court (`POST /api/generate`,
  `stream:false`) et afficher la réponse + la latence.
- **Charger** (warmup) un modèle installé non chargé.
- **Décharger** (unload) un modèle chargé.
- **Journaliser** chaque tentative (réussie, en erreur ou refusée) dans un
  fichier JSONL append-only.
- **Refuser** explicitement toute action hors allowlist ou tout modèle absent.

## Allowlist d'actions (figée)

```text
{ load, unload, test }
```

Toute autre action (`delete`, `pull`, `restart`, …) → refus, journalisé
`status="refused"`, **jamais exécutée**. La validation (allowlist + présence du
modèle dans l'inventaire, sur **nom normalisé**) se fait dans
`app/services/actions.py` ; l'adapter exécute, le service décide.

## Nouveaux endpoints V1

**JSON**

| Méthode / route             | Corps                  | Réponse                       |
|-----------------------------|------------------------|-------------------------------|
| `POST /api/actions/load`    | `{model}`              | `ActionResult`                |
| `POST /api/actions/unload`  | `{model}`              | `ActionResult`                |
| `POST /api/actions/test`    | `{model, prompt?}`     | `ActionResult` (réponse dans `detail`) |
| `GET  /api/actions/log`     | `?limit=N`             | `list[ActionLogEntry]` (N plus récentes, ordre inverse) |

**HTML (HTMX)**

| Méthode / route          | Réponse                                  |
|--------------------------|------------------------------------------|
| `GET /partials/actions`  | Fragment du journal d'actions            |

## Codes de retour

- Action refusée (hors allowlist, modèle non installé/non chargé) → **HTTP 400**,
  journalisée `status="refused"`, **aucun** appel à Ollama.
- `ACTIONS_ENABLED=0` → **HTTP 403** « actions désactivées », UI sans boutons.
- Ollama injoignable / timeout pendant une action → **HTTP 200** avec
  `ActionResult(status="error", detail=…)` (corps d'erreur contrôlé, jamais de
  stacktrace, jamais de 5xx). Choix documenté : 200 + corps d'erreur.

## Journal `data/actions.jsonl`

Append-only, une ligne JSON par action, jamais de réécriture. Aucune base de
données (la vraie observabilité, c'est V5). Une entrée :

```json
{"ts":"2026-06-28T19:00:00+00:00","action":"load","model":"qwen2.5:7b","provider":"ollama","status":"ok","detail":"modèle chargé"}
```

`status` ∈ `{ok, error, refused, unsupported}`. Le dossier `data/` est créé au
besoin et **gitignored**.

## Variables d'environnement V1

| Variable           | Défaut              | Rôle                                            |
|--------------------|---------------------|-------------------------------------------------|
| `ACTIONS_ENABLED`  | `1`                 | `0`/`false` → endpoints d'action en 403         |
| `ACTION_TIMEOUT_S` | `60`                | Timeout (s) des appels d'action vers Ollama     |
| `DATA_DIR`         | `data`              | Dossier du journal (`data/actions.jsonl`)       |

Les durées Ollama (`*_duration`) sont en **nanosecondes** ; converties en ms
dans l'adapter (`total_duration_ms`).

---

## Tests

```bash
uv run ruff check .
uv run pytest
```

Les mocks interceptent le **transport HTTP brut** (`/api/tags`, `/api/ps`,
`/api/generate`) : on teste le parsing réel de `OllamaAdapter`, la conversion
ns→ms, et la vraie logique de validation/journal — jamais un mock d'interface.
Aucun test ne dépend d'un Ollama local en cours d'exécution.

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

## Tests

```bash
uv run ruff check .
uv run pytest
```

Les mocks interceptent le **transport HTTP brut** (`/api/tags`, `/api/ps`) : on
teste le parsing réel de `OllamaAdapter`, jamais un mock d'interface. Aucun test
ne dépend d'un Ollama local en cours d'exécution.

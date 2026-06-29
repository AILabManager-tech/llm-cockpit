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

# LLM Cockpit — V2 (rôles locaux de modèles)

V2 permet de raisonner en **usages** plutôt qu'en noms de modèles : on assigne un
**rôle** à un modèle installé, on change ce modèle, et on teste un rôle en
réutilisant le mécanisme de `test` V1. Couche additive ; V0 et V1 restent
fonctionnels.

```text
V2 raisonne en rôles, mais reste mono-provider (Ollama).
V2 ne route aucune application externe.
V2 n'optimise pas le choix de modèle ; il enregistre une préférence déclarée.
V2 n'introduit aucune base de données (préférences en JSON local).
```

## Objectif V2

- Lister les **rôles** et leur modèle assigné courant.
- Assigner / changer le modèle d'un rôle (parmi les modèles **installés**).
- Tester un rôle = lancer le `test` V1 sur le modèle assigné (résultat journalisé
  dans `data/actions.jsonl` comme toute action V1).
- Persister les préférences dans `data/roles.json`, rechargé à chaque lecture.

## Rôles (énumération figée)

```text
chat, code, vision, embedding, fast, quality, experimental
```

Tous les rôles existent dès le départ, **non assignés** (jamais d'invention d'un
modèle). Un rôle ne peut être assigné qu'à un modèle réellement installé
(comparaison sur **nom normalisé**, réutilisée de V0).

## Nouveaux endpoints V2

| Méthode / route               | Corps         | Réponse / effet                              |
|-------------------------------|---------------|----------------------------------------------|
| `GET  /api/roles`             | —             | `list[RoleAssignment]` (les 7 rôles)         |
| `PUT  /api/roles/{role}`      | `{model}`     | `RoleAssignment` ; assigne / change le modèle |
| `POST /api/roles/{role}/test` | `{prompt?}`   | `ActionResult` (réutilise le `test` V1)      |
| `GET  /partials/roles`        | —             | Fragment HTMX du panneau Rôles               |

Codes de retour : rôle inconnu → **400** ; modèle non installé → **400** ;
rôle non assigné lors d'un test → **400** ; `roles.json` corrompu → **400** avec
message clair (le fichier n'est **jamais** écrasé silencieusement).

## Persistance `data/roles.json`

Fichier JSON local, **écriture atomique** (`tmp` + `os.replace`). Aucune base de
données. `data/` est gitignored. Forme :

```json
{
  "assignments": {
    "chat": {"model": "qwen2.5:7b", "provider": "ollama", "updated_at": "..."}
  }
}
```

`roles.json` absent → état vide (tous rôles non assignés). `roles.json` corrompu
→ erreur claire, jamais d'écrasement.

## Variable d'environnement V2

| Variable            | Défaut             | Rôle                                |
|---------------------|--------------------|-------------------------------------|
| `ROLES_CONFIG_PATH` | `data/roles.json`  | Emplacement du fichier de préférences |

---

# LLM Cockpit — V3 (registry multi-provider)

V3 centralise plusieurs **providers** derrière un registry local et agrège leur
inventaire, sans casser le cœur. Un deuxième type d'adapter (**OpenAI-compatible**,
LM Studio / llama.cpp server / etc.) rejoint Ollama. V0, V1 et V2 restent
fonctionnels.

```text
V3 centralise plusieurs providers mais n'expose pas encore de gateway.
V3 n'invente jamais un provider ou un modèle non détecté.
V3 ne supporte load/unload que là où le provider le permet (Ollama).
V3 n'introduit aucune base de données (registry en JSON local).
```

## Objectif V3

- **Registry** local de providers (`id`, `kind`, `base_url`, `enabled`).
- Ajouter / retirer un provider ; Ollama reste le provider **par défaut**.
- **Adapter OpenAI-compatible** minimal (`/v1/models`, `/v1/chat/completions`),
  en HTTP brut (pas le SDK `openai`).
- Inventaire **agrégé multi-provider** : `/api/models` concatène les providers
  activés, chaque `ModelInfo` portant son `provider`. Forme `list[ModelInfo]`
  inchangée.
- État de chaque provider (joignable, capacités, nombre de modèles).
- **Détection de drift** registry ↔ réalité.

## Kinds d'adapter & capacités

| Kind            | `list_installed` | `list_loaded` | `load`/`unload` | `generate` |
|-----------------|:----------------:|:-------------:|:---------------:|:----------:|
| `ollama`        | ✅ | ✅ | ✅ | ✅ (`/api/generate`) |
| `openai_compat` | ✅ (`/v1/models`) | ❌ | ❌ → `unsupported` | ✅ (`/v1/chat/completions`) |

`load`/`unload` hors Ollama renvoient `ActionResult(status="unsupported")`,
jamais une exception. Les contrôles V1 et les rôles V2 restent **scopés Ollama**.

## Détection de drift

Le drift compare l'état **déclaré** dans le registry à la **réalité** observée :

- déclaré actif (`enabled`) mais **injoignable** → drift ;
- déclaré désactivé mais **répond quand même** → drift (présent inattendu).

Exposé via `GET /api/registry/drift`, jamais masqué. Un provider injoignable est
isolé : il contribue `[]` à l'agrégat sans casser les autres.

## Nouveaux endpoints V3

| Méthode / route            | Corps                          | Réponse / effet                         |
|----------------------------|--------------------------------|-----------------------------------------|
| `GET    /api/providers`    | —                              | `list[ProviderStatus]`                  |
| `POST   /api/providers`    | `{id, kind, base_url, enabled?}` | `ProviderConfig` (**201**)            |
| `DELETE /api/providers/{id}` | —                            | `{removed: id}`                         |
| `GET    /api/registry/drift` | —                            | `list[RegistryDrift]`                   |
| `GET    /partials/providers` | —                            | Fragment HTMX du panneau Providers      |

`/api/models` (V0) renvoie désormais l'inventaire **agrégé**. Codes : kind
inconnu → **400** ; `id`/`base_url` dupliqué → **409** ; provider absent
(DELETE) → **404** ; `providers.json` corrompu → **400** clair, jamais écrasé.

## Persistance `data/providers.json`

JSON local, **écriture atomique** (`tmp` + `os.replace`), gitignored. Absent →
un seul provider Ollama par défaut (depuis `OLLAMA_BASE_URL`), jamais d'invention
d'un second provider.

```json
{
  "providers": [
    {"id": "ollama", "kind": "ollama", "base_url": "http://127.0.0.1:11434", "enabled": true}
  ]
}
```

## Variable d'environnement V3

| Variable                | Défaut                 | Rôle                          |
|-------------------------|------------------------|-------------------------------|
| `PROVIDERS_CONFIG_PATH` | `data/providers.json`  | Emplacement du registry local |

---

## Tests

```bash
uv run ruff check .
uv run pytest
```

Les mocks interceptent le **transport HTTP brut** (`/api/tags`, `/api/ps`,
`/api/generate`, `/v1/models`, `/v1/chat/completions`) : on teste le parsing réel
des adapters `OllamaAdapter` et `OpenAICompatAdapter`, la conversion ns→ms, la
logique de validation/journal, la persistance JSON réelle des rôles, et
l'agrégation/drift du registry — jamais un mock d'interface. Aucun test ne dépend
d'un provider local en cours d'exécution.

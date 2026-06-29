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

# LLM Cockpit — V4 (gateway OpenAI-compatible local)

V4 expose un **point d'entrée unique** : un endpoint local compatible OpenAI.
Une application ne parle plus à Ollama ; elle parle au cockpit avec un nom de
**rôle** (ou un modèle réel), et le cockpit route vers le bon provider/modèle.
V0–V3 restent fonctionnels.

```text
V4 expose un gateway OpenAI minimal, local uniquement.
V4 route par rôle ; il ne mesure pas encore (observabilité = V5).
V4 ne fait ni RAG, ni évaluation, ni fine-tuning.
V4 ne s'expose pas au réseau par défaut (127.0.0.1).
```

## Objectif V4

- `POST /v1/chat/completions` : `model` peut être un **rôle** (`"code"` ou
  `"role:code"`) résolu via les rôles V2/V3, ou un **modèle réel**.
- Réponse au format OpenAI minimal (`choices[].message`, `usage` si disponible),
  plus une métadonnée `x_cockpit_route` (provider/modèle résolus).
- `GET /v1/models` : modèles réels agrégés **+ alias de rôles** (`role:chat`…).
- `GET /api/routes` : table de routage consultable (ce que chaque rôle résout).
- Routage strict : ne route que vers un modèle **réellement présent** chez un
  provider **joignable** (présent dans l'inventaire agrégé V3). Aucun fallback
  silencieux — un rôle non assigné ou un modèle absent donne une erreur claire.

## Routage

`model` reçu →

1. nom de rôle (`role:NAME` ou `NAME` ∈ rôles V2) → résout l'assignation
   `(provider, model)` du rôle, vérifie sa présence dans l'agrégat ;
2. sinon, modèle réel → cherche le `(provider, model)` correspondant dans
   l'agrégat.

Le résultat est une `RouteDecision{requested, resolved_role, provider, model,
ok, reason}`. `model` absent dans la requête → rôle par défaut
`GATEWAY_DEFAULT_ROLE`.

## Nouveaux endpoints V4

| Méthode / route             | Corps / effet                                          |
|-----------------------------|--------------------------------------------------------|
| `POST /v1/chat/completions` | `{model?, messages[]}` → complétion OpenAI routée      |
| `GET  /v1/models`           | modèles réels + alias `role:*`                         |
| `GET  /api/routes`          | `list[RouteDecision]` (résolution par rôle)            |
| `GET  /partials/gateway`    | Fragment HTMX du panneau Gateway                       |

Codes / erreurs (format OpenAI, objet `error`) : rôle non assigné / modèle
inexistant → **400** ; provider injoignable pendant le chat → **502** ;
`GATEWAY_ENABLED=0` → **404** sur `/v1/*`. Jamais de stacktrace exposée.

## Traduction interne

- provider `ollama` → `POST /api/chat` (API native, `stream:false`) ;
- provider `openai_compat` → `POST /v1/chat/completions`.

Le gateway est **local uniquement** (`127.0.0.1`), jamais exposé au réseau par
défaut. **Streaming hors scope V4** (`stream` ignoré, réponse non-streamée).

## Variables d'environnement V4

| Variable               | Défaut  | Rôle                                        |
|------------------------|---------|---------------------------------------------|
| `GATEWAY_ENABLED`      | `1`     | `0`/`false` → `/v1/*` en 404                |
| `GATEWAY_DEFAULT_ROLE` | `chat`  | Rôle utilisé si la requête n'a pas de `model` |

---

# LLM Cockpit — V5 (observabilité gateway, SQLite local)

V5 **mesure** le trafic réel : chaque requête du gateway V4 est journalisée dans
une base **SQLite locale**, et un **dashboard** affiche volume, latence et taux
d'erreur. C'est ici — et pas avant — que SQLite entre dans le projet. Le journal
d'actions V1 (`data/actions.jsonl`) reste distinct (deux mécanismes assumés).
V0–V4 restent fonctionnels.

```text
V5 observe le trafic réel du gateway via SQLite local.
V5 ne crée aucun jeu de tests (évaluations = V6).
V5 ne logge pas le contenu des prompts par défaut.
V5 reste local-first : aucun collecteur externe.
```

## Objectif V5

- Logger chaque requête `/v1/chat/completions` (succès, refus ou erreur) :
  `ts`, route, app appelante, rôle, provider, modèle, latence, statut,
  `http_status`, tokens (si le provider les fournit), erreur.
- Persister en **SQLite** (`data/cockpit.db`, WAL, schéma idempotent).
- **Stats agrégées** : volume, taux d'erreur, latence p50/p95, répartition par
  modèle / provider / app.
- **Dashboard** `/dashboard` (HTMX, rafraîchi périodiquement).

## Identification de l'app appelante

En-tête **`X-Cockpit-App`** (sinon `null`). Choix figé : l'en-tête explicite est
plus fiable que le `user-agent`. Une app cliente envoie `X-Cockpit-App: <nom>`.

## PII : contenu des prompts

Par défaut, **le contenu des prompts n'est pas stocké** (`LOG_PROMPTS=0`). Si
activé, il est **tronqué** à `LOG_PROMPT_MAX_CHARS`. Le champ `prompt` n'est
**jamais exposé** via `/api/logs` (omis du schéma `RequestLog`).

## Best-effort

Le logging ne fait **jamais** échouer une requête gateway : toute erreur d'écriture
(DB verrouillée, backend indisponible) est avalée proprement. DB absente → créée
au démarrage ; fenêtre de stats vide → zéros francs ; tokens absents → `None`
(jamais inventés).

## Nouveaux endpoints V5

| Méthode / route          | Paramètres                                  | Réponse              |
|--------------------------|---------------------------------------------|----------------------|
| `GET /api/logs`          | `?limit&model&provider&app&status`          | `list[RequestLog]`   |
| `GET /api/stats`         | `?window` (secondes)                        | `StatsSummary`       |
| `GET /dashboard`         | —                                           | Page dashboard HTMX  |
| `GET /partials/dashboard`| —                                           | Fragment HTMX        |

Seules les requêtes `/v1/chat/completions` sont journalisées (le trafic
d'inférence). `/v1/models` n'est pas loggé.

## Persistance `data/cockpit.db`

SQLite, table `request_log`, schéma idempotent (`app/db/schema.sql`), mode WAL.
Gitignored (couvert par `data/`). Seul `app/db/store.py` accède à la base.

## Variables d'environnement V5

| Variable              | Défaut             | Rôle                                       |
|-----------------------|--------------------|--------------------------------------------|
| `DB_PATH`             | `data/cockpit.db`  | Emplacement de la base SQLite              |
| `LOG_PROMPTS`         | `0`                | `1` → stocke le prompt (tronqué)           |
| `LOG_PROMPT_MAX_CHARS`| `500`              | Troncature du prompt si `LOG_PROMPTS=1`    |

---

## Tests

```bash
uv run ruff check .
uv run pytest
```

Les mocks interceptent le **transport HTTP brut** (`/api/tags`, `/api/ps`,
`/api/generate`, `/api/chat`, `/v1/models`, `/v1/chat/completions`) : on teste le
parsing réel des adapters, la conversion ns→ms, la logique de validation/journal,
la persistance JSON réelle des rôles, l'agrégation/drift du registry, la
résolution de routage du gateway, et la persistance SQLite réelle des logs
(insert/query, percentiles, best-effort) — jamais un mock d'interface. Aucun test
ne dépend d'un provider local en cours d'exécution.

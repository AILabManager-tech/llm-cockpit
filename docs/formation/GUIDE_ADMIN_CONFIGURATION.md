# Guide administrateur / configuration — LLM Cockpit V8

Pour l'opérateur qui installe, configure et exploite le cockpit. Couvre le
démarrage, les variables d'environnement, l'arborescence des données, les
invariants de sécurité, et l'activation (optionnelle) d'un runner d'adaptation
réel.

---

## 1. Démarrage et ports

```bash
cd ~/llm-cockpit
git checkout phase/v8
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- **Bind local obligatoire** : `127.0.0.1`. Ne **jamais** binder `0.0.0.0` :
  le gateway exposerait tes modèles au réseau. Aucune authentification n'est
  prévue car le cockpit est conçu local-first.
- **Choix du port** : `8000` est souvent occupé sur cette machine. Utilise
  `8001`, puis `8010`/`8011`/`8012` au besoin (`ss -ltn | grep :8001` pour
  vérifier).
- **Module** : `app.main:app`. Le point d'entrée `python -m app.main` lit
  `HOST`/`PORT` depuis l'environnement.

---

## 2. Variables d'environnement (par phase)

Toutes les variables ont des **défauts sûrs**. Rien n'est obligatoire pour
démarrer (sauf un Ollama joignable pour un usage réel).

### Réseau / provider de base (V0)

| Variable          | Défaut                     | Rôle                              |
|-------------------|----------------------------|-----------------------------------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434`   | URL de l'API Ollama               |
| `HOST`            | `127.0.0.1`                | Interface d'écoute (garder local) |
| `PORT`            | `8000`                     | Port d'écoute                     |
| `DATA_DIR`        | `data`                     | Racine des données runtime        |

### Contrôle (V1)

| Variable           | Défaut  | Rôle                                          |
|--------------------|---------|-----------------------------------------------|
| `ACTIONS_ENABLED`  | `1`     | `0` → actions load/unload/test en 403         |
| `ACTION_TIMEOUT_S` | `60`    | Timeout des actions vers Ollama (s)           |

### Rôles (V2)

| Variable            | Défaut             | Rôle                          |
|---------------------|--------------------|-------------------------------|
| `ROLES_CONFIG_PATH` | `data/roles.json`  | Préférences de rôles (JSON)   |

### Registry (V3)

| Variable                | Défaut                 | Rôle                          |
|-------------------------|------------------------|-------------------------------|
| `PROVIDERS_CONFIG_PATH` | `data/providers.json`  | Registry des providers (JSON) |

### Gateway (V4)

| Variable               | Défaut  | Rôle                                        |
|------------------------|---------|---------------------------------------------|
| `GATEWAY_ENABLED`      | `1`     | `0` → `/v1/*` en 404                         |
| `GATEWAY_DEFAULT_ROLE` | `chat`  | Rôle utilisé si la requête n'a pas de `model` |

### Observabilité (V5)

| Variable               | Défaut             | Rôle                                  |
|------------------------|--------------------|---------------------------------------|
| `DB_PATH`              | `data/cockpit.db`  | Base SQLite (logs + évals + RAG + V8) |
| `LOG_PROMPTS`          | `0`                | `1` → stocke le prompt (tronqué)      |
| `LOG_PROMPT_MAX_CHARS` | `500`              | Troncature si `LOG_PROMPTS=1`         |

### Évaluations (V6)

| Variable                    | Défaut             | Rôle                          |
|-----------------------------|--------------------|-------------------------------|
| `EVALS_DIR`                 | `app/evals/suites` | Dossier des suites YAML       |
| `EVAL_RESPONSE_PREVIEW_MAX` | `500`              | Troncature de la réponse stockée |

### RAG (V7)

| Variable                | Défaut             | Rôle                                   |
|-------------------------|--------------------|----------------------------------------|
| `RAG_DOCS_DIR`          | `data/rag/docs`    | Dossier autorisé pour l'ingestion      |
| `RAG_EMBED_MODEL`       | `nomic-embed-text` | Modèle d'embedding (doit être installé)|
| `RAG_TOP_K`             | `4`                | Nombre de chunks récupérés             |
| `RAG_CHUNK_SIZE`        | `800`              | Taille de chunk (caractères)           |
| `RAG_CHUNK_OVERLAP`     | `100`              | Recouvrement entre chunks              |
| `RAG_SOURCE_PREVIEW_MAX`| `240`              | Troncature de l'aperçu de source       |

### Adaptation (V8)

| Variable           | Défaut            | Rôle                                          |
|--------------------|-------------------|-----------------------------------------------|
| `DATASETS_DIR`     | `data/datasets`   | Dossier autorisé des datasets                 |
| `ADAPTERS_DIR`     | `data/adapters`   | Sortie des adaptateurs (par job)              |
| `TRAIN_BASE_MODEL` | *(vide)*          | Modèle de base par défaut ; vide → refus      |
| `TRAIN_RUNNER`     | *(vide)*          | Module runner allowlisté ; vide → **dry-run** |
| `TRAIN_MIN_ROWS`   | `1`               | Taille minimale du dataset                    |
| `TRAIN_LOG_TAIL_MAX` | `2000`          | Taille max du log conservé par job            |

---

## 3. Arborescence des données (`data/`)

Tout le runtime vit sous `DATA_DIR` (défaut `data/`), **gitignored**, jamais
committé (PII).

```text
data/
├─ roles.json            # assignations de rôles (V2)
├─ providers.json        # registry des providers (V3)
├─ actions.jsonl         # journal d'actions append-only (V1) — NON migré en SQLite
├─ cockpit.db            # SQLite : request_log, eval_*, rag_*, dataset/train_job/model_version
├─ rag/docs/             # documents à ingérer (V7)
├─ datasets/             # datasets d'adaptation .jsonl (V8)
└─ adapters/job_<id>/    # sortie des jobs d'adaptation (V8)
```

> Deux mécanismes de log coexistent volontairement : `actions.jsonl` (V1, actions
> de contrôle) et `cockpit.db` (V5+, trafic gateway et au-delà). Le journal V1
> n'a **pas** été migré.

Pour repartir propre : arrête l'app et supprime `data/` (tu perds rôles,
providers, logs, évals, documents RAG, datasets, versions). À faire en
connaissance de cause.

---

## 4. Invariants de sécurité

- **Local uniquement** : `127.0.0.1`, pas de CORS wildcard.
- **Pas de commande shell libre** : les actions Ollama et le runner d'adaptation
  passent par des appels contrôlés (`httpx`) ou un **sous-process en argv
  liste** ; jamais `shell=True`, jamais `systemctl`.
- **Pas de PII par défaut** : le contenu des prompts n'est pas stocké
  (`LOG_PROMPTS=0`) et n'est jamais exposé par `/api/logs`.
- **Ingestion restreinte** : RAG et datasets ne lisent que dans leur dossier
  autorisé (traversée `..` refusée).
- **Pas de téléchargement distant** : ni dataset, ni modèle, ni base externe.
- **Non destructif** : load/unload/test ne suppriment rien ; un job d'adaptation
  échoué/annulé laisse le baseline intact ; le baseline n'est jamais écrasé.

---

## 5. Ajouter un second provider (OpenAI-compatible)

Pour brancher LM Studio, llama.cpp server, etc. :

```bash
curl -X POST http://127.0.0.1:8001/api/providers \
  -H "Content-Type: application/json" \
  -d '{"id":"lmstudio","kind":"openai_compat","base_url":"http://127.0.0.1:1234"}'
```

- L'inventaire devient **agrégé** (chaque modèle porte son `provider`).
- Un provider injoignable est **isolé** : il n'invalide pas les autres et
  apparaît en **drift**.
- `id` ou `base_url` dupliqué → 409 ; `kind` inconnu → 400.
- Les modèles `openai_compat` ne supportent **pas** load/unload, et ne sont pas
  assignables à un rôle en V8 (rôles scopés Ollama).

---

## 6. Activer un runner d'adaptation réel (optionnel, avancé)

**Par défaut, le cockpit reste en dry-run** (`TRAIN_RUNNER` vide) : il valide et
prépare, mais ne lance aucun entraînement. C'est le mode recommandé pour
découvrir l'orchestration sans coût ni risque.

Pour activer un entraînement réel **(décision opérateur)** :

1. Installe les dépendances lourdes **hors du cockpit**, dans l'environnement du
   runner (ex. `peft`, `transformers`, `datasets`, `bitsandbytes` pour QLoRA).
   Ne les ajoute **pas** à `pyproject.toml` du cockpit.
2. Écris un module runner exposant l'interface argv attendue :
   `python -m <module> --dataset <path> --base-model <m> --method <lora|qlora>
   --output <dir>`.
3. Définis :

```bash
export TRAIN_BASE_MODEL="qwen2.5:7b"
export TRAIN_RUNNER="ton_module_runner"
```

4. Le job lancera alors un **sous-process** (argv liste, jamais shell), capturera
   les logs, et — en cas de succès — enregistrera une **version candidate**.
5. **Promotion** : associe un `eval_run` au candidat et au baseline
   (`POST /api/models/versions/{id}/eval`), puis `POST /api/models/promote`. La
   promotion n'est acceptée que si le candidat **bat** le baseline (sinon 409).

> Rappel : promouvoir ne sert pas l'adapter. Le gateway continue de servir le
> modèle de base. Servir réellement un adapter (export GGUF + import Ollama, ou
> serveur dédié) est hors périmètre V8.
> Faisabilité matérielle : QLoRA d'un 7B vise une carte ~16 Go (ex. RTX 5080) ;
> ajuste la méthode/le modèle selon ta VRAM.

---

## 7. Santé et maintenance

```bash
uv run ruff check .     # style/lint
uv run pytest           # 134 tests (logique complète V0→V8)
git status --short      # doit rester propre ; data/ non suivi
```

- `pytest` valide la **logique** (transport mocké), pas le rendu visuel : double
  avec la checklist de `PARCOURS_VALIDATION_PAR_LES_TESTS.md`.
- Les fichiers sous `data/` ne doivent jamais apparaître dans `git status`
  (ils sont gitignored).

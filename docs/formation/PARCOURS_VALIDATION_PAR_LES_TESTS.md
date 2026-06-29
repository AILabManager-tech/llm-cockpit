# Parcours de validation par les tests — LLM Cockpit V8

Ce document traduit la **suite de tests automatisés** (`tests/`) en matière
pédagogique : ce que chaque module **prouve**, comment le **reproduire**
toi-même dans l'interface ou avec `curl`, ce que tu dois **voir**, les **erreurs
fréquentes**, et comment savoir si le comportement est **normal**.

> Les tests valident la *logique* (transport HTTP mocké, aucun modèle réel
> requis). Les reproductions ci-dessous utilisent ta **vraie** instance : prévois
> qu'Ollama tourne et que les modèles cités soient installés (adapte les noms).
> URL d'exemple : `http://127.0.0.1:8001`.

---

## A. Ce que les tests prouvent

Vue d'ensemble : 134 tests verts couvrent l'ensemble V0→V8. Les 14 fichiers
ci-dessous correspondent aux modules visibles dans l'interface.

| Fichier de test            | Module                       | Ce qui est prouvé (en clair)                                                       |
|----------------------------|------------------------------|------------------------------------------------------------------------------------|
| `test_actions.py`          | Actions load/unload/test     | Les actions ne s'exécutent que sur un modèle réellement présent ; tout est journalisé ; hors-allowlist refusé. |
| `test_roles.py`            | Rôles                        | Assignation persistée + relue ; nom normalisé ; modèle non installé / rôle inconnu refusés ; test de rôle réutilise le test V1. |
| `test_gateway.py`          | Gateway `/v1/*`              | Routage par rôle et par modèle réel ; erreurs OpenAI claires ; `/v1/models` liste modèles + alias de rôles ; 404 si désactivé. |
| `test_logging.py`          | Logs SQLite                  | Une requête gateway = exactement une ligne ; refus loggés ; tokens absents = `None` ; prompt non stocké par défaut ; un échec de log ne casse pas la requête. |
| `test_stats.py`            | Stats dashboard              | Fenêtre vide = zéros ; p50/p95 corrects ; répartitions par modèle/app.            |
| `test_checks.py`           | Checks d'évaluation          | Chaque check déterministe se comporte comme annoncé ; un check inconnu/mal formé est refusé avant exécution. |
| `test_evals.py`            | Évaluations                  | Un run sur 2 modèles produit des résultats corrects ; modèle absent = cas `error` sans casser le run ; persistance en SQLite. |
| `test_scoreboard.py`       | Scoreboard                   | Agrégation par (rôle, modèle) ; filtre par rôle ; scoreboard vide géré.           |
| `test_rag_ingest.py`       | RAG ingestion                | Chunking déterministe ; traversée de chemin bloquée ; ingestion stocke les chunks ; modèle d'embedding absent → erreur. |
| `test_rag_query.py`        | RAG query                    | Cosinus correct ; top-K ordonné par similarité ; réponse cite de vraies sources ; store vide = réponse honnête. |
| `test_rag_eval.py`         | RAG vs non-RAG               | Mode non-RAG délègue au runner V6 ; mode RAG augmente les prompts et tag le rôle `+rag`. |
| `test_dataset.py`          | Datasets V8                  | Formats acceptés validés ; JSON invalide / champs manquants / trop petit / traversée refusés. |
| `test_train_job.py`        | Training (dry-run)           | Commande en **argv liste, jamais shell** ; base_model vide refusé ; dry-run sans runner ; succès→version, échec→baseline intact ; annulation. |
| `test_model_registry.py`   | Promotion / serving          | Baseline actif ; promotion **gatée** par les évals ; rollback restaure le baseline ; `serving_status` honnête. |

---

## B. Parcours de validation utilisateur

Pour chaque module : **(test)** ce que le test garantit · **(refaire)** comment
le reproduire · **(voir)** ce que tu dois constater · **(erreur)** piège
courant · **(normal ?)** comment savoir que c'est bon.

### B.1 Inventaire des modèles

- **(test)** L'inventaire agrège les modèles **installés** et **chargés** par
  provider (cf. `test_inventory.py`, `test_registry.py`).
- **(refaire)** Page Inventaire, ou `curl http://127.0.0.1:8001/api/models`.
- **(voir)** Une ligne par modèle, avec provider, état `chargé`/`non chargé`,
  taille, digest.
- **(erreur)** Liste vide alors qu'Ollama est lancé → vérifier que le provider
  Ollama est **joignable** (statut dans le panneau Providers).
- **(normal ?)** Le nombre de modèles correspond à `ollama list`.

### B.2 Actions load / unload / test

- **(test)** `test_load_installed_ok`, `test_unload_loaded_ok`,
  `test_test_installed_parses_duration` prouvent que charger/décharger/tester un
  modèle **présent** fonctionne et est journalisé.
  `test_load_not_installed_refused_no_http` prouve qu'un modèle **absent** est
  refusé **sans même appeler** Ollama. `test_action_outside_allowlist_refused`
  prouve que toute action hors `{load, unload, test}` est refusée.
  `test_actions_disabled_returns_403` : si `ACTIONS_ENABLED=0`, les actions
  renvoient 403.
- **(refaire)** Inventaire → bouton **Charger** sur un modèle non chargé, puis
  **Décharger**. Puis section **Tester un modèle**.
- **(voir)** L'état du modèle bascule (`non chargé` ↔ `chargé`) ; une ligne
  apparaît dans le **Journal d'actions** (`ok`).
- **(erreur)** Tenter de charger un modèle non installé → refus (400) ; c'est
  voulu.
- **(normal ?)** Chaque action laisse une trace dans le journal, succès **ou**
  refus.

### B.3 Rôles

- **(test)** `test_roles_initial_state_all_unassigned` : 7 rôles, aucun assigné
  au départ. `test_assign_installed_model_persists` /
  `test_assignment_reloaded_by_fresh_service` : l'assignation est **persistée et
  relue**. `test_assign_normalizes_name` : `qwen2.5:7b` et `qwen2.5` pointent au
  même endroit (`:latest` implicite). `test_assign_not_installed_refused` et
  `test_assign_unknown_role_400` : modèle absent ou rôle inconnu refusés.
  `test_role_test_reuses_v1_test` : tester un rôle réutilise le test de modèle.
- **(refaire)** Inventaire → **Rôles** → assigne `chat` à un modèle ; recharge la
  page (l'assignation tient). `curl http://127.0.0.1:8001/api/roles`.
- **(voir)** « Mis à jour » se remplit ; au rechargement, le modèle reste choisi.
- **(erreur)** Choisir un modèle non installé → refus ; tester un rôle non
  assigné → refus.
- **(normal ?)** `data/roles.json` contient ton assignation (gitignored).

### B.4 Gateway `/v1/chat/completions`

- **(test)** `test_chat_completions_routed_by_role` : `model:"chat"` est résolu
  vers le modèle assigné. `test_chat_completions_routed_by_real_model` : un nom
  réel marche aussi. `test_chat_unassigned_role_openai_error` : rôle non assigné
  → erreur OpenAI 400. `test_chat_provider_down_502` : provider injoignable →
  502. `test_v1_models_lists_models_and_role_aliases` : `/v1/models` liste
  modèles **et** alias `role:*`. `test_gateway_disabled_404` : `GATEWAY_ENABLED=0`
  → 404. `test_api_routes_table` : `/api/routes` montre la résolution par rôle.
- **(refaire)** :

```bash
curl -X POST http://127.0.0.1:8001/v1/chat/completions \
  -H "Content-Type: application/json" -H "X-Cockpit-App: formation" \
  -d '{"model":"chat","messages":[{"role":"user","content":"Réponds OK."}]}'

curl http://127.0.0.1:8001/v1/models
```

- **(voir)** Réponse format OpenAI (`choices[0].message`) + `x_cockpit_route`
  (provider/modèle réels). Dans l'UI, la table Gateway montre `chat` **routable**.
- **(erreur)** `model:"vision"` non assigné → `{"error": …}` 400 ; c'est voulu.
- **(normal ?)** `x_cockpit_route.provider/model` correspond à l'assignation du
  rôle.

### B.5 Logs SQLite

- **(test)** `test_chat_produces_exactly_one_log` : un appel = une ligne.
  `test_refused_request_is_logged` : même un refus est tracé.
  `test_tokens_absent_logged_as_none` : pas d'invention de tokens.
  `test_prompt_not_stored_by_default` : le **contenu du prompt n'est pas stocké**.
  `test_logging_failure_does_not_break_request` : si l'écriture de log échoue, la
  requête aboutit quand même.
- **(refaire)** Fais 2-3 appels gateway, puis
  `curl http://127.0.0.1:8001/api/logs`.
- **(voir)** Une ligne par appel (app, rôle, provider, modèle, statut, latence,
  tokens). Aucun champ `prompt` exposé.
- **(erreur)** Logs vides → tu n'as pas encore appelé le **gateway** (les tests
  de modèle/rôle et les évals n'y comptent pas).
- **(normal ?)** Le nombre de lignes = nombre d'appels gateway faits.

### B.6 Stats du dashboard

- **(test)** `test_empty_window_is_zeros` : sans données, tout est à zéro (pas
  d'erreur). `test_percentiles_and_error_rate` : p50/p95 et taux d'erreur
  calculés sur des valeurs connues. `test_buckets_by_model_and_app` : répartition
  correcte.
- **(refaire)** Dashboard, ou `curl http://127.0.0.1:8001/api/stats`.
- **(voir)** Cartes total/erreurs/taux, p50/p95, répartitions par
  modèle/provider/app.
- **(erreur)** Latences à `—` → aucune requête avec latence enregistrée.
- **(normal ?)** Total des stats = total des lignes de `/api/logs`.

### B.7 Checks d'évaluation

- **(test)** `test_non_empty`, `test_json_valid`, `test_contains`, `test_regex`,
  `test_equals`, `test_min_max_length`, `test_latency_lt` : chaque check fait ce
  qu'il annonce. `test_unknown_check_raises`, `test_missing_argument_raises`,
  `test_non_numeric_argument_raises` : un check mal écrit est **refusé avant**
  tout run.
- **(refaire)** Ces checks composent les suites d'éval (`app/evals/suites/*.yaml`).
  Tu les déclenches en lançant une éval (§B.8).
- **(voir)** Dans le détail d'un run, chaque check passe (`✔`) ou échoue avec un
  détail inspectable.
- **(erreur)** Un check inconnu dans une suite → l'éval est refusée (400) avant
  de tourner.
- **(normal ?)** Les checks sont **déterministes** : même entrée → même verdict.

### B.8 Évaluations

- **(test)** `test_run_two_models_one_ok_one_error` : comparer 2 modèles produit
  des résultats corrects, et un modèle introuvable devient un cas `error` **sans
  casser le run**. `test_run_persists_to_sqlite` : le run est persisté.
  `test_unknown_suite_raises`, `test_unknown_check_in_suite_raises`,
  `test_no_models_raises` : entrées invalides refusées.
- **(refaire)** :

```bash
curl -X POST http://127.0.0.1:8001/api/evals/run \
  -H "Content-Type: application/json" \
  -d '{"suite":"summary","models":["qwen2.5:7b"]}'
```

- **(voir)** Un `EvalRunSummary` avec un résultat par (cas × modèle), statut,
  score, latence.
- **(erreur)** Suite inconnue → 400 ; modèle absent → cas `error` (le reste du
  run continue).
- **(normal ?)** Le run apparaît dans **Runs récents** du scoreboard.

### B.9 Scoreboard

- **(test)** `test_scoreboard_aggregates_by_role_model` : agrégation par (rôle,
  modèle) avec taux de réussite, latence moyenne, erreurs ; tri par taux
  décroissant. `test_scoreboard_role_filter` : filtre par rôle.
  `test_empty_scoreboard` : vide géré.
- **(refaire)** Dashboard → Scoreboard, ou
  `curl http://127.0.0.1:8001/api/scoreboard`.
- **(voir)** Une ligne par (rôle, modèle) ; le meilleur taux en haut.
- **(erreur)** Scoreboard vide → aucune éval lancée.
- **(normal ?)** Lancer la même éval sur 2 modèles crée 2 lignes comparables.

### B.10 RAG — ingestion

- **(test)** `test_chunk_text_deterministic` : le découpage est reproductible.
  `test_resolve_blocks_traversal` : impossible d'ingérer hors de
  `data/rag/docs/`. `test_ingest_document_stores_chunks` : les chunks sont
  stockés. `test_ingest_missing_embed_model` : si le modèle d'embedding est
  absent → erreur claire.
- **(refaire)** Place `notes.md` sous `data/rag/docs/`, puis :

```bash
curl -X POST http://127.0.0.1:8001/api/rag/ingest \
  -H "Content-Type: application/json" -d '{"path":"notes.md"}'
```

- **(voir)** Le document apparaît (id, nombre de chunks, dimension, modèle).
- **(erreur)** Chemin `../…` → refus ; `nomic-embed-text` non installé → erreur.
- **(normal ?)** `dim` est cohérent (ex. 768 pour `nomic-embed-text`).

### B.11 RAG — query avec sources

- **(test)** `test_retrieve_top_k_orders_by_similarity` : les chunks les plus
  proches sortent en premier. `test_answer_with_sources` : la réponse cite de
  **vraies** sources. `test_answer_empty_store_is_honest` : sans document, la
  réponse dit honnêtement qu'il n'y a pas de source (pas d'hallucination).
- **(refaire)** :

```bash
curl -X POST http://127.0.0.1:8001/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Résume les documents ingérés.","role":"chat"}'
```

- **(voir)** Une réponse + une liste de `sources` (`doc#chunk` + score).
- **(erreur)** Réponse « Aucune source » → tu n'as rien ingéré (comportement
  honnête, pas un bug).
- **(normal ?)** Les sources citées correspondent à des documents que tu as
  réellement ingérés.

### B.12 RAG vs non-RAG

- **(test)** `test_eval_without_rag_delegates_to_runner` : sans RAG, on joue la
  suite telle quelle. `test_eval_with_rag_augments_and_tags_role` : avec RAG, les
  prompts sont **augmentés** du contexte et le run est tagué `rôle+rag`.
- **(refaire)** Lance la même suite deux fois :

```bash
curl -X POST http://127.0.0.1:8001/api/rag/eval -H "Content-Type: application/json" \
  -d '{"suite":"summary","with_rag":false,"models":["qwen2.5:7b"]}'
curl -X POST http://127.0.0.1:8001/api/rag/eval -H "Content-Type: application/json" \
  -d '{"suite":"summary","with_rag":true,"models":["qwen2.5:7b"]}'
```

- **(voir)** Deux runs ; le scoreboard montre `chat` et `chat+rag` **distincts**.
- **(erreur)** Croire que le RAG est forcément meilleur : compare les chiffres.
- **(normal ?)** Le RAG n'est « bon » que si son taux dépasse le non-RAG.

### B.13 Datasets V8

- **(test)** `test_validate_accepts_known_shapes` : `{prompt,response}`,
  `{instruction,output}`, `{messages}` acceptés. `test_invalid_json_line`,
  `test_missing_fields`, `test_too_small`, `test_traversal_blocked` : tout le
  reste refusé **avant** tout job.
- **(refaire)** Place `exemples.jsonl` sous `data/datasets/`, puis :

```bash
curl -X POST http://127.0.0.1:8001/api/datasets \
  -H "Content-Type: application/json" -d '{"name":"exemples","path":"exemples.jsonl"}'
```

- **(voir)** Un `Dataset` avec `rows` et `status:"valid"`.
- **(erreur)** Une ligne sans `response`/`output`/`messages` → refus 400.
- **(normal ?)** Le dataset apparaît dans le panneau Adaptation.

### B.14 Training — dry-run

- **(test)** `test_build_runner_argv_is_a_list_no_shell` : la commande du runner
  est une **liste d'arguments**, jamais une chaîne shell.
  `test_create_job_rejects_empty_base_model` : base_model vide refusé.
  `test_run_job_dry_run` : sans `TRAIN_RUNNER`, le job passe en `dry_run` et **ne
  crée aucune version**. `test_run_job_success_creates_version` (runner mocké) :
  succès → version candidate. `test_run_job_failure_keeps_baseline` : échec →
  baseline intact. `test_cancel_job` : annulation propre.
- **(refaire)** Panneau Adaptation → **Lancer** (avec `dataset_id` et
  `base_model`), ou :

```bash
curl -X POST http://127.0.0.1:8001/api/train \
  -H "Content-Type: application/json" \
  -d '{"dataset_id":1,"base_model":"qwen2.5:7b","method":"lora"}'
curl http://127.0.0.1:8001/api/train/1
```

- **(voir)** Statut `dry_run` ; le `log_tail` montre la commande qui *serait*
  exécutée. Aucun process d'entraînement n'est lancé.
- **(erreur)** Oublier `base_model` (et `TRAIN_BASE_MODEL` vide) → refus 400.
- **(normal ?)** En dry-run, **aucune version** n'est créée — c'est attendu.

### B.15 Promotion registry & `serving_status`

- **(test)** `test_ensure_baseline_is_active` : un baseline existe et est actif.
  `test_promote_refused_without_eval` / `test_promote_refused_when_not_better` :
  promotion **refusée** sans éval ou si le candidat ne bat pas le baseline (409).
  `test_promote_succeeds_when_better` : promotion acceptée si meilleur.
  `test_rollback_restores_baseline` : rollback restaure le baseline.
  `test_serving_status_is_honest` et `test_promotion_does_not_make_candidate_served`
  : **une version promue reste `not_served`**.
- **(refaire)** Panneau Adaptation → table **Versions de modèle** ; bouton
  **Promouvoir (registry)** / **Rollback**. Ou
  `curl http://127.0.0.1:8001/api/models/versions`.
- **(voir)** Le baseline = `served_as_base` ; un candidat = `not_served`, même
  après promotion (où il devient `Actif (registry)`).
- **(erreur)** Croire que « Promouvoir » fait servir l'adapter par le gateway.
  **Non.** Le gateway sert toujours le modèle de base en V8.
- **(normal ?)** Après promotion : `active = true` **et** `serving_status =
  not_served` pour le candidat.

> **Exemple-clé.** Test automatisé `test_promotion_does_not_make_candidate_served`
> → scénario formation : « Promouvoir une version adaptée ne veut pas dire qu'elle
> est servie par le gateway. Après promotion, vérifie que la version est **active
> côté registry**, mais que `serving_status` reste **`not_served`**. »

---

## C. Exercices pratiques inspirés des tests

Chaque exercice = un test traduit en manip concrète. Fais-les dans l'ordre.

1. **Inventaire honnête** (`test_load_not_installed_refused_no_http`) : tente de
   charger un modèle qui n'existe pas via `curl` `POST /api/actions/load` avec
   `{"model":"ghost:404"}`. Attendu : **400**, et le **Journal d'actions**
   montre un `refused`. Leçon : le cockpit n'invente jamais un modèle.

2. **Rôle persistant** (`test_assignment_reloaded_by_fresh_service`) : assigne
   `chat` à un modèle, **recharge** la page. Attendu : le choix tient. Vérifie
   `data/roles.json`.

3. **Routage par rôle** (`test_chat_completions_routed_by_role`) : appelle le
   gateway avec `model:"chat"`. Attendu : `x_cockpit_route.model` = ton modèle
   assigné.

4. **Une requête, une ligne** (`test_chat_produces_exactly_one_log`) : note le
   nombre de lignes dans `/api/logs`, fais **un** appel gateway, recompte.
   Attendu : +1 exactement.

5. **PII off** (`test_prompt_not_stored_by_default`) : après un appel, vérifie
   que `/api/logs` ne contient **aucun** champ `prompt`. Leçon : pas de PII par
   défaut.

6. **Comparer 2 modèles** (`test_run_two_models_one_ok_one_error`) : lance
   `summary` sur deux modèles, dont un faux. Attendu : un `ok`, un `error`, run
   complété. Lis le scoreboard.

7. **RAG honnête** (`test_answer_empty_store_is_honest`) : pose une question RAG
   **avant** d'ingérer quoi que ce soit. Attendu : « Aucune source ». Puis ingère
   un document et repose la question. Attendu : réponse + sources.

8. **RAG vs non-RAG** (`test_eval_with_rag_augments_and_tags_role`) : lance
   `/api/rag/eval` deux fois (`with_rag` false puis true). Attendu : deux lignes
   `chat` vs `chat+rag` au scoreboard.

9. **Dataset strict** (`test_missing_fields`) : crée un `.jsonl` avec une ligne
   `{"prompt":"x"}` (sans réponse). Attendu : **400** à l'ingestion.

10. **Dry-run sûr** (`test_run_job_dry_run`) : lance un job sans `TRAIN_RUNNER`.
    Attendu : statut `dry_run`, **zéro** version créée, **zéro** process
    d'entraînement (`pgrep -af peft` doit être vide).

11. **Promotion gatée** (`test_promote_refused_when_not_better`) : tente de
    promouvoir un candidat dont l'éval ne bat pas le baseline. Attendu : **409**.

12. **Promu ≠ servi** (`test_promotion_does_not_make_candidate_served`) : après
    une promotion réussie, vérifie `serving_status` = `not_served` sur le
    candidat. Leçon : la promotion est une décision de registry, pas de serving.

---

## D. Checklist fonctionnelle LLM Cockpit V8

Coche au fur et à mesure. Si une case échoue, va voir `TROUBLESHOOTING.md`.

**Démarrage**
- [ ] L'app démarre sur `127.0.0.1:8001` (`uvicorn`).
- [ ] La page Inventaire s'affiche, header **V8**, nav Inventaire/Dashboard.

**Inventaire & providers**
- [ ] Le provider **Ollama** est `joignable`, capacités visibles.
- [ ] La table des modèles liste tes modèles (cohérent avec `ollama list`).
- [ ] Charger puis décharger un modèle change son **État**.

**Rôles**
- [ ] Les 7 rôles sont présents ; au moins **`chat`** est assignable.
- [ ] L'assignation **persiste** après rechargement.
- [ ] Tester un rôle assigné produit une ligne `ok` au Journal d'actions.

**Gateway**
- [ ] `/v1/chat/completions` avec `model:"chat"` renvoie une réponse OpenAI.
- [ ] `x_cockpit_route` indique le bon provider/modèle.
- [ ] `/v1/models` liste modèles **et** alias `role:*`.
- [ ] Un rôle non assigné renvoie une **erreur OpenAI 400** (pas un plantage).

**Observabilité**
- [ ] Après des appels gateway, `/api/logs` a une ligne par appel.
- [ ] Aucun champ `prompt` exposé.
- [ ] Le dashboard montre total, p50/p95, répartitions.

**Évaluations & scoreboard**
- [ ] Lancer une éval (`summary`) produit un run.
- [ ] Le scoreboard agrège par (rôle, modèle).
- [ ] Un modèle absent donne un cas `error` sans casser le run.

**RAG**
- [ ] Ingestion d'un `.md` → document avec chunks + dimension.
- [ ] Une question renvoie une réponse **avec sources** citées.
- [ ] Sans document, la réponse dit honnêtement « pas de source ».
- [ ] RAG vs non-RAG apparaissent **distincts** au scoreboard.

**Adaptation**
- [ ] Un dataset valide est accepté ; un invalide est refusé.
- [ ] En dry-run, un job passe en `dry_run`, **aucune** version créée, **aucun**
  entraînement lancé.
- [ ] Le baseline existe et est `served_as_base`.
- [ ] Un candidat est `not_served`, **même après promotion**.
- [ ] Promotion non justifiée par les évals → refus (409).

---

## E. Validation technique : `uv run pytest`

Avant ou après ta validation visuelle, lance la suite complète :

```bash
cd /home/gear-code/02_projects/llm-cockpit/llm-cockpit-v0
uv run ruff check .
uv run pytest
```

Tu dois voir quelque chose comme `134 passed`. **Ce passage au vert confirme la
santé complète de la logique du cockpit** (inventaire, contrôle, rôles, registry,
gateway, logs, évals, RAG, adaptation) sur transport mocké, **sans** dépendre
d'un modèle réel.

> **Mais** `pytest` ne remplace **pas** un test visuel manuel de l'interface :
> il ne vérifie ni le rendu HTML/CSS, ni l'enchaînement HTMX des boutons, ni le
> comportement avec ton **vrai** Ollama et tes **vrais** modèles. Fais donc
> **les deux** : `pytest` pour la logique, la **Checklist D** pour l'interface
> réelle.

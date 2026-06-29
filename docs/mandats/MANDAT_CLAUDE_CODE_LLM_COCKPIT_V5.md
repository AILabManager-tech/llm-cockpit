# MANDAT CLAUDE CODE — LLM COCKPIT V5

```text
STATUT : DRAFT — NE PAS EXÉCUTER SANS VALIDATION HUMAINE.
Ce mandat dépend de l'état réel produit par la phase précédente.
```

> DRAFT structuré, **non verrouillé**. Détails « à figer » dépendants de l'état réel de V4.
> Précondition : V4 terminée, taguée `v4`, `ruff` + `pytest` verts.

---

## MISSION

Mesurer ce qui se passe réellement : logger les requêtes du gateway (latence, modèle, provider, application appelante, succès/erreur, tokens si disponibles) et fournir un **dashboard d'activité**. Première persistance en base : **SQLite**.

---

## MÉTHODE D'EXÉCUTION (terminal)

1. `git checkout -b v5` depuis `v4`. Baseline verte.
2. `app/db/schema.sql` + `app/db/store.py` → middleware/log du gateway → `app/services/stats.py` → `app/main.py` (routes + dashboard) → templates. Tests en parallèle.
3. ruff + pytest verts. README. `git tag v5`.

---

## PÉRIMÈTRE

Racine `llm-cockpit-v0`. Branche `v5`. Inspecter avant de modifier.

---

## CONTEXTE GLOBAL GELÉ

| Phase | Rôle |
|---|---|
| V0 inventaire | V1 contrôle | V2 rôles | V3 registry | V4 gateway |
| **V5** | logs et observabilité ← **TU ES ICI** |
| V6 evals | V7 RAG | V8 LoRA |

---

## ACQUIS V4 — NE PAS RÉÉCRIRE

Gateway `/v1/chat/completions` + routing par rôle, multi-provider. Journal d'actions V1 (`data/actions.jsonl`) **reste** pour les actions de contrôle. V5 ajoute la **persistance SQLite** pour les requêtes gateway (c'est ici, et pas avant, que SQLite entre dans le projet).

---

## INTERDICTIONS ABSOLUES POUR V5

- Pas d'évaluations / scoreboard (V6) : V5 observe le trafic réel, il ne crée pas de jeux de tests.
- Pas de RAG, pas de training.
- Pas de stack d'observabilité externe (pas de Prometheus/Grafana/OpenTelemetry collector) : SQLite local + dashboard HTMX, point. Local-first.
- Ne pas exposer de PII : ne pas logger le contenu intégral des prompts par défaut (au minimum tronquer/désactivable ; décision au mandat d'exécution).
- Ne pas réécrire le journal d'actions V1 en SQLite (deux mécanismes distincts assumés, ou migration décidée explicitement).
- Ne pas préparer V6+.

---

## STACK / DÉPENDANCES

`sqlite3` (stdlib) privilégié. Migration via script idempotent `app/db/schema.sql`. Pas d'ORM lourd sauf justification.

---

## SÉCURITÉ ET INVARIANTS

Bind `127.0.0.1`. `data/cockpit.db` gitignored. Aucune fuite de PII non maîtrisée dans les logs. Le logging ne doit jamais faire échouer une requête gateway (best-effort, erreurs de log avalées proprement). Écritures concurrentes SQLite gérées (WAL ou sérialisation simple, à décider).

---

## FONCTIONNALITÉ V5 ATTENDUE

1. Chaque requête gateway loggée : ts, route, app appelante (si connue, ex. en-tête), rôle, provider, modèle, latence, statut, tokens si disponibles.
2. Endpoint de consultation des logs (filtrable).
3. Stats agrégées : volume, taux d'erreur, p50/p95 latence, répartition par modèle/provider/app.
4. Dashboard `/dashboard` (HTMX) : activité en temps quasi réel.

---

## DIRECTION D'ARCHITECTURE (esquisse indicative, à figer)

- `app/db/store.py` : connexion SQLite, init schéma, insert/query. Seul point d'accès DB.
- Middleware ou hook dans le gateway V4 qui mesure la latence et écrit un `request_log` après réponse.
- `app/services/stats.py` : agrégations (fenêtre temporelle, percentiles).
- App appelante identifiée via un en-tête convenu (ex. `X-Cockpit-App`) ou `user-agent` — à décider.
- Schémas indicatifs : `RequestLog`, `StatsSummary`. **Champs exacts à confirmer** contre le format réel des réponses gateway V4 (présence/absence de `usage`/tokens selon provider).

---

## ENDPOINTS (proposés)

```
GET /api/logs           ?limit&model&provider&app&status  → list[RequestLog]
GET /api/stats          ?window                           → StatsSummary
GET /dashboard          → page dashboard
GET /partials/dashboard → fragment HTMX (rafraîchi périodiquement)
```

---

## STRUCTURE DE FICHIERS (delta proposé)

Nouveaux : `app/db/__init__.py`, `app/db/schema.sql`, `app/db/store.py`, `app/services/logging_mw.py`, `app/services/stats.py`, `app/templates/dashboard.html`, `app/templates/partials/dashboard.html`, `tests/test_db.py`, `tests/test_logging.py`, `tests/test_stats.py`. Étendus : gateway, `config.py`, `schemas.py`, `main.py`.

---

## CONFIGURATION (proposé)

```
DB_PATH      = env("DB_PATH", DATA_DIR + "/cockpit.db")
LOG_PROMPTS  = env_bool("LOG_PROMPTS", False)   # ne pas stocker le contenu par défaut
```

---

## CAS LIMITES

Tokens absents (provider qui ne les renvoie pas) → `None`, pas d'invention. DB verrouillée → log best-effort, requête gateway non impactée. DB absente → créée au démarrage. Fenêtre stats vide → zéros francs, pas d'erreur.

---

## TESTS ATTENDUS (direction)

Une requête gateway produit exactement une ligne `request_log` ; stats calculées (p50/p95, taux d'erreur) sur données connues ; tokens absents → `None` ; échec de log n'échoue pas la requête ; V0–V4 verts ; ruff + pytest verts.

---

## DEFINITION OF DONE

ruff + pytest verts ; trafic gateway loggé en SQLite ; dashboard affiche volume/latence/erreurs par modèle/provider/app ; pas de PII non maîtrisée ; pas d'évals/RAG/training ; aucun fichier de phase future ; `git tag v5`.

---

## README ATTENDU (bloc invariants)

```text
V5 observe le trafic réel du gateway via SQLite local.
V5 ne crée aucun jeu de tests (évaluations = V6).
V5 ne logge pas le contenu des prompts par défaut.
V5 reste local-first : aucun collecteur externe.
```

---

## POINTS À FIGER AU MANDAT D'EXÉCUTION (dépend de V4)

- Quels champs `usage`/tokens le gateway V4 expose réellement selon les providers branchés.
- Mécanisme d'identification de l'app appelante (en-tête vs user-agent).
- Sort du journal d'actions V1 : cohabitation JSONL/SQLite ou migration.
- Politique exacte de troncature/anonymisation si `LOG_PROMPTS` est activé.

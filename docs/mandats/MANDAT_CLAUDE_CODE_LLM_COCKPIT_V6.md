# MANDAT CLAUDE CODE — LLM COCKPIT V6

```text
STATUT : DRAFT — NE PAS EXÉCUTER SANS VALIDATION HUMAINE.
Ce mandat dépend de l'état réel produit par la phase précédente.
```

> DRAFT structuré, **non verrouillé**. Détails « à figer » dépendants de l'état réel de V5.
> Précondition : V5 terminée, taguée `v5`, `ruff` + `pytest` verts.

---

## MISSION

Arrêter de choisir les modèles « au feeling ». Créer des **jeux de tests locaux**, comparer deux modèles sur les mêmes prompts, mesurer latence / qualité / respect du format / erreurs, produire un **scoreboard par rôle**, conserver les résultats. C'est le socle de preuve dont dépendent V7 (RAG mesuré) et V8 (fine-tuning justifié).

---

## MÉTHODE D'EXÉCUTION (terminal)

1. `git checkout -b v6` depuis `v5`. Baseline verte.
2. `app/evals/checks.py` → `app/evals/runner.py` → `app/evals/scoreboard.py` → tables SQLite eval → `app/main.py` → templates → suites d'exemple `data/evals/*.yaml`. Tests en parallèle.
3. ruff + pytest verts. README. `git tag v6`.

---

## PÉRIMÈTRE

Racine `llm-cockpit-v0`. Branche `v6`. Inspecter avant de modifier.

---

## CONTEXTE GLOBAL GELÉ

| Phase | Rôle |
|---|---|
| V0..V4 (inventaire→gateway) | V5 logs |
| **V6** | évaluations comparatives ← **TU ES ICI** |
| V7 RAG | V8 LoRA |

---

## ACQUIS V5 — NE PAS RÉÉCRIRE

Gateway routé, observabilité SQLite (`request_log`, stats), dashboard. V6 réutilise le gateway (V4) pour exécuter les évals **à travers le routage réel** et SQLite (V5) pour stocker les résultats. Le harness V6 sera **réutilisé tel quel** par V7 (RAG vs non-RAG) et V8 (adapté vs baseline).

---

## INTERDICTIONS ABSOLUES POUR V6

- Pas de RAG (V7), pas de training (V8).
- Pas de juge LLM opaque non vérifiable comme seule mesure : les checks doivent être **déterministes et inspectables** d'abord (format JSON, présence, longueur, latence) ; un éventuel scoring LLM reste optionnel, traçable, jamais l'unique vérité.
- Pas d'eval distante / dataset téléchargé : suites **locales**.
- Pas de queue externe : un run d'eval est un job **in-process** (asyncio), annulable.
- Ne pas préparer V7+.

---

## STACK / DÉPENDANCES

`pyyaml` autorisé (suites d'eval en YAML). Réutilise SQLite V5.

---

## SÉCURITÉ ET INVARIANTS

Bind `127.0.0.1`. Les évals n'exécutent jamais de code arbitraire issu des sorties de modèle (pas d'`exec` de code généré). Résultats stockés localement. Un run long ne bloque pas l'UI (job in-process + statut).

---

## FONCTIONNALITÉ V6 ATTENDUE

1. Définir une suite d'eval locale (cas = prompt + checks + rôle/attendu).
2. Lancer une suite sur N modèles → mesures par cas.
3. Mesures : passé/échoué, score, latence, respect du format, erreurs.
4. Scoreboard par rôle : quel modèle est meilleur pour quel usage, avec preuves.
5. Conserver runs et résultats (SQLite). UI scoreboard.

Exemples de suites : code Python, JSON strict, résumé, extraction, raisonnement, réponse métier, prompt RAG (préfiguration V7).

---

## DIRECTION D'ARCHITECTURE (esquisse indicative, à figer)

- `app/evals/checks.py` : checks déterministes nommés (`json_valid`, `contains:x`, `regex:…`, `latency_lt:ms`, `non_empty`, …). Extensible mais inspectable.
- `app/evals/runner.py` : exécute une suite via le gateway V4 (donc le vrai routage), collecte `EvalResult`.
- `app/evals/scoreboard.py` : agrège par (rôle, modèle) → `ScoreboardRow`.
- Schémas indicatifs : `EvalCase`, `EvalResult`, `EvalRun`, `ScoreboardRow`. **Champs/forme des checks à confirmer** contre la forme réelle des réponses gateway V4 et du logging V5.

---

## ENDPOINTS (proposés)

```
POST /api/evals/run       body {suite, models[]}  → EvalRun (id)
GET  /api/evals           → runs récents
GET  /api/evals/{id}      → détail d'un run
GET  /api/scoreboard      ?role  → scoreboard agrégé
GET  /partials/scoreboard → fragment HTMX
```

---

## STRUCTURE DE FICHIERS (delta proposé)

Nouveaux : `app/evals/__init__.py`, `app/evals/checks.py`, `app/evals/runner.py`, `app/evals/scoreboard.py`, `app/templates/partials/scoreboard.html`, `tests/test_checks.py`, `tests/test_evals.py`, `tests/test_scoreboard.py`, suites `data/evals/*.yaml`. Étendus : `db/schema.sql` (tables eval), `schemas.py`, `config.py`, `main.py`.

---

## CONFIGURATION (proposé)

```
EVALS_DIR = env("EVALS_DIR", DATA_DIR + "/evals")
```

---

## CAS LIMITES

Modèle injoignable pendant un run → cas marqué `error`, run continue. Suite invalide (YAML cassé) → erreur claire avant run. Check inconnu → erreur de validation, pas d'exécution. Run annulé → statut cohérent, résultats partiels conservés.

---

## TESTS ATTENDUS (direction)

Chaque check déterministe testé isolément (`json_valid`, `contains`, `latency_lt`…) ; un run sur 2 modèles (transport/gateway mocké) produit des `EvalResult` corrects ; scoreboard agrège correctement ; modèle down → cas `error` sans casser le run ; V0–V5 verts ; ruff + pytest verts.

---

## DEFINITION OF DONE

ruff + pytest verts ; comparaison de ≥ 2 modèles sur une suite locale ; scoreboard par rôle avec preuves ; résultats persistés ; checks déterministes et inspectables ; aucun RAG/training ; aucun fichier de phase future ; `git tag v6`.

---

## README ATTENDU (bloc invariants)

```text
V6 compare les modèles sur des suites locales, avec preuves.
V6 mesure d'abord avec des checks déterministes et inspectables.
V6 n'exécute jamais le code généré par un modèle.
V6 ne fait ni RAG ni fine-tuning ; il fournit le socle de preuve.
```

---

## POINTS À FIGER AU MANDAT D'EXÉCUTION (dépend de V5)

- Forme réelle des réponses gateway V4 (tokens, finish_reason) exploitables comme mesures.
- Réutilisation directe des tables/logs V5 vs tables eval dédiées.
- Catalogue final des checks selon les rôles réellement utilisés.
- Faut-il un scoring LLM optionnel et comment le tracer.

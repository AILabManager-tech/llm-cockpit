# MANDAT CLAUDE CODE — LLM COCKPIT V8

```text
STATUT : DRAFT — NE PAS EXÉCUTER SANS VALIDATION HUMAINE.
Ce mandat dépend de l'état réel produit par la phase précédente.
```

> DRAFT structuré, **non verrouillé**. Détails « à figer » dépendants de l'état réel de V7.
> Précondition : V7 terminée, taguée `v7`, `ruff` + `pytest` verts, **et un socle d'évaluation V6 réellement utilisé**.

---

## MISSION

Orchestrer une **adaptation de modèle contrôlée et mesurée** — seulement quand le socle d'évaluation existe. Préparer un dataset validé, lancer un job LoRA/QLoRA, comparer le modèle adapté au **baseline**, versionner le résultat, **rollback** si pire, **promouvoir** uniquement si les évals le justifient. Le cockpit n'est pas un laboratoire d'entraînement : il orchestre et mesure.

---

## MÉTHODE D'EXÉCUTION (terminal)

1. `git checkout -b v8` depuis `v7`. Baseline verte. **Vérifier** qu'un socle d'eval V6 est réellement exploité (sinon, le fine-tuning est prématuré — arrêter).
2. `app/training/dataset.py` → `app/training/runner.py` → `app/training/job.py` → `app/training/registry.py` (versions + promote/rollback) → `app/main.py` → templates. Tests en parallèle.
3. ruff + pytest verts. README. `git tag v8`.

---

## PÉRIMÈTRE

Racine `llm-cockpit-v0`. Branche `v8`. Inspecter avant de modifier.

---

## CONTEXTE GLOBAL GELÉ

| Phase | Rôle |
|---|---|
| V0..V6 | V7 RAG mesuré |
| **V8** | adaptation LoRA/QLoRA orchestrée, comparée au baseline ← **TU ES ICI** |

---

## ACQUIS V7 — NE PAS RÉÉCRIRE

Harness d'eval V6 (preuve), RAG mesuré V7, gateway/registry/observabilité. V8 **réutilise le harness V6** pour comparer adapté vs baseline. Aucune nouvelle infra d'évaluation : la décision promote/rollback s'appuie sur les évals existantes.

---

## INTERDICTIONS ABSOLUES POUR V8 (HORS SCOPE STRICT)

- **Entraînement fondationnel** : interdit.
- **Recherche modèle avancée** : interdit.
- **Plateforme d'entraînement complète** : interdit. V8 orchestre un job d'adaptation, il ne devient pas une plateforme ML.
- Pas d'entraînement **dans le process web** : un job lance un **sous-process runner allowlisté** (argv en liste, jamais `shell=True`), in-process pour la supervision uniquement.
- Pas de promotion automatique sans évals favorables : la promotion est **gated par la preuve V6**.
- Pas de téléchargement de datasets distants non validés.

---

## STACK / DÉPENDANCES

`peft`, `transformers`, `datasets`, `bitsandbytes` (QLoRA) — **lourds**, donc isolés derrière un **runner externe allowlisté** (`TRAIN_RUNNER`). Le cockpit reste léger ; il appelle le runner, capture les logs, mesure. Si `TRAIN_RUNNER` n'est pas configuré → mode **dry-run** uniquement (prépare/valide, ne lance pas).

---

## SÉCURITÉ ET INVARIANTS

Bind `127.0.0.1`. Sous-process uniquement via allowlist d'exécutables (`python -m <runner>`), argv liste, jamais de string shell, jamais `systemctl`. Datasets et adaptateurs locaux (`data/`), gitignored, jamais de PII committée. Un job échoué/annulé laisse le baseline intact (non destructif). Le baseline n'est jamais écrasé ; on **ajoute** une version.

---

## FONCTIONNALITÉ V8 ATTENDUE

1. Préparer + valider un dataset (format, taille, intégrité) → `Dataset`.
2. Lancer un job LoRA/QLoRA (sous-process runner) avec statut/log suivis.
3. Enregistrer le résultat comme **version de modèle** (adapter sur disque).
4. Comparer adapté vs baseline via le harness V6.
5. **Promouvoir** seulement si les évals le justifient ; **rollback** sinon.
6. UI : panneau training (datasets, jobs, versions, comparaison, promote/rollback).

---

## DIRECTION D'ARCHITECTURE (esquisse indicative, à figer)

- `dataset.py` (validation), `runner.py` (sous-process allowlisté + capture logs), `job.py` (cycle de vie in-process : pending→running→done/failed/cancelled), `registry.py` (`ModelVersion`, baseline, promote/rollback, lien `eval_run_id`).
- Schémas indicatifs : `Dataset`, `TrainJob`, `ModelVersion`. **Forme exacte (méthode lora/qlora, hyperparamètres, intégration Ollama du modèle adapté) à confirmer** au mandat d'exécution, selon l'outillage réel disponible sur la machine.

---

## ENDPOINTS (proposés)

```
POST /api/datasets               body {name, path}     → Dataset (validé)
GET  /api/datasets               → datasets
POST /api/train                  body {dataset_id, base_model, method} → TrainJob
GET  /api/train/{id}             → statut + log_tail
POST /api/train/{id}/cancel      → annule (non destructif)
GET  /api/models/versions        → versions (dont baseline)
POST /api/models/promote         body {version_id}     → promu si évals favorables
POST /api/models/rollback        body {version_id}     → retour baseline
GET  /partials/training          → fragment HTMX
```

---

## STRUCTURE DE FICHIERS (delta proposé)

Nouveaux : `app/training/__init__.py`, `app/training/{dataset,runner,job,registry}.py`, `app/templates/partials/training_panel.html`, `tests/test_dataset.py`, `tests/test_train_job.py`, `tests/test_model_registry.py`. Étendus : `db/schema.sql` (datasets/jobs/versions), `schemas.py`, `config.py`, `main.py`. Adaptateurs sous `data/adapters/<id>/`.

---

## CONFIGURATION (proposé)

```
ADAPTERS_DIR    = env("ADAPTERS_DIR", DATA_DIR + "/adapters")
TRAIN_BASE_MODEL= env("TRAIN_BASE_MODEL", "")   # vide → refuse, jamais d'invention
TRAIN_RUNNER    = env("TRAIN_RUNNER", "")        # exécutable allowlisté ; vide → dry-run only
```

---

## CAS LIMITES

`TRAIN_RUNNER` absent → dry-run (validation seule), jamais d'entraînement fantôme. Dataset invalide → refus avant job. Job échoué → statut `failed`, baseline intact, logs conservés. Promotion sans `eval_run_id` favorable → refus. Annulation → `cancelled`, artefacts partiels nettoyés ou marqués.

---

## TESTS ATTENDUS (direction)

Validation de dataset (cas valides/invalides) ; cycle de vie d'un job (runner mocké) sans toucher au vrai entraînement ; promote refusé si évals défavorables ; rollback restaure le baseline ; sous-process appelé en argv liste (jamais shell) ; dry-run si pas de runner ; V0–V7 verts ; ruff + pytest verts.

---

## DEFINITION OF DONE

ruff + pytest verts ; dataset validé → job LoRA/QLoRA orchestré (ou dry-run propre) → version enregistrée → comparée au baseline via V6 → promote/rollback **gated par la preuve** ; baseline jamais écrasé ; aucun entraînement dans le process web ni `shell=True` ; le cockpit reste un orchestrateur, pas une plateforme d'entraînement ; aucun fichier hors scope ; `git tag v8`.

---

## README ATTENDU (bloc invariants)

```text
V8 orchestre une adaptation LoRA/QLoRA, mesurée contre le baseline.
V8 ne fait pas d'entraînement fondationnel ni de plateforme ML.
V8 n'entraîne pas dans le process web (runner externe allowlisté).
V8 ne promeut un modèle que si les évals le justifient ; sinon rollback.
```

---

## POINTS À FIGER AU MANDAT D'EXÉCUTION (dépend de V7 et du matériel réel)

- Outillage d'entraînement réellement installé (peft/transformers/bitsandbytes) et VRAM disponible (RTX 5080 16 Go) → faisabilité QLoRA.
- Comment servir le modèle adapté derrière le gateway (export GGUF + import Ollama, ou serveur dédié).
- Format exact du dataset et des hyperparamètres selon le runner choisi.
- Critère de promotion chiffré (seuil de gain sur le scoreboard V6) à trancher avec un humain.

# MANDAT CLAUDE CODE — LLM COCKPIT V7

```text
STATUT : DRAFT — NE PAS EXÉCUTER SANS VALIDATION HUMAINE.
Ce mandat dépend de l'état réel produit par la phase précédente.
```

> DRAFT structuré, **non verrouillé**. Détails « à figer » dépendants de l'état réel de V6.
> Précondition : V6 terminée, taguée `v6`, `ruff` + `pytest` verts.

---

## MISSION

Connecter les modèles à des **données locales** et **vérifier** que ça améliore vraiment les réponses : ingestion de documents, embeddings, vector DB locale, retrieval, génération augmentée, et **comparaison RAG vs non-RAG via le harness V6**. Le RAG n'est pas supposé meilleur par magie — il doit être mesuré.

---

## MÉTHODE D'EXÉCUTION (terminal)

1. `git checkout -b v7` depuis `v6`. Baseline verte.
2. `app/rag/ingest.py` → `app/rag/embed.py` → `app/rag/store.py` → `app/rag/query.py` → `app/rag/eval_bridge.py` (réutilise V6) → `app/main.py` → templates. Tests en parallèle.
3. ruff + pytest verts. README. `git tag v7`.

---

## PÉRIMÈTRE

Racine `llm-cockpit-v0`. Branche `v7`. Inspecter avant de modifier.

---

## CONTEXTE GLOBAL GELÉ

| Phase | Rôle |
|---|---|
| V0..V5 | V6 évaluations |
| **V7** | RAG local mesuré ← **TU ES ICI** |
| V8 LoRA |

---

## ACQUIS V6 — NE PAS RÉÉCRIRE

Harness d'eval (suites locales, checks déterministes, scoreboard, runs persistés). V7 **réutilise ce harness** pour comparer RAG vs non-RAG : aucune nouvelle infra d'évaluation, on branche le RAG dedans. Embeddings via Ollama (`/api/embeddings`).

---

## INTERDICTIONS ABSOLUES POUR V7

- Pas de fine-tuning (V8).
- Pas de vector DB lourde/serveur externe (pas de Pinecone/Weaviate/Qdrant serveur) : **store vectoriel local** (ex. `sqlite-vec` sur la base existante). Local-first.
- Pas de framework RAG opaque imposant son orchestration (pas d'adoption aveugle d'un gros framework) : ingestion → embed → store → retrieve → generate, étapes explicites et testables.
- Ne pas prétendre que le RAG améliore sans **mesure comparative** (DoD l'exige).
- Ne pas préparer V8.

---

## STACK / DÉPENDANCES

`sqlite-vec` (extension vectorielle sur SQLite existant) ; embeddings via Ollama `POST /api/embeddings` (pas de lib d'embedding lourde) ; `pypdf` autorisé pour PDF, stdlib pour txt/md.

---

## SÉCURITÉ ET INVARIANTS

Bind `127.0.0.1`. Documents ingérés restent locaux (`data/rag/`), gitignored, jamais committés (PII). Réponses RAG **citent leurs sources** (doc + chunk). Pas d'ingestion hors du dossier autorisé. Pas d'exécution de contenu de document.

---

## FONCTIONNALITÉ V7 ATTENDUE

1. Ingestion de documents locaux (txt/md/pdf) → chunking → embeddings → store.
2. Retrieval : top-K chunks pertinents pour une requête.
3. Génération augmentée : réponse avec sources citées, via le gateway/rôles existants.
4. Comparaison **RAG vs non-RAG** sur une suite d'eval (harness V6).
5. UI : panneau RAG (documents ingérés, requête, réponse + sources).

---

## DIRECTION D'ARCHITECTURE (esquisse indicative, à figer)

- `ingest.py` (parse + chunk), `embed.py` (Ollama embeddings), `store.py` (sqlite-vec, tables `rag_document`/`rag_chunk` + vecteurs), `query.py` (retrieve + prompt augmenté + génération via gateway V4), `eval_bridge.py` (branche RAG/non-RAG dans le runner V6).
- Schémas indicatifs : `RagDocument`, `RagChunk`, `RagSource`, `RagAnswer`. **Forme exacte (taille de chunk, métriques de similarité) à confirmer** au mandat d'exécution.

---

## ENDPOINTS (proposés)

```
POST   /api/rag/ingest          body {path|upload}     → RagDocument
GET    /api/rag/documents       → docs ingérés
DELETE /api/rag/documents/{id}  → retirer un doc
POST   /api/rag/query           body {query, role?}    → RagAnswer (avec sources)
POST   /api/rag/eval            body {suite, with_rag} → EvalRun (réutilise V6)
GET    /partials/rag            → fragment HTMX
```

---

## STRUCTURE DE FICHIERS (delta proposé)

Nouveaux : `app/rag/__init__.py`, `app/rag/{ingest,embed,store,query,eval_bridge}.py`, `app/templates/partials/rag_panel.html`, `tests/test_rag_ingest.py`, `tests/test_rag_query.py`, `tests/test_rag_eval.py`. Étendus : `db/schema.sql`, `schemas.py`, `config.py`, `main.py`.

---

## CONFIGURATION (proposé)

```
RAG_DOCS_DIR   = env("RAG_DOCS_DIR", DATA_DIR + "/rag/docs")
RAG_EMBED_MODEL= env("RAG_EMBED_MODEL", "nomic-embed-text")
RAG_TOP_K      = int(env("RAG_TOP_K", "4"))
```

`RAG_EMBED_MODEL` doit être réellement installé (sinon erreur claire, jamais d'invention).

---

## CAS LIMITES

Modèle d'embedding absent → erreur claire, pas de fallback inventé. Document non parsable → ignoré avec warning, pas de crash global. Aucun chunk pertinent → réponse honnête « pas de source », pas d'hallucination forcée. Store vide → retrieval vide géré.

---

## TESTS ATTENDUS (direction)

Chunking déterministe ; ingestion → store (embeddings mockés) ; retrieval top-K cohérent ; réponse RAG cite des sources réelles ; comparaison RAG vs non-RAG produit un `EvalRun` exploitable ; embedding model absent → erreur ; V0–V6 verts ; ruff + pytest verts.

---

## DEFINITION OF DONE

ruff + pytest verts ; ingestion + retrieval + génération augmentée fonctionnels avec sources ; comparaison RAG vs non-RAG **mesurée** via le harness V6 ; store vectoriel local ; aucun fine-tuning ; aucun fichier de phase future ; `git tag v7`.

---

## README ATTENDU (bloc invariants)

```text
V7 répond à partir de documents locaux, avec sources.
V7 mesure le RAG vs non-RAG ; il ne le suppose pas meilleur.
V7 garde un store vectoriel local (aucune base vectorielle serveur).
V7 ne fait aucun fine-tuning.
```

---

## POINTS À FIGER AU MANDAT D'EXÉCUTION (dépend de V6)

- Forme réelle du runner V6 pour y brancher RAG/non-RAG proprement.
- Choix de chunking (taille/overlap) et métrique de similarité selon les docs réels.
- Modèle d'embedding réellement disponible sur la machine cible.
- Format des suites d'eval RAG (réutilisation des checks V6).

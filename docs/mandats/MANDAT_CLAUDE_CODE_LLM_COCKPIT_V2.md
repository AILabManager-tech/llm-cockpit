# MANDAT CLAUDE CODE — LLM COCKPIT V2

```text
STATUT : DRAFT — NE PAS EXÉCUTER SANS VALIDATION HUMAINE.
Ce mandat dépend de l'état réel produit par la phase précédente.
```

> DRAFT structuré, **non verrouillé**. Les détails d'implémentation marqués « à figer » dépendent de l'état réel de V1 et seront tranchés au moment du mandat d'exécution, code sous les yeux.
> Précondition : V1 terminée, taguée `v1`, `ruff` + `pytest` verts.

---

## MISSION

Permettre de raisonner en **usages** plutôt qu'en noms de modèles : assigner un **rôle** à un modèle, changer le modèle par défaut d'un rôle, tester un modèle dans son rôle, et persister ces préférences localement. Couche additive sur V0+V1, même dépôt.

---

## MÉTHODE D'EXÉCUTION (terminal)

1. `git checkout -b v2` depuis `v1`. Baseline `pytest` vert avant de commencer.
2. Étendre `app/config.py` → `app/schemas.py` → `app/services/roles.py` → `app/main.py` → templates. Tests en parallèle.
3. `uv run ruff check .` + `uv run pytest` (V0/V1 restent verts). README. `git tag v2` au DoD.

---

## PÉRIMÈTRE

Racine `/home/gear-code/02_projects/llm-cockpit/llm-cockpit-v0`. Branche `v2`. Jamais de dossier voisin. Inspecter avant de modifier.

---

## CONTEXTE GLOBAL GELÉ

| Phase | Rôle |
|---|---|
| V0 | inventaire lecture seule |
| V1 | contrôle sécurisé minimal |
| **V2** | rôles et sélection de modèles ← **TU ES ICI** |
| V3 | registry multi-provider |
| V4 | gateway OpenAI-compatible |
| V5 | logs et observabilité |
| V6 | évaluations comparatives |
| V7 | RAG local mesuré |
| V8 | adaptation LoRA/QLoRA |

---

## ACQUIS V1 — NE PAS RÉÉCRIRE

Inventaire V0 (`ModelInfo`, fusion, `/api/models`), contrôle V1 (`load`/`unload`/`test`, allowlist, journal `data/actions.jsonl`), `OllamaAdapter` étendu. V2 **réutilise** la validation et le `test` de V1 pour « tester un modèle dans son rôle ».

---

## INTERDICTIONS ABSOLUES POUR V2

- Pas de multi-provider (ça, c'est V3) : V2 assigne des rôles à des modèles **Ollama** uniquement.
- Pas de gateway, pas de routing d'applications externes (V4).
- Pas de SQLite (préférences en **fichier JSON local**).
- Pas d'auto-sélection « intelligente » du meilleur modèle : V2 est une **préférence manuelle déclarée**, pas un optimiseur (l'optimisation par preuve, c'est V6).
- Ne pas préparer V3+ (pas de schéma provider, pas de dossier vide).

---

## STACK / DÉPENDANCES

Aucune nouvelle dépendance (`json` stdlib). Écriture atomique du fichier de préférences (tmp + `os.replace`).

---

## SÉCURITÉ ET INVARIANTS

Bind `127.0.0.1`. Assigner un rôle à un modèle **non installé** → refus clair. Persistance locale uniquement, écriture atomique, `data/` gitignored. Aucune action destructive.

---

## FONCTIONNALITÉ V2 ATTENDUE

1. Liste des rôles et de leur modèle assigné actuel.
2. Assigner / changer le modèle d'un rôle (parmi les modèles installés).
3. Tester un rôle = lancer le `test` V1 sur le modèle assigné au rôle.
4. Persistance dans un fichier JSON local, rechargé au démarrage.
5. UI : panneau « Rôles », sélection du modèle par rôle, bouton tester.

Rôles cibles (énumération à confirmer) : `chat`, `code`, `vision`, `embedding`, `fast`, `quality`, `experimental`.

---

## DIRECTION D'ARCHITECTURE (esquisse indicative, à figer au mandat d'exécution)

- Un service `app/services/roles.py` charge/sauvegarde `data/roles.json`, valide qu'un modèle assigné est installé, expose get/set.
- Réutiliser `inventory.list_models()` (V0) pour la validation et `actions.test` (V1) pour le test de rôle.
- Schéma indicatif : `Role(str, Enum)`, `RoleAssignment{role, provider, model, updated_at}`, `RoleConfig{assignments}`. **Noms et champs exacts à confirmer** contre la forme réelle des schémas V1.

---

## ENDPOINTS (proposés, à confirmer)

```
GET  /api/roles                 → état des assignations
PUT  /api/roles/{role}          body {model}  → change le modèle du rôle
POST /api/roles/{role}/test     → teste le modèle assigné (réutilise test V1)
GET  /partials/roles            → fragment HTMX
```

---

## STRUCTURE DE FICHIERS (delta proposé)

Nouveaux : `app/services/roles.py`, `app/templates/partials/roles_panel.html`, `tests/test_roles.py`.
Étendus : `app/config.py`, `app/schemas.py`, `app/main.py`, `app/templates/inventory.html`.
**Pas de dossier `roles/` top-level.** Pas de fichier de phase future.

---

## CONFIGURATION (proposé)

```
ROLES_CONFIG_PATH = env("ROLES_CONFIG_PATH", DATA_DIR + "/roles.json")
```

Rôles par défaut : non assignés au départ (jamais d'invention d'un modèle assigné).

---

## CAS LIMITES

Rôle inconnu → 400. Modèle non installé → refus. `roles.json` absent → état vide initialisé proprement. `roles.json` corrompu → erreur claire, ne pas écraser silencieusement.

---

## TESTS ATTENDUS (direction)

Assigner un rôle à un modèle installé → persisté et relu ; assigner un modèle non installé → refus ; tester un rôle → réutilise le chemin `test` V1 ; rôle inconnu → 400 ; V0/V1 restent verts ; ruff + pytest verts.

---

## DEFINITION OF DONE

ruff + pytest verts (V0/V1 inclus) ; rôles assignables/persistés ; test de rôle fonctionnel ; aucune SQLite, aucun multi-provider, aucun gateway ; aucun fichier de phase future ; `git tag v2`.

---

## README ATTENDU (bloc invariants)

```text
V2 raisonne en rôles, mais reste mono-provider (Ollama).
V2 ne route aucune application externe.
V2 n'optimise pas le choix de modèle ; il enregistre une préférence déclarée.
V2 n'introduit aucune base de données (préférences en JSON local).
```

---

## POINTS À FIGER AU MANDAT D'EXÉCUTION (dépend de l'état réel de V1)

- Forme exacte des schémas V1 réutilisés (`ActionResult`, signature de `test`).
- Faut-il un rôle `vision`/`embedding` si aucun modèle correspondant n'est installé (rôle déclarable mais non assigné ?).
- Emplacement final du fichier de préférences et stratégie de migration si le format change en V3.

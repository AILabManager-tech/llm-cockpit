# Formation — Interface LLM Cockpit V8 (index)

Documentation d'utilisation de l'interface web de **LLM Cockpit V8**. Tout est
local-first (`127.0.0.1`), aucune donnée ne sort de la machine.

Branche : `phase/v8` · Tag : `v8`.

---

## Par où commencer

| Tu es…                                  | Lis…                                              |
|-----------------------------------------|---------------------------------------------------|
| Nouveau, tu veux démarrer en 5 min      | [`QUICKSTART_INTERFACE.md`](QUICKSTART_INTERFACE.md) |
| Utilisateur, tu veux tout comprendre    | [`FORMATION_INTERFACE_LLM_COCKPIT_V8.md`](FORMATION_INTERFACE_LLM_COCKPIT_V8.md) |
| Tu veux valider que tout marche         | [`PARCOURS_VALIDATION_PAR_LES_TESTS.md`](PARCOURS_VALIDATION_PAR_LES_TESTS.md) |
| Opérateur, tu installes/configures      | [`GUIDE_ADMIN_CONFIGURATION.md`](GUIDE_ADMIN_CONFIGURATION.md) |
| Quelque chose ne marche pas             | [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)        |

---

## Contenu du dossier

```text
docs/formation/
├─ README.md                              # cet index
├─ QUICKSTART_INTERFACE.md                # démarrage express
├─ FORMATION_INTERFACE_LLM_COCKPIT_V8.md  # guide principal complet
├─ PARCOURS_VALIDATION_PAR_LES_TESTS.md   # tests → parcours + checklist
├─ GUIDE_ADMIN_CONFIGURATION.md           # variables, données, sécurité, runner
├─ TROUBLESHOOTING.md                     # dépannage
└─ screenshots/                           # captures réelles de l'interface
```

---

## Captures d'écran

Captures **réelles** (Chrome headless, Ollama actif, 12 modèles installés).
Ton inventaire peut différer.

| Fichier                              | Montre                                                 |
|--------------------------------------|--------------------------------------------------------|
| `screenshots/01_home_top.png`        | Header V8 + navigation + provider Ollama               |
| `screenshots/02_inventory_models.png`| Table des modèles installés/chargés                    |
| `screenshots/03_roles_assignment.png`| Section Rôles avec menus déroulants                    |
| `screenshots/04_gateway_routes.png`  | Section Gateway (table de routage par rôle)            |
| `screenshots/05_test_model.png`      | Section « Tester un modèle »                           |
| `screenshots/06_dashboard_stats.png` | Stats gateway (volume, p50/p95, répartitions)          |
| `screenshots/07_scoreboard.png`      | Scoreboard des évaluations                             |
| `screenshots/08_rag_panel.png`       | Panneau RAG local (documents + interrogation)          |
| `screenshots/09_training_panel.png`  | Panneau Adaptation LoRA/QLoRA                          |
| `screenshots/10_serving_status_warning.png` | Distinction « Actif (registry) » vs « Serving »  |

---

## Démarrage rapide

```bash
cd /home/gear-code/02_projects/llm-cockpit/llm-cockpit-v0
git checkout phase/v8
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

```text
http://127.0.0.1:8001            # Inventaire
http://127.0.0.1:8001/dashboard  # Dashboard
```

> Le port `8000` est souvent pris : utilise `8001` (ou `8010`).

---

## Les 3 choses à ne pas oublier

1. **Promu ≠ servi** : en V8, le gateway sert toujours le **modèle de base** ; une
   version adaptée promue reste `serving_status: not_served`.
2. **Stats = trafic gateway** : seuls les appels `/v1/chat/completions` alimentent
   le dashboard.
3. **Tout est local** : aucune donnée ne sort, aucun service cloud, dry-run par
   défaut pour l'adaptation.

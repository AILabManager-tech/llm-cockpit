# llm_cockpit — état du chantier

Repo : `/home/gear-code/02_projects/llm-cockpit/llm-cockpit/` (git local, pas de remote)
Branche courante : `main` — `79b8188`
Date de ce point : 2026-08-12

> Fichier de suivi interne. À exclure si le repo est publié (comme `docs/` l'a été).

## Contexte des 4 dossiers du parent

- **`llm-cockpit/`** (celui-ci) = source de vérité. Git réel, données runtime réelles
  (`data/actions.jsonl`, `cockpit.db`, `roles.json`).
- `COCKPIT_LLM/` = archive de planification (mandats V0-V8, roadmaps A/B, PDF) **+**
  `formation_v8/` (copie des docs de formation retirés du repo le 2026-08-12).
  **Décision : gardé tel quel, hors repo.** Cohérent avec `MANIFEST.md` de l'export qui
  liste explicitement `docs/formation/` et `docs/mandats/` comme "Removed Before Publishing".
- `llm-cockpit-github-export/` = snapshot d'export, désormais **périmé** (antérieur à tout
  le travail du 2026-08-12). Régénérable depuis ce repo.
- `llm-cockpit-v0/` = un seul `README.md`, vide, sans valeur.

## DONE

- [x] `llm-cockpit/` identifié comme unique source de vérité
- [x] Question `COCKPIT_LLM/` tranchée : archive externe conservée, docs de formation
      copiées dedans (`formation_v8/`) avant que la suppression soit committée → zéro perte
- [x] Suite de tests verte : **141 tests**, `ruff` clean
- [x] 2 tests obsolètes (assertions FR sur des templates devenus EN) corrigés
- [x] Traduction EN de **tous** les messages back-end visibles (routing, actions, checks
      d'éval, erreurs HTTP, réponses RAG, suites d'éval) — le FR est rendu par `i18n.js`
- [x] Couverture i18n vérifiée par script : tous les libellés rendus ont une traduction FR
      (les 69 restants sont des données dynamiques : noms de modèles, digests, ms, rôles)
- [x] Ports alignés sur le poste : `8000`/`20000-20999` → **`22050-22099`**
      (bloc 20xxx = NEXOS ; 22xxx = apps LLM locales)
- [x] App vérifiée en vrai : 28 routes GET à 200, gateway testé bout en bout
      (routage par rôle + logs + stats)
- [x] Packaging Linux vérifié en vrai — **2 bugs bloquants trouvés et corrigés** :
      `--add-data` mappait `schema.sql` sur un dossier (bundle gelé mort à l'import) ;
      `create_window(icon=)` invalide en pywebview ≥ 5
- [x] Fallback navigateur ajouté quand aucun backend GTK/QT n'est dispo (cas réel du
      bundle PyInstaller) + `Depends:` GTK du `.deb` passés en `Recommends:`
- [x] `.deb` construit et inspecté : `dist/linux/llm-cockpit_0.1.0_amd64.deb` (18 Mo)
- [x] README réécrit pour publication (capacités, config, gateway, packaging, tests)
- [x] LICENSE MIT + `uv.lock` trackés, `docs/` interne retiré du tree publié
- [x] `main` fast-forward de V0 → V8 (historique linéaire, branches `phase/*` intactes)
- [x] 5 commits atomiques (`a573fb6` → `79b8188`)

## TODO — décisions utilisateur

- [ ] **Supprimer `llm-cockpit-v0/`** (1 README vide) — destructif, confirmation requise
- [ ] **Supprimer `llm-cockpit-github-export/`** — périmé depuis le 2026-08-12, régénérable ;
      destructif, confirmation requise
- [ ] **Publier sur GitHub ?** Le repo n'a aucun remote. `git push` = hard-stop.
      Si oui : créer le repo, `git remote add origin …`, exclure `llm_cockpit.md`
- [ ] **Fenêtre native** : le bundle PyInstaller ne peut pas importer le `gi` système →
      il ouvre le navigateur par défaut. Pour une vraie fenêtre native il faudrait ajouter
      un backend Qt pip-installable (PyQt6 + QtWebEngine, ~200 Mo) à l'extra `desktop`.
      Non fait : décision de périmètre / poids.

## Vérifié cette session

- `uv run pytest` → 141 passed
- `uv run ruff check .` → All checks passed
- serveur `127.0.0.1:22050` : 28 routes GET → 200
- gateway : `model:"code"` → `ollama/qwen2.5-coder:7b`, logué, agrégé dans `/api/stats`
- bundle gelé `dist/linux/LLM-Cockpit/LLM-Cockpit --port 22051` → `/`, `/dashboard`,
  `/static/*`, `/partials/*` à 200
- `dpkg-deb -I` sur le `.deb` → métadonnées correctes

## Non vérifié

- Le toggle FR/EN n'a pas été cliqué dans un vrai navigateur cette session (extension
  Chrome non connectée, `chrome-cdp` de gstack est macOS-only). Vérifié autrement :
  syntaxe JS (`node --check`) + couverture des libellés par script.

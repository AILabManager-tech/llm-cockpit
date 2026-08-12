> **MANDATS_AGENT** — mandat `03 · PLANIFIER` — Claude Opus 5 (`claude-opus-5`) — 2026-08-12 — exécution autonome enchaînée avec les mandats 04 et 07

| Champ | Valeur |
|---|---|
| Mandat exécuté | 03 · PLANIFIER — feuille de route jalonnée |
| Chemin du mandat source | `~/Documents/MANDATS_AGENT/03___PLANIFIER___FEUILLE-DE-ROUTE-JALONNEE.md` |
| Modèle | Claude Opus 5 (`claude-opus-5`) |
| Date | 2026-08-12 |
| Mode d'exécution | Autonome, chaîné avec `04 · EXÉCUTER` et `07 · FINALISER` |
| Projet | LLM Cockpit — `~/02_projects/llm-cockpit/llm-cockpit` |

---

## A. État de départ

Snapshot pris avant planification.

| Élément | Valeur observée |
|---|---|
| Chemin absolu | `~/02_projects/llm-cockpit/llm-cockpit` |
| Racine Git | idem (repo autonome) |
| Branche | `main` |
| HEAD | `884cc44` |
| Remote | `https://github.com/AILabManager-tech/llm-cockpit` (privé) |
| Branches distantes | `main`, `dependabot/uv/pypdf-6.15.0`, `dependabot/uv/setuptools-83.0.0` |
| Fichiers modifiés | `app/desktop.py`, `linux/llm-cockpit.desktop`, `scripts/build_deb.py`, `scripts/install_linux.py`, `tests/test_desktop.py` |
| Tests au démarrage | 144 passed (dernière exécution avant interruption) |
| Bundle courant | `dist/linux/LLM-Cockpit` — 38 Mo |
| Docs de pilotage | `README.md`, `llm_cockpit.md` (suivi, gitignoré), `../COCKPIT_LLM/` (archive) |

### État réel vs état affirmé

| Affirmation | État observé | Écart |
|---|---|---|
| « L'app desktop s'ouvre en fenêtre native » (intention d'origine) | Faux depuis toujours : le bundle gelé ne peut pas importer le `gi` système | Écart réel, objet de ce plan |
| « Fenêtre dédiée via Brave `--app` » (travail en cours, non committé) | Implémenté, 144 tests verts, **jamais lancé pour de vrai** | NON DÉMONTRÉ |
| Repo à jour sur GitHub | `main` distant = `884cc44` = HEAD local | Conforme |
| Aucun travail externe en attente | Faux : 2 branches Dependabot créées côté GitHub | Écart découvert au snapshot |

**Constat périmé écarté** : « il faut ~200 Mo de Qt, donc le mode `--app` navigateur est préférable » — périmé par décision utilisateur du 2026-08-12 : le coût en Mo est accepté, la fenêtre Qt est demandée.

---

## B. Objectif reformulé

> Lancer LLM Cockpit ouvre **une fenêtre d'application autonome**, sans onglet ni barre d'adresse, **sans dépendre d'un navigateur installé sur la machine**, y compris depuis le paquet `.deb` sur une machine vierge.

### Définition de « terminé »

1. Le binaire gelé ouvre une fenêtre dont le moteur de rendu est **QtWebEngine embarqué dans le bundle**, pas un navigateur du système.
2. Le cockpit y est fonctionnel (inventaire, dashboard, HTMX).
3. Aucune régression : suite de tests verte, lint vert.
4. Le `.deb` reconstruit contient QtWebEngine et s'installe/se désinstalle proprement.
5. La documentation dit ce qui est réellement livré.

### Hors périmètre

- Windows et macOS (le packaging livré est Linux).
- Toute fonctionnalité produit du cockpit (RAG, évals, gateway…) : gelée.
- Refonte de l'UI.

### Invariants à ne jamais casser

- `INV-1` Les 144 tests existants restent verts.
- `INV-2` Le serveur reste sur `127.0.0.1`, port dans `22050-22099`.
- `INV-3` Aucune dépendance sous licence copyleft forte (GPL) n'entre dans le projet MIT.
- `INV-4` L'app reste utilisable si la fenêtre Qt échoue (dégradation, jamais crash).
- `INV-5` `data/`, `build/`, `dist/` restent hors du dépôt.

### Contrainte non négociable

`INV-3` élimine PyQt6 (GPL v3). **PySide6 (LGPLv3) est la seule option viable**, à condition que les bibliothèques Qt restent remplaçables — ce que le mode `onedir` de PyInstaller garantit.

---

## C. Tableau des jalons

| ID | Jalon | Priorité | Dépend de | Effort | Certitude | Critère de réussite |
|----|-------|----------|-----------|--------|-----------|---------------------|
| J1 | Faisabilité PySide6 hors gel | P0 | — | faible | moyenne | `webview.platforms.qt` s'importe et une fenêtre s'ouvre depuis le venv |
| J2 | Sélection explicite du backend Qt + cascade préservée | P0 | J1 | faible | haute | Le code demande `gui='qt'` ; suite verte ; fallbacks intacts |
| J3 | QtWebEngine embarqué dans le bundle gelé | P0 | J2 | moyen | **faible** | Le binaire de `dist/` ouvre une fenêtre servie par le QtWebEngine du bundle |
| J4 | `.deb` régénéré et vérifié | P1 | J3 | faible | haute | `.deb` contient QtWebEngine, `dpkg-deb -c` le prouve, install/uninstall OK |
| J5 | Documentation + intégration | P1 | J3 | faible | haute | README décrit le comportement réel ; commits atomiques ; `main` poussé |
| J6 | Branches Dependabot tranchées | P2 | — | faible | haute | Chaque branche est mergée ou fermée avec raison ; suite verte après |

J6 est **parallélisable** : il ne dépend d'aucun autre jalon.

---

## D. Contrat détaillé des jalons

```yaml
id: "J1"
titre: "Faisabilité PySide6 hors gel"
objectif: "Savoir si le backend Qt fonctionne sur cette machine avant d'investir dans le packaging."
priorite: "P0"
depend_de: []
debloque: ["J2", "J3"]
perimetre:
  inclus: ["ajout de qtpy + PySide6 à l'extra desktop", "lancement de app.desktop hors gel"]
  exclus: ["toute modification de la logique de cascade"]
travaux:
  - "Ajouter qtpy et PySide6 à l'extra desktop de pyproject.toml"
  - "uv sync --extra desktop"
  - "Importer webview.platforms.qt et vérifier le renderer retenu"
  - "Lancer app.desktop et observer le processus fenêtré"
criteres_de_reussite:
  - "import de webview.platforms.qt sans exception"
  - "renderer == 'qtwebengine'"
  - "une fenêtre existe, avec la WM_CLASS attendue, pendant que le serveur répond 200"
preuve_attendue:
  - "sortie de l'import + valeur de renderer"
  - "wmctrl/xdotool listant la fenêtre, et curl /api/health à 200 au même instant"
invariants_a_preserver: ["INV-3 : PySide6 uniquement, jamais PyQt6"]
risques:
  - "Session Wayland sans XWayland : la fenêtre peut échouer à s'afficher"
  - "PySide6 volumineux : téléchargement long"
effort: "faible"
certitude: "moyenne"
hard_stops: []
```

```yaml
id: "J2"
titre: "Sélection explicite du backend Qt, cascade préservée"
objectif: "Demander Qt sans casser la dégradation existante."
priorite: "P0"
depend_de: ["J1"]
debloque: ["J3"]
perimetre:
  inclus: ["app/desktop.py", "tests/test_desktop.py"]
  exclus: ["suppression des fallbacks navigateur"]
travaux:
  - "Passer gui='qt' à webview.start() quand le backend Qt est disponible"
  - "Conserver la cascade : Qt -> navigateur --app -> navigateur par défaut"
  - "Tests sur la sélection du backend"
criteres_de_reussite:
  - "Le code demande explicitement le backend qt"
  - "Suite complète verte, lint vert"
  - "Un backend Qt absent redonne exactement le comportement actuel"
preuve_attendue:
  - "pytest -q et ruff check ."
  - "test dédié : webview.start reçoit gui='qt'"
invariants_a_preserver: ["INV-1", "INV-4"]
risques: ["Régression silencieuse des fallbacks"]
effort: "faible"
certitude: "haute"
hard_stops: []
```

```yaml
id: "J3"
titre: "QtWebEngine embarqué dans le bundle gelé"
objectif: "La fenêtre native doit venir du bundle, pas de la machine."
priorite: "P0"
depend_de: ["J2"]
debloque: ["J4", "J5"]
perimetre:
  inclus: ["scripts/build_linux_bundle.py", "scripts/build_desktop.py"]
  exclus: ["passage au mode onefile"]
travaux:
  - "Faire collecter PySide6 + QtWebEngine par PyInstaller"
  - "Vérifier la présence de QtWebEngineProcess et des ressources dans dist/"
  - "Lancer le binaire gelé et prouver la fenêtre"
criteres_de_reussite:
  - "QtWebEngineProcess présent dans le bundle"
  - "Le binaire gelé ouvre une fenêtre pendant que /api/health répond 200"
  - "Aucun message de repli vers un navigateur dans la sortie"
preuve_attendue:
  - "find sur le bundle montrant QtWebEngineProcess et les .pak"
  - "wmctrl + curl simultanés, sortie du binaire sans ligne de fallback"
invariants_a_preserver: ["INV-2", "INV-4", "INV-5"]
risques:
  - "PyInstaller et QtWebEngine : sandbox et chemins de ressources souvent cassés en gelé"
  - "Bundle passant de 38 Mo a ~400 Mo"
effort: "moyen"
certitude: "faible"
hard_stops: []
```

```yaml
id: "J4"
titre: ".deb régénéré et vérifié"
objectif: "Le paquet livré contient réellement la fenêtre native."
priorite: "P1"
depend_de: ["J3"]
debloque: []
perimetre:
  inclus: ["scripts/build_deb.py", "scripts/install_linux.py", "scripts/uninstall_linux.py"]
  exclus: ["publication du .deb"]
travaux:
  - "Reconstruire le .deb"
  - "Revoir Depends/Recommends au vu des vraies dépendances de QtWebEngine"
  - "Vérifier install puis uninstall en profil utilisateur"
criteres_de_reussite:
  - "dpkg-deb -c montre QtWebEngineProcess"
  - "install_linux.py puis uninstall_linux.py laissent le profil dans son état initial"
preuve_attendue:
  - "dpkg-deb -I et -c"
  - "liste des fichiers du profil avant/après"
invariants_a_preserver: ["INV-5"]
risques: ["Dépendances système réelles de QtWebEngine mal déclarées"]
effort: "faible"
certitude: "haute"
hard_stops: []
```

```yaml
id: "J5"
titre: "Documentation et intégration"
objectif: "Ce qui est écrit correspond à ce qui est livré."
priorite: "P1"
depend_de: ["J3"]
debloque: []
perimetre:
  inclus: ["README.md", "llm_cockpit.md", "commits", "push"]
  exclus: ["passage du repo en public"]
travaux:
  - "Mettre le README au niveau du comportement réel et de la note de licence LGPL"
  - "Commits atomiques"
  - "Pousser main"
criteres_de_reussite:
  - "Aucune affirmation du README non vérifiée dans cette session"
  - "git status propre, main local == main distant"
preuve_attendue: ["git log", "git ls-remote"]
invariants_a_preserver: ["INV-5"]
risques: ["Documenter un comportement supposé"]
effort: "faible"
certitude: "haute"
hard_stops:
  - "Push : autorisé par l'utilisateur dans la conversation du 2026-08-12 pour ce repo"
```

```yaml
id: "J6"
titre: "Branches Dependabot tranchées"
objectif: "Ne pas laisser le dépôt distant diverger silencieusement."
priorite: "P2"
depend_de: []
debloque: []
perimetre:
  inclus: ["dependabot/uv/pypdf-6.15.0", "dependabot/uv/setuptools-83.0.0"]
  exclus: ["mise en place d'une politique Dependabot"]
travaux:
  - "Inspecter chaque bump"
  - "Appliquer localement, lancer la suite, intégrer ou fermer avec raison"
criteres_de_reussite:
  - "Aucune branche Dependabot en suspens sans décision écrite"
  - "Suite verte après intégration"
preuve_attendue: ["pytest après bump", "état des branches distantes"]
invariants_a_preserver: ["INV-1"]
risques: ["Bump cassant une dépendance transitive"]
effort: "faible"
certitude: "haute"
hard_stops: []
```

---

## E. Séquence recommandée

| Position | Jalon | Pourquoi ici |
|---|---|---|
| 1 | J1 | Réduit l'incertitude la plus forte avant tout investissement en packaging |
| 2 | J2 | Changement réversible et testé, protège la dégradation avant le gel |
| 3 | J3 | Étape à faible certitude : elle vient après le filet de tests |
| 4 | J4 | Consomme le résultat de J3 |
| 5 | J5 | Documente uniquement ce qui a été démontré |
| — | J6 | Parallélisable, indépendant de toute la chaîne Qt |

**Horizon ferme** : J1 à J6, tous contractualisés ci-dessus.
**Horizon indicatif** : aucun. Si J3 échoue durablement, la suite se rediscute au lieu de se planifier maintenant.

**Hypothèse explicite** : PyInstaller sait embarquer QtWebEngine de façon fonctionnelle en `onedir` sur cette machine. Validée par J3, invalidée par un binaire gelé qui retombe sur le navigateur.

---

## F. Points de décision anticipés

| Point | Jalon | Information nécessaire | Options | Recommandation |
|---|---|---|---|---|
| Poids du livrable | J3 | Taille finale du bundle | Accepter ~400 Mo / revenir au mode `--app` | Accepter : la fenêtre native a été demandée en connaissance du coût |
| Échec de QtWebEngine gelé | J3 | Nature de l'échec | Corriger / livrer non gelé / revenir au mode `--app` | Corriger d'abord ; si irréductible, `HUM-*` et la cascade actuelle reste en place |
| Push | J5 | — | — | Autorisé le 2026-08-12 pour ce repo |
| Repo public | hors plan | — | — | Reste fermé : l'historique porte un email personnel |

---

## G. Hors périmètre

- Windows / macOS : aucun packaging livré pour ces plateformes.
- Mode `onefile` : QtWebEngine s'en accommode mal, et `onedir` est requis pour la conformité LGPL.
- PyQt6 : éliminé par `INV-3`.
- Toute évolution fonctionnelle du cockpit.
- Passage du dépôt en public.

---

## H. Risques du plan lui-même

1. **J3 est le point de rupture.** Sa certitude est faible ; PyInstaller et QtWebEngine échouent fréquemment sur les chemins de ressources et le sandbox. Si J3 échoue, J4 et J5 perdent leur objet et le plan devient caduc au-delà de J2.
2. **Environnement graphique.** La preuve d'une fenêtre suppose un affichage accessible depuis cette session. Si aucune fenêtre ne peut être observée, les critères de J1 et J3 deviennent `NON DÉMONTRÉ` — ils ne doivent pas être requalifiés en PASS sur la seule foi d'un processus vivant.
3. **Poids.** Un bundle de ~400 Mo peut faire reconsidérer la décision une fois le chiffre réel connu.

# Dépannage — LLM Cockpit V8

Symptômes courants et résolution. Beaucoup de « problèmes » sont en réalité des
comportements **voulus** (refus de sécurité, états honnêtes). Cette page le dit
clairement.

---

## Démarrage

### L'app ne démarre pas / « address already in use »

Le port est occupé (souvent `8000`). Choisis-en un autre :

```bash
ss -ltn | grep :8001 || echo libre
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### La page est vide / le style ne se charge pas

L'interface charge **htmx** depuis le CDN unpkg. Hors-ligne, les boutons ne
fonctionnent pas. Solutions : être en ligne, ou utiliser directement l'**API
JSON** (`/api/...`, `/v1/...`), qui ne dépend d'aucun CDN.

---

## Inventaire & providers

### Providers : Ollama « injoignable »

Ollama n'écoute pas. Démarre-le (`ollama serve`) et vérifie
`OLLAMA_BASE_URL` (défaut `http://127.0.0.1:11434`). Le cockpit reste vivant
même si Ollama est down — il l'affiche honnêtement, ce n'est pas un crash.

### La table des modèles est vide

Soit Ollama est injoignable (voir ci-dessus), soit aucun modèle n'est installé
(`ollama list`). Le cockpit **n'invente jamais** de modèle.

### Un provider apparaît en « drift »

Normal : le drift signale un désaccord déclaré ↔ réalité (ex. « déclaré actif
mais injoignable », ou « désactivé mais répond »). Corrige la `base_url` ou
l'état `enabled`, ou retire le provider.

### Les boutons Charger/Décharger n'apparaissent pas

Seuls les modèles **Ollama** les affichent. Les modèles `openai_compat` ne
supportent pas load/unload (c'est déclaré dans leurs capacités).

---

## Rôles

### « modèle non installé » au moment d'assigner

Tu as choisi un modèle absent d'Ollama. Installe-le (`ollama pull …`) ou
choisis-en un autre. Comportement voulu : pas d'assignation fantôme.

### « rôle non assigné » au test ou au gateway

Le rôle visé n'a pas de modèle. Assigne-le dans Inventaire → Rôles.

### L'assignation disparaît après redémarrage

Vérifie que `data/roles.json` est inscriptible et que `ROLES_CONFIG_PATH` pointe
au bon endroit. Si le fichier est corrompu, l'API renvoie une **erreur claire
(400)** et ne l'écrase pas — répare ou supprime le fichier.

---

## Gateway

### `{"error": …}` 400 sur `/v1/chat/completions`

Cause la plus fréquente : `model` est un **rôle non assigné** ou un **modèle
inexistant**. Assigne le rôle, ou utilise un nom de modèle réel présent dans
l'inventaire agrégé. C'est un refus volontaire, pas un bug.

### 502 sur `/v1/chat/completions`

Le provider cible est injoignable pendant la génération. Vérifie qu'Ollama
tourne et que le modèle se charge. Le message d'erreur reste contrôlé (jamais de
stacktrace).

### `/v1/*` renvoie 404

`GATEWAY_ENABLED=0`. Repasse à `1` (ou ne définis pas la variable).

### Le streaming ne marche pas

Non supporté en V8 (`stream:false`). Les réponses sont non-streamées ; le champ
`stream` est ignoré.

---

## Observabilité (logs & stats)

### `/api/logs` ou les stats sont vides

Seules les requêtes du **gateway** (`/v1/chat/completions`) y comptent. Tester un
modèle/rôle ou lancer une éval **n'alimente pas** les stats. Fais un vrai appel
gateway.

### Je ne vois pas le contenu de mes prompts dans les logs

Voulu : `LOG_PROMPTS=0` par défaut (anti-PII). Le champ `prompt` n'est jamais
exposé par l'API, même si `LOG_PROMPTS=1` (où il est seulement stocké, tronqué).

### Latences à `—`

Aucune requête avec latence enregistrée dans la fenêtre demandée.

---

## Évaluations & scoreboard

### Suite inconnue / YAML invalide (400)

Le nom de suite n'existe pas dans `EVALS_DIR`, ou le YAML est cassé, ou un
**check inconnu** est référencé. Suites livrées : `json_strict`, `code_python`,
`summary`.

### Un modèle ressort en `error` dans un run

S'il est introuvable dans l'inventaire agrégé, son cas est marqué `error` mais le
run **continue** et se termine. Vérifie le nom du modèle.

### Le scoreboard est vide

Aucune éval lancée. Lance-en une depuis le Dashboard.

---

## RAG

### « modèle d'embedding non installé »

`RAG_EMBED_MODEL` (défaut `nomic-embed-text`) doit être installé :
`ollama pull nomic-embed-text`. Pas de fallback inventé.

### « chemin hors du dossier autorisé »

Le fichier doit être **dans** `RAG_DOCS_DIR` (`data/rag/docs/`). Les chemins avec
`..` sont refusés. Copie le fichier dans le bon dossier.

### La réponse dit « Aucune source »

Honnête, pas un bug : aucun document pertinent (souvent : rien d'ingéré). Ingère
des documents d'abord.

### Le RAG ne semble pas meilleur que sans RAG

C'est exactement ce que V7 permet de **mesurer**. Compare les deux runs
(`with_rag` true/false) au scoreboard ; le RAG n'est utile que si son taux
dépasse le non-RAG.

---

## Adaptation (V8)

### Le job reste en `dry_run`

Voulu : `TRAIN_RUNNER` n'est pas configuré. Le cockpit valide et prépare sans
entraîner. Pour un entraînement réel, voir `GUIDE_ADMIN_CONFIGURATION.md §6.

### « base_model requis »

`TRAIN_BASE_MODEL` est vide et tu n'as pas fourni `base_model` dans la requête.
Renseigne l'un des deux. Pas d'invention de modèle.

### Aucune version créée après un job

En **dry-run**, c'est normal : aucune version n'est produite. Une version
candidate n'apparaît qu'après un job **réussi avec un runner réel**.

### Promotion refusée (409)

Voulu : la promotion est **gatée par les évals**. Il faut un `eval_run` attaché
au candidat **et** au baseline, et le candidat doit **dépasser** le baseline.
Attache d'abord les évals (`POST /api/models/versions/{id}/eval`).

### J'ai promu un adapter mais le gateway répond pareil

**Comportement voulu et central en V8.** « Promu (registry) » ≠ « servi ». Le
gateway sert toujours le modèle de base ; le candidat reste `serving_status:
not_served`. Servir un adapter est hors périmètre V8.

---

## Vérification de santé globale

```bash
cd /home/gear-code/02_projects/llm-cockpit/llm-cockpit-v0
uv run ruff check .
uv run pytest
git status --short
```

- `134 passed` attendu. Un échec pointe un vrai problème de logique → lis le nom
  du test échoué (cf. `PARCOURS_VALIDATION_PAR_LES_TESTS.md`).
- `git status --short` doit être **vide** ; rien sous `data/` ne doit y
  apparaître (gitignored).
- `pytest` ne teste **pas** le rendu visuel : complète avec la **Checklist D** de
  `PARCOURS_VALIDATION_PAR_LES_TESTS.md`.

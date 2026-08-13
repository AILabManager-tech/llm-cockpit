# LLM Cockpit — guide utilisateur

Guide d'utilisation du cockpit installé sur ce poste. Tout ce qui suit a été
vérifié contre le code, pas rédigé de mémoire.

---

## 1. Ce que fait le cockpit

Le cockpit est un poste de pilotage local pour les modèles qui tournent sur ta
machine. Il répond à neuf questions, dans cet ordre :

| Couche | Question à laquelle elle répond |
|---|---|
| Inventaire | Quels modèles sont installés, lesquels sont chargés en mémoire ? |
| Contrôle | Charger, décharger, tester un modèle sans passer par le terminal |
| Rôles | Quel modèle joue le rôle « code », « chat », « vision » ? |
| Registry | Quels fournisseurs sont branchés, et divergent-ils ? |
| Gateway | Une adresse unique où mes applications envoient leurs requêtes |
| Observabilité | Qui a appelé quoi, combien de temps ça a pris, qu'est-ce qui a raté ? |
| Évaluations | Quel modèle est réellement meilleur, mesuré et non ressenti ? |
| RAG | Répondre à partir de mes documents locaux, avec les sources citées |
| Adaptation | Entraîner un adaptateur LoRA et le promouvoir seulement s'il gagne |

Trois principes tenus par le code, utiles à connaître :

- **Rien n'est inventé.** Un modèle absent produit une erreur, jamais un
  remplacement silencieux.
- **Le baseline n'est jamais écrasé.** Une adaptation crée une version à côté.
- **« Actif » ne veut pas dire « servi ».** Voir la section 9.

---

## 2. Lancer le cockpit

**Depuis le menu d'applications** : cherche « LLM Cockpit ». Une fenêtre
d'application s'ouvre, sans onglet ni barre d'adresse.

**Depuis un terminal** :

```bash
llm-cockpit
```

Options utiles :

```bash
llm-cockpit --port 22060          # forcer un port précis
llm-cockpit --data-dir /chemin    # utiliser un autre dossier de données
```

Sans `--port`, le cockpit prend le premier port libre entre **22050 et 22099**.

Fermer la fenêtre arrête le serveur. Il ne reste rien en tâche de fond.

### Emplacements sur ce poste

| Quoi | Où |
|---|---|
| Application installée | `~/.local/share/llm-cockpit/` |
| **Tes données** | `~/.local/state/llm-cockpit/` |
| Lanceur | `~/.local/bin/llm-cockpit` |
| Entrée de menu | `~/.local/share/applications/llm-cockpit.desktop` |

Les deux premiers sont **séparés volontairement** : désinstaller l'application
ne touche pas à tes données.

### Prérequis

Ollama doit tourner sur `http://127.0.0.1:11434`. Si le cockpit affiche
« Ollama unreachable », c'est qu'Ollama n'écoute pas — le cockpit ne le démarre
jamais lui-même, par conception.

---

## 3. Inventaire — la page d'accueil

C'est la page ouverte au lancement. Elle rafraîchit toute seule toutes les 5 s.

**Le bandeau Ollama** indique `reachable` / `unreachable` et l'adresse
interrogée. Un cockpit qui n'affiche aucun modèle mais dit `reachable` signifie
qu'aucun modèle n'est installé — le message le distingue explicitement d'un
Ollama injoignable.

**Le tableau des modèles** fusionne deux sources : les modèles installés
(`/api/tags`) et les modèles chargés en mémoire (`/api/ps`). La colonne
**State** dit `loaded` ou `not loaded`, et **Source** indique d'où vient
l'information — `ps_only` signale un modèle chargé mais absent de la liste des
installés, ce qui est une anomalie à connaître.

**Colonne Actions** : `Load` charge le modèle en mémoire, `Unload` le décharge.
Ces boutons n'apparaissent que pour Ollama et seulement si les actions sont
activées.

**Tester un modèle** : le panneau « Test a model » envoie une invite à un
modèle et affiche la réponse dans le journal d'actions, en bas de page. Laisse
l'invite vide pour utiliser celle par défaut.

### Ce que le contrôle ne fera jamais

Trois actions seulement sont autorisées, en dur dans le code : `load`, `unload`,
`test`. Il n'y a pas de suppression de modèle, pas d'arrêt de service. Chaque
tentative est journalisée, y compris les refus, dans
`~/.local/state/llm-cockpit/actions.jsonl`.

Pour désactiver complètement le contrôle : lancer avec `ACTIONS_ENABLED=0`.

---

## 4. Rôles — nommer les usages

Sept rôles existent, fixés :

`chat` · `code` · `vision` · `embedding` · `fast` · `quality` · `experimental`

Assigne un modèle à un rôle depuis le panneau **Roles**. L'intérêt vient à la
section 6 : tes applications appelleront `code` au lieu de
`qwen2.5-coder:7b`, et tu changeras de modèle sans toucher à leur code.

Un modèle non installé est refusé à l'assignation — pas de rôle qui pointe dans
le vide.

**Tester un rôle** vérifie la chaîne complète : rôle → modèle assigné →
génération réelle. Le résultat va dans le journal d'actions.

Les assignations sont dans `~/.local/state/llm-cockpit/roles.json`.

---

## 5. Registry — brancher d'autres fournisseurs

Ollama est présent par défaut. Le panneau **Providers** permet d'ajouter tout
service exposant une API compatible OpenAI : donne un identifiant, choisis
`openai_compat`, indique l'URL de base.

La colonne **Drift** signale un écart entre ce que le registry croit et ce que
le fournisseur expose réellement. `ok` signifie qu'ils sont d'accord.

Deux limites assumées pour un fournisseur OpenAI-compatible : `load` et
`unload` ne sont pas supportés (l'API ne les exprime pas), et la liste des
modèles chargés est toujours vide plutôt que fausse.

---

## 6. Gateway — l'adresse unique pour tes applications

Le cockpit expose une API compatible OpenAI sur son propre port :

```
POST /v1/chat/completions
GET  /v1/models
```

Exemple, en supposant le cockpit sur le port 22050 :

```bash
curl http://127.0.0.1:22050/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'x-cockpit-app: mon-script' \
  -d '{"model": "code", "messages": [{"role": "user", "content": "bonjour"}]}'
```

Le champ `model` accepte :

- un **rôle** : `code`, ou `role:code` ;
- un **nom de modèle réel** : `qwen2.5-coder:7b`.

La réponse contient un champ supplémentaire `x_cockpit_route` qui dit
exactement ce qui a été résolu : rôle demandé, modèle retenu, fournisseur. Tu
n'as jamais à deviner qui a répondu.

L'en-tête `x-cockpit-app` est facultatif mais recommandé : il fait apparaître
ton application dans les statistiques, ce qui rend le tableau de bord
réellement utile.

Depuis Python, avec le client OpenAI officiel :

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:22050/v1", api_key="unused")
reponse = client.chat.completions.create(
    model="code",
    messages=[{"role": "user", "content": "bonjour"}],
)
```

Le panneau **Gateway** du cockpit affiche la table de routage courante : ce que
chaque rôle résoudrait *maintenant*, et pourquoi. Un rôle non assigné ou dont
le modèle a disparu apparaît `not routable` avec sa raison — jamais de repli
silencieux vers un autre modèle.

---

## 7. Tableau de bord — ce qui s'est réellement passé

Onglet **Dashboard**. Chaque requête passée par le gateway y est enregistrée
dans une base SQLite locale.

Tu y lis : le nombre de requêtes, le taux d'erreur, les latences p50 et p95, la
répartition par modèle, par fournisseur et par application, puis la liste des
dernières requêtes.

**Les invites ne sont pas stockées** par défaut. Pour les conserver malgré
tout : `LOG_PROMPTS=1`. Réfléchis-y à deux fois, c'est de la donnée sensible.

---

## 8. Évaluations — comparer sans se raconter d'histoires

Une évaluation joue une **suite** de cas sur un ou plusieurs modèles et vérifie
les réponses avec des **checks déterministes**. Aucun juge LLM, aucun appel
réseau externe, et **le code généré n'est jamais exécuté**.

Trois suites sont livrées : `summary`, `json_strict`, `code_python`.

Huit checks existent :

| Check | Vérifie |
|---|---|
| `non_empty` | réponse non vide |
| `json_valid` | la réponse est du JSON valide |
| `contains:texte` | la réponse contient `texte` |
| `regex:motif` | la réponse correspond au motif |
| `equals:valeur` | égalité stricte après nettoyage |
| `min_length:n` / `max_length:n` | longueur de la réponse |
| `latency_lt:ms` | la réponse est arrivée en moins de `ms` |

Dans le panneau **Scoreboard** : choisis la suite, saisis les modèles à
comparer séparés par des virgules (des rôles sont acceptés), lance. Tu obtiens
le taux de réussite, le nombre de cas, la latence moyenne et les erreurs, par
modèle.

Les évaluations passent par le **routage réel du gateway** : tu mesures le
chemin que tes applications empruntent, pas un chemin de laboratoire.

### Écrire ta propre suite

Une suite est un fichier YAML :

```yaml
name: ma_suite
role: code
description: Ce que cette suite vérifie.
cases:
  - name: cas_1
    prompt: |
      L'invite envoyée au modèle.
    checks:
      - non_empty
      - contains:def
```

Pointe `EVALS_DIR` vers ton dossier de suites pour qu'elles soient chargées.

---

## 9. RAG — répondre à partir de tes documents

**Ingérer.** Dépose tes fichiers dans `~/.local/state/llm-cockpit/rag/docs/`,
puis indique le nom du fichier dans le panneau **Local RAG** (chemin relatif à
ce dossier — un chemin qui en sort est refusé).

Formats acceptés : `.txt`, `.md`, `.pdf`.

L'ingestion découpe le document en fragments et calcule leurs embeddings avec
le modèle `nomic-embed-text`, qui doit être installé dans Ollama. Un document
sans texte extractible est refusé plutôt qu'ingéré vide — utile avec les PDF
scannés, qui ne contiennent que des images.

**Interroger.** Pose ta question, choisis éventuellement un rôle pour la
génération. La réponse cite ses sources sous la forme `[document#n]`, avec un
extrait de chaque passage utilisé. Si aucune source pertinente n'est trouvée,
le cockpit le dit au lieu de répondre quand même.

**Mesurer.** L'évaluation RAG joue la *même* suite deux fois — une fois avec le
contexte documentaire, une fois sans — et te laisse comparer les deux taux de
réussite. C'est la seule façon honnête de savoir si ton RAG apporte quelque
chose.

Tes documents ne quittent jamais la machine et ne sont jamais versionnés.

---

## 10. Adaptation LoRA / QLoRA

Le cockpit **orchestre et mesure** une adaptation ; il n'entraîne pas lui-même.
L'entraînement réel tourne dans un exécutant externe que tu déclares via
`TRAIN_RUNNER`. Sans cette variable, tout reste en **dry-run** : le cockpit
prépare, valide, et affiche la commande qui *aurait* été lancée.

**1. Préparer un dataset.** Un fichier `.jsonl` dans
`~/.local/state/llm-cockpit/datasets/`. Chaque ligne accepte l'une de ces trois
formes :

```json
{"prompt": "...", "response": "..."}
{"instruction": "...", "output": "..."}
{"messages": [{"role": "user", "content": "..."}]}
```

Valide-le depuis le panneau **Datasets** : le cockpit compte les lignes valides
et refuse le fichier à la première ligne malformée, en te donnant son numéro.

**2. Lancer un job.** Choisis le dataset, le modèle de base, la méthode (`lora`
ou `qlora`). Aucune autre méthode n'est acceptée. Sans modèle de base explicite
ni `TRAIN_BASE_MODEL`, le job est refusé — jamais de choix arbitraire.

**3. Évaluer la version produite**, avec une suite de la section 8.

**4. Promouvoir.** La promotion est refusée si : la version n'a pas
d'évaluation, le baseline n'en a pas non plus, ou le candidat ne fait **pas
mieux** que le baseline. Tu ne peux pas promouvoir un modèle qui régresse.

**5. Revenir en arrière** avec `Roll back`, qui réactive le baseline.

### L'avertissement à comprendre

La colonne **Serving** et son message d'alerte disent la vérité suivante :
promouvoir une version la marque *active dans le registry*, mais **le gateway
continue de servir le modèle de base**. L'adaptateur promu n'est pas servi par
`/v1/chat/completions`.

Cette distinction est délibérée : elle t'évite de croire que ta production
utilise un modèle qu'elle n'utilise pas.

---

## 11. Configuration

Toutes les variables se passent à l'environnement au lancement :

```bash
ACTIONS_ENABLED=0 llm-cockpit
```

| Variable | Défaut | Effet |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Adresse d'Ollama |
| `HOST` / `PORT` | `127.0.0.1` / `22050` | Écoute du serveur |
| `DATA_DIR` | dossier d'état | Emplacement des données |
| `ACTIONS_ENABLED` | `1` | `0` désactive load/unload/test |
| `ACTION_TIMEOUT_S` | `60` | Délai maximal d'une action |
| `GATEWAY_ENABLED` | `1` | `0` renvoie 404 sur `/v1/*` |
| `GATEWAY_DEFAULT_ROLE` | `chat` | Rôle utilisé si la requête n'indique rien |
| `LOG_PROMPTS` | `0` | `1` stocke le contenu des invites |
| `EVALS_DIR` | suites livrées | Dossier de tes propres suites |
| `RAG_EMBED_MODEL` | `nomic-embed-text` | Modèle d'embeddings, doit être installé |
| `RAG_TOP_K` | `4` | Nombre de passages récupérés |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | `800` / `100` | Découpage des documents |
| `TRAIN_BASE_MODEL` | vide | Modèle de base par défaut des jobs |
| `TRAIN_RUNNER` | vide | Exécutant d'entraînement ; vide = dry-run |

---

## 12. Interface en français

Le bouton **FR**, en haut à droite, bascule toute l'interface en français. Le
choix est mémorisé et se réapplique après chaque rafraîchissement.

Les identifiants techniques — noms de modèles, empreintes, `registry`,
`gateway` — restent volontairement inchangés.

---

## 13. Dépannage

**« Ollama unreachable »** — Ollama n'écoute pas sur l'adresse configurée.
Vérifie avec `curl http://127.0.0.1:11434/api/tags`.

**Aucun modèle listé mais Ollama joignable** — aucun modèle n'est installé.
`ollama pull qwen2.5:3b` par exemple.

**L'ingestion RAG échoue sur « embedding model not installed »** —
`ollama pull nomic-embed-text`.

**Un rôle apparaît `not routable`** — soit aucun modèle ne lui est assigné,
soit le modèle assigné a été supprimé d'Ollama. Le message précise lequel des
deux.

**La fenêtre ne s'ouvre pas** — le cockpit dégrade automatiquement : fenêtre
Qt, puis navigateur en mode application, puis navigateur par défaut. Lance
`llm-cockpit` depuis un terminal pour lire la raison.

**Le port est occupé** — le cockpit prend le suivant dans `22050-22099` sans
rien demander. Utilise `--port` pour en imposer un.

---

## 14. Désinstaller

Depuis le dépôt :

```bash
uv run python scripts/uninstall_linux.py
```

Le script retire l'application, le lanceur, l'icône et l'entrée de menu, puis
affiche le chemin de tes données, qu'il **ne supprime pas**. À toi de faire le
ménage à la main si tu veux repartir de zéro :

```bash
rm -rf ~/.local/state/llm-cockpit
```

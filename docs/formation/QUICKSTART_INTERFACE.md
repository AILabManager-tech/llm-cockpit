# Quickstart — LLM Cockpit V8

Le strict minimum pour ouvrir le cockpit et faire ton premier appel. Détails
complets dans `FORMATION_INTERFACE_LLM_COCKPIT_V8.md`.

## 1. Démarrer

```bash
cd /home/gear-code/02_projects/llm-cockpit/llm-cockpit-v0
git checkout phase/v8
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

> Le port `8000` est souvent pris : utilise `8001` (ou `8010`). Le bind reste
> **local** (`127.0.0.1`) : c'est voulu.

Ouvre :

```text
http://127.0.0.1:8001            # Inventaire
http://127.0.0.1:8001/dashboard  # Dashboard (stats, évals, RAG, adaptation)
```

## 2. Vérifier qu'Ollama répond

Sur la page Inventaire, le panneau **Providers** doit montrer Ollama
`joignable` avec un nombre de modèles > 0. Sinon, démarre Ollama (`ollama serve`)
et recharge.

## 3. Assigner le rôle `chat` (30 secondes)

Inventaire → section **Rôles** → menu déroulant de la ligne `chat` → choisis un
modèle installé (ex. `qwen2.5:7b`). C'est persisté automatiquement.

## 4. Premier appel au gateway

```bash
curl -X POST http://127.0.0.1:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Cockpit-App: formation" \
  -d '{
    "model": "chat",
    "messages": [
      {"role": "user", "content": "Réponds simplement OK."}
    ]
  }'
```

Tu dois recevoir une réponse au format OpenAI, avec un bloc `x_cockpit_route`
indiquant le provider/modèle réellement utilisé.

## 5. Voir l'activité

```bash
curl http://127.0.0.1:8001/api/stats
curl http://127.0.0.1:8001/api/logs
```

Ou page **Dashboard** : ton appel apparaît dans les stats et les dernières
requêtes.

## 6. Aller plus loin (5 minutes chacun)

| Objectif                 | Action rapide                                                |
|--------------------------|--------------------------------------------------------------|
| Comparer 2 modèles       | Dashboard → Scoreboard → suite `summary` → modèles → Lancer  |
| Répondre depuis un doc   | Mets un `.md` dans `data/rag/docs/`, ingère-le, pose une question |
| Voir l'adaptation        | Dashboard → Adaptation (reste en **dry-run** par défaut)     |

## 7. À retenir absolument

- **Promu ≠ servi** : dans Adaptation, « Promouvoir (registry) » sélectionne une
  version dans le registry mais **ne la sert pas**. Le gateway sert toujours le
  modèle de base (`serving_status: not_served` pour les candidats).
- **Stats = trafic gateway uniquement** : tester un modèle/rôle ou lancer une
  éval n'alimente pas les stats.
- **Tout est local** : aucune donnée ne sort de ta machine.

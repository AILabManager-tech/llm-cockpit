# LLM Cockpit

A local-first cockpit for the LLMs running on your own machine: inventory,
controlled load/unload, role assignment, an OpenAI-compatible gateway,
request observability, deterministic evaluations, a measured local RAG, and
LoRA/QLoRA adaptation orchestration.

Everything runs on `127.0.0.1`. No cloud call, no telemetry, no hidden state:
the cockpit only talks to the providers you declare (Ollama by default).

The UI is English by default with a French toggle in the top bar.

## What it does

| Layer | Capability |
|---|---|
| Inventory | Merges Ollama `/api/tags` (installed) and `/api/ps` (loaded) into one list with a reliable `loaded` flag |
| Control | Allowlisted actions only — `load`, `unload`, `test` — each one logged to `data/actions.jsonl` |
| Roles | Assign a model per role (`chat`, `code`, `vision`, `embedding`, `fast`, `quality`, `experimental`) |
| Registry | Aggregates several providers (Ollama, any OpenAI-compatible endpoint) and reports drift |
| Gateway | `POST /v1/chat/completions` and `GET /v1/models` — an app can call `model: "code"` and get routed to the assigned model |
| Observability | Every gateway request stored in a local SQLite file, with a dashboard (counts, error rate, p50/p95, per model/provider/app) |
| Evals | Deterministic check suites (no LLM judge, generated code is never executed) with a per-role scoreboard |
| RAG | Local ingestion → retrieval → generation, with cited sources and an eval bridge to compare RAG on/off |
| Adaptation | LoRA/QLoRA job orchestration against an allowlisted external runner, measured against the baseline |

Design rules the code holds to: nothing is invented (a missing model is an
error, never a silent fallback), the baseline is never overwritten, and
"active in the registry" is never presented as "served by the gateway".

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) running locally (default `http://127.0.0.1:11434`)

## Run

```bash
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 22050
```

Then open `http://127.0.0.1:22050/`.

## Configuration

Everything is read from the environment; defaults are safe.

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `HOST` / `PORT` | `127.0.0.1` / `22050` | Bind address |
| `DATA_DIR` | `data` | Local state (action log, SQLite, roles, RAG, datasets) |
| `ACTIONS_ENABLED` | `1` | `0` disables every control action |
| `ACTION_TIMEOUT_S` | `60` | Timeout for a control action |
| `GATEWAY_ENABLED` | `1` | `0` returns 404 on `/v1/*` |
| `GATEWAY_DEFAULT_ROLE` | `chat` | Role used when a request omits the model |
| `LOG_PROMPTS` | `0` | Prompt bodies are **not** stored unless set to `1` |
| `EVALS_DIR` | packaged suites | Override the eval suite directory |
| `RAG_EMBED_MODEL` | `nomic-embed-text` | Embedding model, must be installed |
| `RAG_TOP_K` / `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | `4` / `800` / `100` | Retrieval tuning |
| `TRAIN_BASE_MODEL` | *(empty)* | Empty means a job must pass `base_model` explicitly |
| `TRAIN_RUNNER` | *(empty)* | Empty means training jobs stay in dry-run |

`data/` is gitignored: ingested documents, datasets, adapters and logs never
leave the machine.

## Using the gateway from another app

```bash
curl http://127.0.0.1:22050/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'x-cockpit-app: my-app' \
  -d '{"model": "code", "messages": [{"role": "user", "content": "hello"}]}'
```

`model` accepts a role (`code`, `role:code`) or a real model name. The
response carries an `x_cockpit_route` field showing exactly what was resolved,
and the request lands in the dashboard.

## Linux desktop

LLM Cockpit ships as a desktop application: its window engine (Qt WebEngine)
travels inside the package, so the machine needs no browser and no Python.

```bash
uv sync --extra desktop
uv run python scripts/build_deb.py
```

The `.deb` lands in `dist/linux/` (~190 MB packed, ~590 MB installed — an
embedded browser engine is most of it). Local install without root:

```bash
uv run python scripts/build_linux_bundle.py
uv run python scripts/install_linux.py   # scripts/uninstall_linux.py to revert
```

The launcher picks a free port in `22050-22099`, starts the server, and opens
a dedicated window — no tab, no address bar. If the Qt bindings are missing
(a plain `uv sync` without the `desktop` extra), it degrades in two steps:
a Chromium-family browser in `--app` mode, then the default browser.

Qt comes from **PySide6 under LGPLv3**, kept dynamically linked in the
PyInstaller `onedir` bundle so the Qt libraries remain replaceable, which is
what the LGPL requires. The cockpit's own code stays MIT.

## User guide

A detailed walkthrough of every panel — inventory, roles, gateway, dashboard,
evals, RAG, LoRA orchestration, configuration and troubleshooting — is in
[`docs/GUIDE_UTILISATEUR.md`](docs/GUIDE_UTILISATEUR.md) (French).

## Tests

```bash
uv run pytest
uv run ruff check .
```

The suite is fully offline: HTTP calls to providers are mocked, no model is
required to run it.

## License

MIT. See [LICENSE](LICENSE).

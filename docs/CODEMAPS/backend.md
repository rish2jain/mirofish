# Backend codemap

**Last updated:** 2026-04-01

**Entry points:** `backend/run.py`, `backend/app/__init__.py`

## Architecture

```text
run.py
  → create_app(Config [, orchestration])
       extensions: llm_backend, graph_storage
       blueprints:
         /api/graph      → graph_bp    (api/graph.py)
         /api/simulation → simulation_bp (api/simulation/*.py)
         /api/report     → report_bp   (api/report.py)
         /api/templates  → templates_bp (api/templates.py)
         /api/hooks      → hooks_bp    (api/hooks.py)
       SPA fallback: frontend/dist via Flask static (production build)
```

## API blueprints (prefixes)

### `/api/graph` — `backend/app/api/graph.py`

| Area | Routes (representative) |
| ---- | ----------------------- |
| Projects | `GET/DELETE /project/<id>`, `GET /project/list`, `POST /project/<id>/reset` |
| Ingest / ontology | `POST /ontology/generate` (multipart: files + form fields) |
| Graph build | `POST /build` (JSON `project_id`, optional chunking) |
| Tasks | `GET /task/<id>`, `GET /task/<id>/sse`, `GET /tasks` |
| Graph data | `GET /nodes`, `GET /edges`, `GET /data/<graph_id>`, `DELETE /delete/<graph_id>` |
| Bundles / snapshots | `GET|POST` import/export bundle, `POST` snapshot, `GET` snapshots, `POST` graph-diff |
| Query | `POST /query` — read-only Cypher against Kuzu (when backend is Kuzu) |

Uses `WorkbenchSession`, `ProjectManager`, `GraphBuilderService`, `workflow_bundle`.

### `/api/simulation` — `backend/app/api/simulation/`

Submodules are imported from `simulation/__init__.py` (side-effect registration on `simulation_bp`).

| Module | Responsibility |
| ------ | ---------------- |
| `management.py` | Create, prepare, get, list, history, compare, profiles, config, script download, `generate-profiles` |
| `run_control.py` | Start/stop/delete, run-status (+ SSE stream), timeline, posts, comments, agent-stats, actions |
| `entities.py` | List/get entities by graph |
| `interview.py` | Agent interview, env lifecycle (`env-status`, `close-env`) |
| `extras.py` | Fork, cost estimate |
| `batch.py` | Batch create |
| `common.py` | Shared helpers |

### `/api/report` — `backend/app/api/report.py`

Generate and poll status, CRUD-style access, chat (+ stream), sections/progress, logs (polling + SSE), compare, PDF, tool endpoints (`/tools/search`, `/tools/statistics`).

### `/api/templates` — `backend/app/api/templates.py`

List/get templates; `PUT`/`POST` writes when allowed (e.g. `MIROFISH_ALLOW_TEMPLATE_WRITE` / debug).

### `/api/hooks` — `backend/app/api/hooks.py`

`GET/POST /webhooks`, `DELETE /webhooks/<sub_id>` — requires service API key (`MIROFISH_API_KEY`). Implements outbound webhook registry (`webhook_service`).

## Layers below API

```text
api/  →  tools/  →  services/  →  core/ + resources/ + utils/
```

| Layer | Role |
| ----- | ---- |
| `backend/app/tools/` | `GenerateOntologyTool`, `BuildGraphTool`, `PrepareSimulationTool`, `RunSimulationTool`, `GenerateReportTool`, `simulation_support` |
| `backend/app/services/` | Graph (storage, builder, memory, tools), simulation (manager, runner, IPC, config, profiles), report (agent, manager, prompts, models, logging, simulation index), entity pipeline, ontology, text, webhooks, workflow bundle |
| `backend/app/core/` | `llm_orchestrator`, `workbench_session`, session/task managers, `resource_loader` |
| `backend/app/resources/` | Stores: projects, documents, graph (Kuzu), simulations, reports, LLM provider adapter |
| `backend/app/utils/` | LLM client, cache, auth helpers, background tasks, logging, parsers, schemas |

## Data / graph storage

- `GRAPH_BACKEND`: `kuzu` (default, `KUZU_DB_PATH`) or `json` (`DATA_DIR`).
- Uploads and simulation artifacts under `backend/uploads/` (see `Config`).

## Related

- [frontend.md](./frontend.md) — UI routes and `src/api/*` clients  
- [integrations.md](./integrations.md) — Docker, MCP, webhook delivery  

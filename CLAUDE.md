# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is MiroFish

Swarm intelligence prediction engine. Upload documents, MiroFish extracts entities into a knowledge graph, generates AI agent personas, runs dual-platform social media simulations (Twitter + Reddit via OASIS), and produces analysis reports via a ReACT agent. Fork of 666ghj/MiroFish — fully English, local KuzuDB, multi-provider LLM support.

## Commands

```bash
# Setup
cp .env.example .env          # Configure LLM provider (or leave blank for CLI auto-detection)
npm run setup:all              # Install Node + Python (uv) deps
npm run dev                    # Run backend (5001) + frontend (3000) concurrently

# Individual services
npm run backend                # cd backend && uv run python run.py
npm run frontend               # cd frontend && npm run dev

# Frontend only
cd frontend && npm run build   # Production build

# Backend only
cd backend && uv run python run.py

# Tests
cd backend && uv run pytest                          # All tests
cd backend && uv run pytest tests/test_twitter_profiles.py  # Single test

# MCP Server (for Claude Code integration)
cd mcp-server && npm install   # First time only
# Then add to .mcp.json or Claude Code picks it up automatically

# Docker
docker compose up -d --build

# Optional: PDF export support
cd backend && uv pip install "mirofish-backend[pdf]"
```

## Architecture

**Frontend:** Vue 3 + Vite + D3.js — port 3000, proxies `/api` to backend at 5001.

**Backend:** Python Flask — port 5001. Uses `uv` for dependency management (`pyproject.toml`).

### Backend layers (top → bottom)

```
api/           Thin Flask blueprints (graph_bp, simulation_bp, report_bp, templates_bp)
  ↓
tools/         Composable workbench operations (generate_ontology, build_graph,
               prepare_simulation, run_simulation, generate_report)
  ↓
services/      Core business logic (15 modules — the bulk of the codebase)
  ↓
core/          Workbench session management, task tracking, resource loading,
               LLM orchestrator (CLI auto-detection)
  ↓
resources/     Pluggable adapters (projects, documents, graphs, simulations, reports)
  ↓
utils/         LLM client, file parser, retry, logging, Kuzu pagination, cost estimator
```

### LLM Orchestrator (`core/llm_orchestrator.py`)

On startup, auto-detects the best available LLM backend:
1. **Claude CLI** (`claude` on PATH) — uses Claude Code subscription
2. **Codex CLI** (`codex` on PATH) — uses Codex subscription
3. **Gemini CLI** (`gemini` on PATH) — uses Gemini subscription
4. **API fallback** — requires `LLM_API_KEY` in `.env`

If `LLM_PROVIDER` is explicitly set, auto-detection is skipped. The orchestrator result is stored in `app.extensions["llm_backend"]` and summarized via `/health` (`llm_backend`, `llm_model`; `llm_binary` path only when `FLASK_DEBUG` or `EXPOSE_BINARY_PATH` is set, otherwise `llm_cli_on_path`).

### Key service modules

- **llm_client.py** — Multi-provider abstraction (OpenAI, Anthropic, Claude CLI, Codex CLI, Gemini CLI). All LLM calls go through this.
- **graph_storage.py** — Abstract `GraphStorage` with KuzuDB and JSON backends. Selected via `GRAPH_BACKEND` env var.
- **graph_db.py** — Compatibility facade over per-graph storage instances.
- **entity_extractor.py** — LLM-based entity/relationship extraction from documents.
- **simulation_runner.py** — Runs OASIS simulations in isolated subprocesses with IPC via JSON files.
- **simulation_ipc.py** — Inter-process communication for simulation subprocess.
- **report_agent.py** — ReACT agent with tool-calling loop for report generation (~106KB, largest file).
- **graph_tools.py** — Search, interview, and analysis tools used by the report agent (~68KB).
- **cost_estimator.py** — Token cost estimation for CLI and API modes.

### Data pipeline

```
Document upload → LLM ontology extraction → Knowledge graph (KuzuDB)
  → Entity filtering → Agent persona generation (LLM)
  → OASIS dual-platform simulation (Twitter + Reddit subprocess)
  → Graph memory updates → Report generation (ReACT agent)
  → Interactive chat / agent interviews
  → PDF export / scenario A/B comparison
```

### State persistence

- Workbench sessions: `backend/uploads/workbench_sessions/`
- Task state: `backend/uploads/tasks/`
- Graph data: `backend/data/kuzu_db/` (KuzuDB) or `backend/data/json_graphs/` (JSON)
- Uploaded files: `backend/uploads/`
- Simulation data: `backend/uploads/simulations/`

## Frontend routes

| Path | View | Purpose |
|------|------|---------|
| `/` | Home | Landing page, file upload modal, template picker |
| `/process/:projectId` | MainView | 5-step workflow (graph → sim → report) |
| `/simulation/:simulationId` | SimulationView | Simulation overview |
| `/simulation/:simulationId/start` | SimulationRunView | Live simulation progress |
| `/report/:reportId` | ReportView | Generated report |
| `/interaction/:reportId` | InteractionView | Agent interviews |

## API structure

Four Flask blueprints under `/api/`:
- **`/api/graph/`** — Document upload, ontology generation, graph building, project data
- **`/api/simulation/`** — Simulation CRUD, prepare, start/stop, profiles, posts, timeline, agent stats, fork, cost estimate
- **`/api/report/`** — Report generation, chat (ReACT), compare, PDF export
- **`/api/templates/`** — Consulting simulation templates (regulatory impact, M&A, crisis comms)

### Key newer endpoints

- `POST /api/simulation/fork` — Clone a simulation with modified params (A/B scenario testing)
- `GET /api/simulation/<id>/cost-estimate` — Token cost estimate for a simulation
- `POST /api/report/compare` — Side-by-side comparison of two reports
- `GET /api/report/<id>/pdf` — Export report as branded PDF (requires `weasyprint`)
- `GET /api/templates/` — List consulting templates
- `GET /api/templates/<id>` — Get a single template

## LLM providers

Set `LLM_PROVIDER` in `.env`: `openai`, `anthropic`, `claude-cli`, `codex-cli`, `gemini-cli`, or **leave blank for auto-detection**. CLI providers use stdin-based prompting (no SDK). Docker deployments use proxy sidecars for bounded concurrency.

## CLI proxies (Docker only)

Three OpenAI-compatible FastAPI sidecars sharing the same `/v1/chat/completions` contract:

| Proxy | Directory | Port | CLI Command |
|-------|-----------|------|-------------|
| codex-proxy | `codex-proxy/` | 11435 | `codex exec --skip-git-repo-check` |
| claude-proxy | `claude-proxy/` | 11436 | `claude -p --output-format json` |
| gemini-proxy | `gemini-proxy/` | 11437 | `gemini -p` |

Each configured via `*_PROXY_WORKERS` and `*_PROXY_TIMEOUT` env vars.

## Consulting templates

JSON configs in `backend/templates/` pre-fill simulation requirements and entity type hints:
- `regulatory_impact.json` — Regulatory/policy impact analysis
- `ma_reaction.json` — M&A reaction forecasting
- `crisis_comms.json` — Crisis communications simulation

## MCP Server

`mcp-server/` is a Node.js MCP server for Claude Code integration. Tools:
- `list_templates` — List simulation templates
- `run_simulation` — Full pipeline (create → prepare → start)
- `get_report` — Fetch or generate report
- `chat_with_report` — Chat with report agent
- `inject_variable` — Fork simulation with changes
- `get_simulation_status` — Check progress

Auto-discovered via `.mcp.json` at project root.

## Key dependencies

- **camel-oasis** (0.2.5) + **camel-ai** (0.2.78) — Multi-agent social simulation
- **kuzu** — Embedded graph database (no external service)
- **PyMuPDF** — PDF parsing
- **pydantic** — Data validation
- **waitress** — Production WSGI server
- **d3** (v7) — Graph visualization in frontend
- **weasyprint** (optional) — PDF export
- **@modelcontextprotocol/sdk** — MCP server for Claude Code

## Conventions

- Backend: snake_case modules/functions, PascalCase classes
- Frontend: PascalCase Vue components, camelCase JS modules
- Workflow steps in frontend are prefixed `Step1`–`Step5` in component names
- API modules mirror frontend steps: graph → simulation → report
- Config validation happens at startup in `Config.validate()`
- The backend is being refactored toward a "pi-style" shape: one workbench session core, pluggable resource adapters, composable tools, and thin API shells

# CLI-First LLM Orchestration Design

## Overview

Make MiroFish automatically detect and prefer local CLI tools (Claude → Codex → Gemini) over cloud APIs, add consulting templates, scenario A/B forking, PDF export, and an MCP server for Claude Code integration.

## Phase 0: LLM Orchestrator

**New module:** `backend/app/core/llm_orchestrator.py`

### Behavior

1. On startup, run `shutil.which()` for `claude`, `codex`, `gemini` in priority order.
2. Produce a `LLMBackend` enum: `claude_cli | codex_cli | gemini_cli | api`.
3. If `.env` explicitly sets `LLM_PROVIDER`, skip auto-detection (explicit config wins).
4. Auto-detection only runs when `LLM_PROVIDER` is empty/unset.

### Integration

- `Config.validate()` — if orchestrator found a CLI, skip API key requirement.
- `create_app()` — calls orchestrator, stores result in `app.extensions["llm_backend"]`.
- `/health` — returns `llm_backend` and `llm_model`; filesystem path `llm_binary` only in debug or when `EXPOSE_BINARY_PATH` is set (otherwise `llm_cli_on_path` boolean).
- `LLMClient` — gains `gemini-cli` provider path.

### Data Model

```python
class LLMBackend(str, Enum):
    CLAUDE_CLI = "claude-cli"
    CODEX_CLI = "codex-cli"
    GEMINI_CLI = "gemini-cli"
    API = "api"

@dataclass(frozen=True)
class OrchestrationResult:
    backend: LLMBackend
    binary_path: str | None
    provider: str
    base_url: str
    model: str
    api_key: str
```

## Phase 1: CLI Proxies + Gemini CLI

### Gemini CLI in LLMClient

Add `_chat_gemini_cli()` to `LLMClient`. Uses `gemini -p "prompt"` for non-interactive prompting. Add `gemini-cli` to `CLI_PROVIDERS` in `oasis_llm.py`.

### Docker Proxies

Three OpenAI-compatible FastAPI sidecars sharing identical contract:

- `POST /v1/chat/completions` — accepts OpenAI chat format, returns OpenAI response format
- `GET /v1/models` — lists available models
- `GET /health` — health check

| Proxy | Directory | CLI Command | Port |
|-------|-----------|-------------|------|
| claude-proxy | `claude-proxy/` | `claude -p --output-format json` via stdin | 11436 |
| codex-proxy | `codex-proxy/` | `codex exec --skip-git-repo-check` via stdin | 11435 |
| gemini-proxy | `gemini-proxy/` | `gemini -p` via stdin | 11437 |

**Local dev:** Direct CLI subprocess calls (existing pattern). No proxy needed.
**Docker:** Proxies provide bounded concurrency via semaphore.

### docker-compose.yml Updates

Add `claude-proxy` and `gemini-proxy` services. Main `mirofish` service gets orchestrator-driven env vars.

## Phase 2: Consulting Templates

### Template Format

```json
{
  "id": "regulatory_impact",
  "name": "Regulatory Impact Analysis",
  "description": "Predict public and market reaction to regulatory changes",
  "default_requirement": "Analyze public reaction to this regulation over 60 days",
  "suggested_rounds": 15,
  "entity_type_hints": ["regulator", "company", "analyst", "consumer", "politician"],
  "system_prompt_addition": "Focus on regulatory compliance, market dynamics, and stakeholder reactions."
}
```

### New Files

- `backend/templates/regulatory_impact.json`
- `backend/templates/ma_reaction.json`
- `backend/templates/crisis_comms.json`

### API

- `GET /api/templates` — list all templates
- `GET /api/templates/<id>` — get single template

### Frontend

Template picker dropdown in `Step1GraphBuild.vue` upload flow. Selecting a template pre-fills the requirement text and configures entity type hints.

## Phase 3: Scenario A/B + Reporting

### Scenario Forking

- `POST /api/simulation/fork` — clone a simulation with modified parameters.
  - Request: `{ simulation_id, changes: { requirement?, max_rounds?, variable_overrides? } }`
  - Response: new simulation ID with `forked_from` metadata.

### Report Comparison

- `POST /api/report/compare` — structured diff between two reports.
  - Request: `{ report_id_a, report_id_b }`
  - Response: side-by-side comparison with divergence highlights.

### PDF Export

- `GET /api/report/<id>/pdf` — render report as branded PDF.
- Uses `weasyprint` for HTML-to-PDF conversion.
- Branded header/footer with MiroFish logo and generation metadata.

### Cost Estimator

- `backend/app/utils/cost_estimator.py` — estimates token costs.
- Works in both CLI and API modes (CLI uses estimated tokens × published prices).
- Exposed via `GET /api/simulation/<id>/cost-estimate`.

## Phase 4: MCP Server

### Structure

The MCP server is implemented as **plain JavaScript** (not TypeScript). Tools are registered on the `McpServer` instance in a single entry file rather than a separate `tools/` package layout.

```
mcp-server/
  package.json
  src/
    index.js          # MCP server entry; tools (list_templates, run_simulation, get_report, inject_variable, …) defined here
  .mcp.json           # Claude Code integration config
```

(Older drafts assumed a TypeScript split such as `index.ts` and `tools/*.ts`; the repository uses `src/index.js` only.)

### Tools

| Tool | Description | Backend Endpoint |
|------|-------------|-----------------|
| `mirofish.list_templates` | List available simulation templates | `GET /api/templates` |
| `mirofish.run_simulation` | Create + prepare + start a simulation | `POST /api/simulation/create` → `prepare` → `start` |
| `mirofish.get_report` | Get a report by ID or generate new | `GET /api/report/<id>` |
| `mirofish.inject_variable` | Fork simulation with changed variable | `POST /api/simulation/fork` |

### Configuration

`.mcp.json` at project root for Claude Code auto-discovery:
```json
{
  "mcpServers": {
    "mirofish": {
      "command": "node",
      "args": ["mcp-server/src/index.js"],
      "env": { "MIROFISH_API_URL": "http://localhost:5001" }
    }
  }
}
```

## File Change Summary

### New Files
- `backend/app/core/llm_orchestrator.py`
- `backend/app/core/__init__.py` (if missing)
- `backend/app/utils/cost_estimator.py`
- `backend/app/api/templates.py`
- `backend/templates/regulatory_impact.json`
- `backend/templates/ma_reaction.json`
- `backend/templates/crisis_comms.json`
- `claude-proxy/main.py`
- `gemini-proxy/main.py`
- `docker/cli-proxy.Dockerfile` (multi-stage build: targets `claude-proxy`, `gemini-proxy`; stubs in `claude-proxy/Dockerfile` and `gemini-proxy/Dockerfile` point here)
- `mcp-server/` (full directory)

### Modified Files
- `backend/app/utils/llm_client.py` — add `gemini-cli` provider
- `backend/app/utils/oasis_llm.py` — add `gemini-cli` to CLI_PROVIDERS
- `backend/app/config.py` — update validate() for orchestrator
- `backend/app/__init__.py` — call orchestrator, enrich /health
- `backend/app/api/__init__.py` — register templates blueprint
- `backend/app/api/simulation.py` — add fork endpoint
- `backend/app/api/report.py` — add compare + PDF endpoints
- `docker-compose.yml` — add claude-proxy, gemini-proxy services
- `.env.example` — document new options
- `frontend/src/components/Step1GraphBuild.vue` — template picker
- `CLAUDE.md` — document new architecture

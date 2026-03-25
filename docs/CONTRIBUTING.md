# Contributing to MiroFish

## Prerequisites

- Node.js 18+
- Python 3.11–3.12
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- At least one LLM provider: a CLI tool (Claude, Codex, or Gemini) on PATH, or an API key

## Setup

```bash
cp .env.example .env       # configure LLM provider or leave blank for auto-detection
npm run setup:all          # install Node + Python deps
npm run dev                # start backend + frontend concurrently
```

## Available Commands

<!-- AUTO-GENERATED: scripts -->

### Root (`package.json`)

| Command              | Description                                           |
| -------------------- | ----------------------------------------------------- |
| `npm run setup`      | Install root Node deps + frontend Node deps           |
| `npm run setup:backend` | Install Python deps via `uv sync`                  |
| `npm run setup:all`  | Run both `setup` and `setup:backend`                  |
| `npm run dev`        | Run backend + frontend concurrently (hot reload)      |
| `npm run backend`    | Start Flask backend only (`uv run python run.py`)     |
| `npm run frontend`   | Start Vite dev server only                            |
| `npm run build`      | Production build of the Vue frontend                  |

### Frontend (`frontend/package.json`)

| Command                 | Description                            |
| ----------------------- | -------------------------------------- |
| `npm run dev`           | Vite dev server with hot reload        |
| `npm run build`         | Vite production build                  |
| `npm run preview`       | Preview production build locally       |

### Backend (`backend/pyproject.toml`)

| Command                                       | Description                        |
| --------------------------------------------- | ---------------------------------- |
| `cd backend && uv run python run.py`          | Start Flask backend                |
| `cd backend && uv run pytest`                 | Run all tests                      |
| `cd backend && uv run pytest tests/<file>.py` | Run a single test file             |

### MCP Server (`mcp-server/package.json`)

| Command              | Description                                  |
| -------------------- | -------------------------------------------- |
| `npm run start`      | Start the MCP stdio server                   |

<!-- /AUTO-GENERATED: scripts -->

## Project Structure

```text
frontend/          Vue 3 + Vite + D3.js
backend/           Python Flask API + services
  app/api/         REST endpoints (graph, simulation, report, templates)
  app/core/        LLM orchestrator, workbench sessions, task tracking
  app/services/    Business logic (15 modules)
  app/utils/       LLM client, cost estimator, file parser
  templates/       Consulting simulation templates (JSON)
codex-proxy/       Docker sidecar for Codex CLI
claude-proxy/      Docker sidecar for Claude CLI
gemini-proxy/      Docker sidecar for Gemini CLI
mcp-server/        MCP server for Claude Code integration
```

## Testing

```bash
cd backend && uv run pytest                          # all tests
cd backend && uv run pytest tests/test_twitter_profiles.py -v  # single file, verbose
```

Test files live in `backend/tests/`. When adding new functionality, add corresponding tests.

## Code Style

- **Python**: snake_case for modules/functions, PascalCase for classes
- **JavaScript/Vue**: PascalCase for Vue components, camelCase for JS modules
- **Immutability**: prefer creating new objects over mutating existing ones
- **File size**: aim for 200–400 lines, max 800

## PR Checklist

- [ ] Code compiles and lints clean (`python -m py_compile` for Python, `npm run build` for frontend)
- [ ] Tests pass (`uv run pytest`)
- [ ] New environment variables documented in `.env.example`
- [ ] New API endpoints documented in `docs/API.md`
- [ ] No hardcoded secrets or API keys

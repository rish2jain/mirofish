# Runbook

## Deployment

### Local Development

```bash
cp .env.example .env
npm run setup:all
npm run dev
```

Frontend: `http://localhost:3000` | Backend: `http://localhost:5001`

### Docker (Production)

```bash
cp .env.example .env
# Edit .env as needed (or leave LLM_PROVIDER blank for CLI auto-detection)
docker compose up -d --build
```

The Dockerfile is a multi-stage build:
1. **Stage 1** (Node 20): builds the Vue frontend → produces `frontend/dist`
2. **Stage 2** (Python 3.11): installs Python deps, copies backend + frontend dist, exposes port 5001

### Docker Services

| Service        | Port  | Purpose                                     |
| -------------- | ----- | ------------------------------------------- |
| `mirofish`     | 5001  | Main Flask app (backend + frontend)         |
| `codex-proxy`  | 11435 | OpenAI-compatible proxy for Codex CLI       |
| `claude-proxy` | 11436 | OpenAI-compatible proxy for Claude CLI      |
| `gemini-proxy` | 11437 | OpenAI-compatible proxy for Gemini CLI      |

### MCP Server

```bash
cd mcp-server && npm install   # first time
# Auto-discovered via .mcp.json by Claude Code
```

## Health Checks

| Endpoint                          | Expected Response                                     |
| --------------------------------- | ----------------------------------------------------- |
| `GET /health`                     | `{"status":"ok","service":"MiroFish Backend","llm_backend":"...","llm_model":"..."}` |
| `GET http://localhost:11435/health` | `{"status":"ok","workers":4}` (codex-proxy)          |
| `GET http://localhost:11436/health` | `{"status":"ok","workers":4}` (claude-proxy)         |
| `GET http://localhost:11437/health` | `{"status":"ok","workers":4}` (gemini-proxy)         |

## Common Issues

### "No local LLM CLIs found on PATH"

The LLM orchestrator couldn't find `claude`, `codex`, or `gemini` on PATH, and no API key is configured.

**Fix:** Either install a CLI tool, or set `LLM_API_KEY` and `LLM_PROVIDER` in `.env`.

### Simulation subprocess timeout

OASIS simulations run in isolated subprocesses. If they time out, the simulation status shows `failed`.

**Fix:** Reduce `OASIS_DEFAULT_MAX_ROUNDS` or check LLM provider latency. CLI providers are slower than API providers — consider reducing rounds to <20 for CLI mode.

### PDF export returns HTML instead of PDF

`weasyprint` is an optional dependency. Without it, the `/api/report/<id>/pdf` endpoint falls back to HTML.

**Fix:** Install the PDF extras: `cd backend && uv pip install "mirofish-backend[pdf]"`

### Codex/Claude proxy "binary not found" in Docker

The proxy containers mount CLI binaries from the host via volume mounts.

**Fix:** Ensure the CLI is installed and authenticated on the Docker host. Check volume mount paths in `docker-compose.yml` match your host's binary locations.

### Graph storage errors

KuzuDB is the default embedded graph database. If you see `StorageError`, check disk space and permissions on `KUZU_DB_PATH`.

**Fix:** Verify `backend/data/kuzu_db/` is writable. Switch to JSON backend with `GRAPH_BACKEND=json` as a fallback.

## Rollback

### Local

```bash
git log --oneline -10            # find the commit to roll back to
git checkout <commit-hash> -- .  # restore files
npm run dev                      # restart
```

### Docker

```bash
docker compose down
git checkout <previous-tag>
docker compose up -d --build
```

## Data Locations

| Data                  | Path                                      |
| --------------------- | ----------------------------------------- |
| Uploaded documents    | `backend/uploads/`                        |
| Workbench sessions    | `backend/uploads/workbench_sessions/`     |
| Task state            | `backend/uploads/tasks/`                  |
| Simulation data       | `backend/uploads/simulations/`            |
| KuzuDB graph data     | `backend/data/kuzu_db/`                   |
| JSON graph data       | `backend/data/json_graphs/`               |

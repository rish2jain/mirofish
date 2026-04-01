# Integrations codemap

**Last updated:** 2026-04-01

## Docker Compose (`docker-compose.yml`)

| Service | Purpose |
| ------- | ------- |
| `mirofish` | Main image: Flask + built Vue static; app port **5001**; mounts `backend/uploads`, `backend/data`; optional Traefik labels for `synth.scty.org` |
| `codex-proxy` | OpenAI-compatible proxy → Codex CLI; host port **11435** |
| `claude-proxy` | Built from `docker/cli-proxy.Dockerfile` (target `claude-proxy`); port **11436** |
| `gemini-proxy` | Same Dockerfile, target `gemini-proxy`; port **11437** |

The app service typically points `LLM_BASE_URL` at a proxy (e.g. `http://codex-proxy:11435/v1`). Proxies need host-mounted CLI binaries and auth dirs (see Compose `volumes`).

**Network:** `traefik` is declared `external: true` (create before deploy if you use those labels).

**Health:** `GET http://127.0.0.1:5001/health` on the app container; each proxy exposes `GET /health`.

## MCP server (`mcp-server/`)

- Transport: stdio (`@modelcontextprotocol/sdk`).
- Base URL: env `MIROFISH_API_URL` (default `http://localhost:5001`).
- Tools (see `mcp-server/src/index.js`): `list_templates`, `run_simulation`, `get_report`, `chat_with_report`, `inject_variable`, `get_simulation_status`.
- Repo root `.mcp.json` is used for Claude Code discovery.

## Webhooks (outbound)

- Registration API under `/api/hooks/webhooks` (Bearer / service key — see `backend/app/utils/api_auth.py` and `MIROFISH_API_KEY`).
- Implementation: `backend/app/services/webhook_service.py`; events such as simulation completion/failure with optional HMAC (`X-MiroFish-Signature`).

## Related

- [backend.md](./backend.md) — hook blueprint and simulation/report APIs  
- [frontend.md](./frontend.md) — Workflow tools UI for webhook registration  

# MiroFish codemaps

**Last updated:** 2026-04-01

High-level maps of the repo. Paths are relative to the repository root.

| Document | Scope |
| -------- | ----- |
| [backend.md](./backend.md) | Flask app factory, API blueprints, `services/`, `tools/`, `core/`, `resources/` |
| [frontend.md](./frontend.md) | Vue routes, API client modules, main views |
| [integrations.md](./integrations.md) | Docker Compose, MCP server, webhooks |

**Entry points**

- Backend: `backend/run.py` → `backend/app/__init__.py` (`create_app`)
- Frontend dev: `frontend/src/main.js`, `frontend/src/App.vue`, `frontend/src/router/index.js`
- MCP: `mcp-server/src/index.js` (stdio server; targets `MIROFISH_API_URL`, default `http://localhost:5001`)

**Regeneration**

There is no `npx tsx scripts/codemaps/generate.ts` in this repo. Update these markdown files when blueprints, routes, or Compose services change.

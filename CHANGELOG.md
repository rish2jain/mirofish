# Changelog

All notable changes for this fork are tracked here (high level).

## Unreleased

- Backend: split simulation API into `app/api/simulation/` subpackage; split report agent into `report_models`, `report_logging`, `report_prompts`, `report_manager`; `SimulationRunner` class-level dicts guarded with an `RLock`; adaptive monitor polling and in-memory run-state eviction for completed simulations; template JSON validated with Pydantic on load; graph tool retries use shared `RetryableAPIClient`.
- Frontend: Pinia (`ui`, `workbench` stores), shared `useWorkflowLayout`, extracted `renderMarkdown` utility, debounced graph resize + `ResizeObserver`, templates API client fix, toast notifications instead of `alert`, main workflow error banner, removed unused `Process.vue`.
- Tooling: Docker image installs backend deps via `uv sync --frozen`; CI runs backend `pytest` and frontend `vitest`; MCP `pollSimulation` uses exponential backoff; `docker-compose` healthcheck for the main app service.

# MiroFish Improvement Plan

> Research audit conducted 2026-03-31 across backend, frontend, and infrastructure.  
> **Path note:** Application code lives under **`backend/app/`** (e.g. `app/services/`, `app/api/`). Older references to `api/` or top-level `services/` mean those paths.

---

## Non-P0 implementation status (2026-03-31)

**Deployment scope note:** this install is used as a **single-user, local-only tool**. P0 items below remain relevant if MiroFish is exposed on a network or shared with others, but they are intentionally deferred for this deployment profile.

The following **non-P0** buckets were executed in a consolidated pass (plus follow-ups). Use this section as the source of truth for what changed; sections P1–P5 still list original findings for context.

**Follow-up (same day):** webhook **DLQ** on disk (`uploads/webhooks/dlq/*.jsonl`); **GraphPanel** incremental D3 when the same `graph_id` gains nodes/edges + skip redraw when node/edge identity sets are unchanged (`utils/graphLayout.js`); **focus/center** on selected node; **`ReportOutlinePanel.vue`** shared by Step4/Step5; **`simulation_runner`** action-log reader uses narrower `except`; tests for DLQ, `ReportAgent.plan_outline` (mocked), `_check_all_platforms_completed`, `graphLayout`; **`// @ts-check`** on `src/api/simulation.js`.

| Bucket | Delivered (summary) | Still worth doing |
|--------|---------------------|-------------------|
| **P1 backend** | `report_agent` split into `report_models`, `report_logging`, `report_prompts`, `report_manager` + slimmer agent; simulation API as `app/api/simulation/` package; `SimulationRunner` locking; graph retry via shared client; `print` → logger in OASIS modules; unused `asyncio` removed from runner; **action log tail:** narrow catch to `(OSError, json.JSONDecodeError, UnicodeDecodeError)` | Narrow remaining broad `except Exception` in `report.py`, `graph_tools.py`, etc.; trim `services/__init__.py` if import-time work hurts |
| **P1 frontend** | `Process.vue` removed; shared `utils/markdown.js`; `templates.js` unwrap fix; Pinia stores; toast + MainView error surfacing; `useWorkflowLayout`; GraphPanel debounce + `ResizeObserver` + **500-node cap**; **`graphLayout.js`** + incremental merge + identical-payload skip; node **Center** control; **`ReportOutlinePanel.vue`** (outline column for Step4 + Step5) with improved section **a11y** when collapsible | Further split **Step2** and remaining mega-sections inside Step4/Step5 (timeline, logs, interaction chrome); replace remaining `alert()` if any |
| **P2** | **~25** backend test modules under `backend/tests/` (incl. hooks/webhooks, workflow bundle, LLM client slice, graph builder, simulation manager, **`test_webhook_dlq.py`**, **`test_report_agent_plan_outline.py`**, **`test_simulation_runner_platforms.py`**, compare APIs, graph query validate, phase completion); **Vitest** — `markdown`, `api/report.test.js`, `api/simulation.test.js`, **`utils/graphLayout.test.js`**; **ESLint**; **Playwright smoke**; **CI** runs `pytest`, backend **`ruff check app tests`**, `npm test`, **`npm run lint`**, **`npm run test:e2e`** | Deeper `SimulationRunner` IPC/integration tests; bundle round-trip / more SSE integration tests |
| **P3** | **SSE** `GET /api/simulation/<id>/run-status/stream`; **Step3** `EventSource` + fallback (`VITE_SIMULATION_SSE`); **report logs** `GET /api/report/<id>/agent-log/sse` + `console-log/sse`; **Step4** optional `EventSource` (`VITE_REPORT_LOG_SSE`, default on); MCP `pollSimulation` backoff; **GraphPanel:** incremental force simulation when structure is a strict superset (reuse positions), not full enter/update/exit | Strict D3 enter/update/exit pattern; graph build / prepare progress over SSE (Step2/MainView still mostly poll) |
| **P4** | Dockerfile **`uv sync --frozen`**; `mcp-server/package-lock.json`; English root `package.json` description; **CHANGELOG**; compose **healthcheck**; template **Pydantic** validation; fourth template in **CLAUDE.md**; **README** “Integrations & ops” for new APIs; `LLM_BOOST_*` documented in `docs/ENV.md`; `docs/ENV.md` regenerated from `scripts/generate_env_docs.py`; graceful shutdown for long-lived builder threads | — |
| **P5** | **Report compare**: `/report/compare`, section table when API returns `sections_*`, Compare nav; **Tools** `/tools` (export/import bundle, snapshots/diff, batch sims, webhooks UI); **Template editor** `/templates/edit` form-first UI; **GraphPanel** read-only **Query** modal → `POST /api/graph/query` (Kuzu); Home nav links; **simulation-level compare** `/simulation/compare` (timelines, posts, delta) | Broader **JSDoc / `@ts-check`** on API modules; more **rem** + aria pass on workflow chrome |
| **Feature roadmap** | **Bundles:** `GET …/export-bundle`, `…/export-bundle/file`, `POST …/import-bundle` (`workflow_bundle.py`); **snapshots/diff:** `POST …/graph-snapshot`, `GET …/graph-snapshots`, `POST …/graph-diff`; **templates write:** `PUT`/`POST` `/api/templates/*` behind `MIROFISH_ALLOW_TEMPLATE_WRITE` or `FLASK_DEBUG`; **batch:** `POST /api/simulation/batch/create`; **webhooks:** `webhook_service` + `/api/hooks/webhooks` + `simulation.completed` / `simulation.failed` + **in-memory retries (3×)** + **per-subscription DLQ** (`uploads/webhooks/dlq/<id>.jsonl` after exhaustion); **streaming chat:** `POST /api/report/chat/stream` + `LLMClient.chat_stream_text` / `chat_stream_narrative`; **optional auth:** `MIROFISH_API_KEY`, `MIROFISH_REQUIRE_USER_HEADER`, `owner_user_id` on projects | Step2/MainView SSE; optional DLQ replay/admin UI |

**Env knobs (see `.env.example`):** `REPORT_SECTION_PARALLEL`, `REPORT_SECTION_PARALLEL_MAX_WORKERS`, `INSIGHT_FORGE_PARALLEL_SUBQUERIES`, `INSIGHT_FORGE_SUBQUERY_WORKERS`, `VITE_SIMULATION_SSE`, `VITE_REPORT_LOG_SSE`, `MIROFISH_API_KEY`, `MIROFISH_ALLOW_TEMPLATE_WRITE`, `MIROFISH_REQUIRE_USER_HEADER`, `BATCH_SIM_MAX_ITEMS`.

### Recommended-order phases 2–5 (execution checklist)

Per **Recommended Execution Order** below: **Phase 1 (P0) remains open.** Phases **2–5** are **addressed** for the items in this table; mega-Vue splits (Step2/4/5) and full workflow E2E remain **optional** polish.

| Phase | Scope | Done |
|-------|--------|------|
| 2 | Code health (splits optional) | Backend/frontend hygiene; **ReportOutlinePanel** reduces Step4/Step5 duplication for the outline column |
| 3 | Tests + CI | Growing pytest set (~25 files); Vitest incl. **graphLayout**; CI lint + e2e |
| 4 | Perf + DX | Sim status SSE; report log SSE; MCP backoff; **GraphPanel** incremental graph updates + skip identical poll payloads |
| 5 | Features + polish | Report compare + sections; Tools/Template editor; graph query + diff/snapshots; bundles; batch; **webhooks + DLQ**; chat stream SSE; Home a11y; Prettier |

## Backlog (local-only priorities)

These items remain relevant for the current **single-user, local-only** setup. They are not blocked on P0 hardening or multi-user concerns.

1. Narrow remaining broad `except Exception` usage, especially in backend API, report, and graph-tool paths.
2. Further split large frontend files, mainly [Step2EnvSetup.vue](/Users/rishabh/Documents/Mirofish/mirofish/frontend/src/components/Step2EnvSetup.vue) and remaining heavy sections in [Step4Report.vue](/Users/rishabh/Documents/Mirofish/mirofish/frontend/src/components/Step4Report.vue) and [Step5Interaction.vue](/Users/rishabh/Documents/Mirofish/mirofish/frontend/src/components/Step5Interaction.vue).
3. Add deeper `SimulationRunner` IPC and integration tests.
4. Add more bundle round-trip and SSE integration tests.
5. Add Step2/MainView SSE for graph build and preparation progress.
6. Move GraphPanel closer to a strict D3 enter/update/exit lifecycle.
7. Expand JSDoc / `@ts-check` across more frontend API modules.
8. Continue broader `rem` and `aria` cleanup on workflow chrome.
9. Add optional DLQ replay/admin UI for webhooks if local webhook workflows matter.

Out of scope for this deployment:

1. P0 hardening from the security section, unless this install is exposed beyond localhost.
2. Multi-user auth/RBAC.

---

## P0 — Security & Correctness (Fix Now)

> **Local-only scope note:** keep this section as a reference for any future hosted/shared deployment. For the current single-user local setup, these items are acknowledged but intentionally deferred.

| Issue | Location | Impact |
|-------|----------|--------|
| CLI proxy ports exposed on `0.0.0.0` with no auth | `docker-compose.yml:52-106` | Anyone can make free LLM calls on your subscriptions |
| 82x raw `str(e)` in API error responses | `app/api/` (simulation, report, graph blueprints) | Leaks internal paths, class names, config in production |
| Simulation ID validation missing on `/start`, `/stop`, `/interview` | `app/api/simulation/` | Guard coverage is inconsistent across simulation-ID endpoints; early validation is still missing on several mutating routes |
| Duplicate `_get_cors_origins()` in `config.py` | `app/config.py` | **Fixed:** single function; defaults include **3000**, **5173**, and **5001** (see `Config.CORS_ORIGINS`) |

### Details

**CLI proxy ports**: Change `docker-compose.yml` port bindings from `0.0.0.0:1143X` to `127.0.0.1:1143X`, or remove `ports:` entirely since the `mirofish` service reaches proxies via Docker network. Add a bearer token check to proxy endpoints.

**Error response leakage**: Replace `return jsonify({"success": False, "error": str(e)}), 500` with generic messages in production. Log the real error server-side. Only expose detail when `FLASK_DEBUG=true`.

**Simulation ID validation**: `_reject_unsafe_simulation_id()` / `_resolved_simulation_dir_or_error()` already protect `/delete`, and `_reject_unsafe_simulation_id()` also protects `/run-status/stream`. Apply equivalent early guards to `/start`, `/stop`, `/interview`, and other simulation-ID endpoints that still accept raw IDs.

**Duplicate CORS function**: ~~Remove shadowed duplicate and align defaults with Vite (3000) and legacy 5173.~~ **Done** (2026-03-31).

---

## P1 — Architecture & Code Quality

> **Status:** Most backend rows and many frontend rows are **addressed**; mega-component splits remain optional. See [Non-P0 implementation status](#non-p0-implementation-status-2026-03-31).

### Backend

| Issue | Details |
|-------|---------|
| `report_agent.py` is 2,713 lines | Extract: prompts to `report_prompts.py`, loggers to `report_logging.py`, `ReportManager` to `report_manager.py`, models to `report_models.py` |
| `api/simulation.py` is 2,378 lines | Split into: entity routes, CRUD routes, run control, interview routes → **`app/api/simulation/`** package |
| `SimulationRunner` class-level dicts have no locking | `_run_states`, `_processes`, `_monitor_threads` mutated from Flask threads + monitor threads concurrently. Add `threading.Lock` similar to `TaskManager._task_lock` |
| Retry logic duplicated in 3 places | `retry.py` (decorator), `graph_tools._call_with_retry` (method), inline in `oasis_profile_generator.py`. Consolidate to use `retry_with_backoff` from `retry.py` |
| `print()` in production code | `oasis_llm.py` and `oasis_profile_generator.py`. Replace with logger calls |
| 137x `except Exception` (broad catches) | Most swallow errors silently, return inconsistent fallbacks. Narrow exception types and add proper logging — **partial:** `simulation_runner` action-log reader narrowed; API/report/graph_tools still broad in places |
| Unused `import asyncio` in `simulation_runner.py` | Imported but never used. Remove or indicates abandoned async migration |
| `services/__init__.py` is 63 lines | Non-trivial init file doing import-time work — consider making it explicit |

### Frontend

| Issue | Details |
|-------|---------|
| `Step4Report.vue` is 5,160 lines | Extract: `ReportOutline.vue`, `ReportSection.vue`, `AgentLogTimeline.vue`, `WorkflowOverview.vue` — **partial:** left outline column is **`ReportOutlinePanel.vue`** (shared with Step5) |
| `Step2EnvSetup.vue` is 2,602 lines | Break into focused sub-components |
| `Step5Interaction.vue` is 2,584 lines | Break into focused sub-components — **partial:** outline column shared via **`ReportOutlinePanel.vue`** |
| Header/layout duplicated across 5 views | Extract `AppHeader.vue` + `useWorkflowLayout` composable. Currently the entire header HTML, `leftPanelStyle`/`rightPanelStyle` computed properties, `toggleMaximize()`, and `addLog()` are copy-pasted into every view |
| `Process.vue` (2,067 lines) is dead code | Not in router — `MainView.vue` replaced it. Still has `alert()` calls. Delete it |
| `alert()` used for errors (3 places) | `Process.vue`, `Step1GraphBuild.vue`. Replace with a toast/notification component |
| `error.value` set but never rendered | `MainView.vue` catches errors but has no `v-if="error"` in template — user sees nothing |
| D3 resize handler not debounced | Every pixel of resize triggers full `renderGraph()`. Add 150-200ms debounce + use `ResizeObserver` |
| No state management beyond one store | Every view re-fetches everything on navigation. Add Pinia for project/simulation/graph state |
| `renderMarkdown` duplicated | Identical ~50-line function in both `Step4Report.vue` and `Step5Interaction.vue`. Extract to `/src/utils/markdown.js` |
| Templates API double-unwraps response | `templates.js` does `response.data` but Axios interceptor in `index.js` already returns `res.data` — this is a bug |

---

## P2 — Testing & CI

> **Status:** Test runner, backend/frontend coverage, broad backend ruff, and Playwright smoke are now wired into CI. Remaining work is broader system coverage, not missing infrastructure.

### Current State (updated)

| Area | Coverage |
|------|----------|
| Backend tests | **~25** files under `backend/tests/` (incl. hooks, webhooks, **`test_webhook_dlq.py`**, bundle import, LLM client, graph builder, **`test_report_agent_plan_outline.py`**, **`test_simulation_runner_platforms.py`**, compare APIs, graph query validate, phase completion) |
| Frontend tests | **Vitest** — `markdown.test.js`, `api/report.test.js`, `api/simulation.test.js`, **`utils/graphLayout.test.js`** |
| CI test step | **`uv run pytest`** on the backend, **`uv run ruff check app tests`**, and **`npm ci && npm test && npm run lint && npm run test:e2e`** on PRs/tags/dispatch |
| Linting | **ESLint** in `frontend/` (`npm run lint`); Python **ruff across `app` + `tests`** |
| E2E | **Playwright** smoke: `frontend/e2e/smoke.spec.js`, `npm run test:e2e` (build + preview) |

### Backend Test Files

- `test_ontology_response.py` — `unwrap_malformed_ontology()`
- `test_report_pdf_html.py` — XSS/sanitization for PDF export
- `test_twitter_profiles.py` — profile endpoints
- `test_api_health.py` — `/health`, templates list
- `test_report_outline_context.py` — parallel-report outline-only context helper
- `test_phase_completion_api.py` — report compare, `Config.validate` graph backend, simulation SSE stream
- `test_simulation_compare_api.py` — simulation compare endpoint payload/delta coverage
- `test_simulation_compare_and_cleanup.py` — compare error paths + background-task shutdown registry
- `test_graph_query_validate.py` — read-only Kuzu/Cypher guard (`validate_read_only_kuzu_query`)
- `test_webhook_dlq.py` — failed delivery writes JSONL dead-letter per subscription
- `test_report_agent_plan_outline.py` — `plan_outline` with mocked `chat_json` / graph context
- `test_simulation_runner_platforms.py` — `_check_all_platforms_completed` with temp `actions.jsonl` layout

### Completely Untested (still high value)

- `LLMClient` (all providers, JSON parsing, structured output) — **some** coverage in `test_llm_client.py`
- `GraphBuilderService` / `EntityExtractor` / `OntologyGenerator` — **partial:** `test_graph_builder_get_data.py`
- `SimulationRunner` (start, stop, monitor, IPC) — integration-heavy; **partial:** platform completion helper + model tests
- `ReportAgent` end-to-end (`generate_section_react`, chat) — **partial:** `plan_outline` unit test with mocks
- `GraphToolsService` (all retrieval tools)
- `TaskManager` / `SessionManager` / `WorkbenchSession`
- Most API surface beyond smoke
- Config validation edge cases, cost estimator

### Recommended Test Priorities

1. `LLMClient` unit tests — mock each provider response format
2. API smoke tests — Flask test client for blueprints (**started** with health/templates)
3. `TaskManager` / `SessionManager` persistence — atomic writes, concurrent access
4. `Config.validate()` edge cases — missing env vars, invalid values
5. Frontend: Vitest for API modules + markdown (**markdown done**)
6. E2E: Playwright smoke across the five main workflow/tooling pages (**done**); full browser-driven journey remains optional

### CI Improvements

```yaml
# Add before the build job in .github/workflows/docker-image.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install uv && cd backend && uv sync && uv run pytest
      - run: cd frontend && npm ci && npm test && npm run lint
  build-and-push:
    needs: test
```

Optional: `npx playwright install chromium && npm run test:e2e` with built `dist/` + preview.

Also add:

- `cache-from: type=gha` / `cache-to: type=gha,mode=max` for Docker layer caching
- PR/push triggers (currently only tags + manual dispatch)
- Keep backend ruff broad as new modules/tests are added

---

## P3 — Performance

> **Status:** Major items implemented or partially implemented; see status table. Full D3 data join and MCP backoff still optional.

| Bottleneck | Location | Fix | Status |
|------------|----------|-----|--------|
| Report generation: sequential LLM sections | `app/services/report_agent.py` | Parallelize independent sections (ReACT per section) | **Opt-in** `REPORT_SECTION_PARALLEL`; outline-only context between sections |
| `simulation_ipc.py` blocks Flask threads | `app/services/simulation_ipc.py` | Async/SSE or thread pool | **Adaptive poll backoff**; does not remove blocking wait |
| Monitor thread polls every 2s, writes full state | `app/services/simulation_runner.py` | Back off when idle; write on change | **Done** (adaptive sleep + reduced churn) |
| `_run_states` dict grows unbounded | `simulation_runner.py` | Evict completed simulations | **Done** (eviction policy) |
| D3 graph fully destroyed on refresh | `GraphPanel.vue` | Enter/update/exit vs full clear | **Improved:** `utils/graphLayout.js` builds stable node/edge sets; **skip** full redraw when ids unchanged; **incremental** reuse of `chart-layer` + merged positions when same `graph_id` and strict superset of nodes/edges; **focus/center** on selection; still not a full D3 data-join lifecycle |
| No D3 node count cap | `GraphPanel.vue` | Cap ~500 + message | **Done** |
| `InsightForge` sequential sub-queries | `app/services/graph_tools.py` | Batch or parallelize | **Parallel** `search_graph` for sub-queries (env-toggle) |
| Report chat re-reads markdown from disk | `report_agent` | In-memory cache after first read | **Done** |
| MCP `pollSimulation` fixed 5s interval | `mcp-server/src/index.js` | Exponential backoff | **Present** (5s start, ×1.5 up to 30s) |
| Simulation status push | — | SSE alternative to 2s polling | **`GET .../run-status/stream`** + frontend EventSource |
| Report agent / console log push | `app/api/report.py`, `Step4Report.vue` | SSE for log tail | **`GET .../agent-log/sse`**, **`.../console-log/sse`** + optional `EventSource` (`VITE_REPORT_LOG_SSE`) |

---

## P4 — Developer Experience & Infrastructure

> **Status:** Docker uv, MCP lockfile, English description, CHANGELOG, healthcheck, template validation, CLAUDE fourth template, `LLM_BOOST_*` docs, and the ENV generator — **done**.

| Issue | Location | Fix |
|-------|----------|-----|
| `requirements.txt` duplicates `pyproject.toml` | `backend/` | Dockerfile uses `uv sync --frozen` (**done**) |
| `mcp-server/` has no `package-lock.json` | `mcp-server/` | Commit lockfile (**done**) |
| Root `package.json` description still in Chinese | `package.json` | English description (**done**) |
| `docs/ENV.md` says "AUTO-GENERATED" but isn't | `docs/ENV.md` | **Done**: generator script added and docs regenerated from `.env.example` |
| No CHANGELOG | project root | **CHANGELOG added** |
| `geopolitical_conflict.json` template undocumented | `backend/templates/` | **CLAUDE.md** updated to four templates |
| Main Docker service has no healthcheck | `docker-compose.yml` | **Healthcheck added** |
| Docker PATH has version-pinned Claude binary | `docker-compose.yml` | **Done**: stable `/home/deploy/.local/share/claude/current` path with startup symlink bootstrap |
| `SECRET_KEY` regenerated on every restart | `app/config.py` | **Done**: persisted to `backend/uploads/.secret_key` when env is unset |
| Root `package.json` `dev` script uses `kill-port 5001` | `package.json` | **Done**: documented in README and paired with `npm run dev:no-kill` |
| No template schema validation | `app/api/templates.py` | **Pydantic validation on load** |
| No graceful shutdown for background threads | `graph_builder.py`, report paths | **Done**: background task registry joins tracked threads on shutdown |

---

## P5 — UX & Accessibility

> **Status:** Partial — not “zero aria”; ESLint baseline exists. Large polish items remain.

| Issue | Details |
|-------|---------|
| Sparse `aria-*` / `role` | **Improved** on GraphPanel controls, node-detail **Center** control, and **ReportOutlinePanel** (collapsible section headers when completed); not audited app-wide |
| Icon-only buttons | Prefer `aria-label` + `title` (**partially** applied) |
| No responsive breakpoints on workflow views | Only some views have media queries. Dual-panel layout breaks on mobile | **Improved:** workflow views, compare pages, and template editor now have mobile breakpoints |
| No loading skeletons | Spinners only | **Improved:** compare and template views now show skeletons during fetches |
| Global notifications | **Toast + error banner** patterns introduced; unify further if needed |
| Font sizes use `px` everywhere | Prefer `rem` where practical | **Improved:** status indicators and several new views use `rem`; broader cleanup optional |
| No node search/filter in D3 graph | Large graphs still hard to navigate |
| Keyboard on drag-drop upload zone | **Home:** `role="button"`, `tabindex`, Enter/Space, `aria-label` |
| Color-only status indicators | Add text labels where possible | **Improved:** workflow status indicators now pair dot + text labels |
| ESLint / Prettier | **ESLint** (`flat/essential`); **Prettier** (`npm run format` / `format:check`) |
| Report A/B comparison UI | **Done:** `POST /api/report/compare`, `/report/compare` + Compare nav; optional **section** table when API returns `sections_a` / `sections_b` |
| Workflow tools / graph query | **`/tools`** (bundles, snapshots, batch, webhooks); **GraphPanel** Cypher **Query** → `/api/graph/query` |
| TypeScript or JSDoc | **Partial:** `// @ts-check` + module blurb on `src/api/simulation.js`; extend to other `src/api/*.js` as needed |

---

## Feature Enhancement Ideas

Original value/complexity estimates; **implementation status** reflects the roadmap pass (2026-03-31). See [Non-P0 implementation status](#non-p0-implementation-status-2026-03-31) for file/route pointers.

| Feature | Value | Complexity | Status (2026-03-31) |
|---------|-------|------------|---------------------|
| WebSocket/SSE for real-time updates | Replace polling with push for sim progress, report gen, agent logs | Medium | **Partial:** SSE for `run-status/stream`, report `agent-log/sse` + `console-log/sse`; Step2/MainView graph/task still mostly HTTP poll; no WebSocket |
| Simulation comparison UI | Side-by-side scenarios | Low-Medium | **Done:** `POST /api/simulation/compare`, `/simulation/compare`, timelines/posts/delta summary |
| Graph query interface | Cypher against Kuzu graphs | Medium | **Done:** `POST /api/graph/query`, validation in `graph_storage.py`, GraphPanel **Query** dialog |
| Template editor UI | Lower barrier than raw JSON | Low | **Done:** `/templates/edit` + `PUT`/`POST` `/api/templates/*`; form-first editor with advanced JSON fallback |
| Export/import workflows | Share project + graph | Low | **Done:** `export-bundle`, `export-bundle/file`, `import-bundle` (+ Tools page); bundle version `1` in `workflow_bundle.py` |
| Multi-user auth | Tenant isolation | High | **Out of scope for current deployment:** optional `MIROFISH_API_KEY` (Bearer), `MIROFISH_REQUIRE_USER_HEADER` + `X-MiroFish-User`, `owner_user_id` on `Project` exist, but full sessions/JWT/RBAC are unnecessary for a single-user local install |
| Streaming LLM responses | Lower perceived latency | Medium | **Partial:** `POST /api/report/chat/stream` (narrative, no tools); full ReACT/tool chat still non-streaming |
| Batch simulation runs | Queue many sims | Medium | **Done:** `POST /api/simulation/batch/create` (+ Tools UI); sequential create, not a persisted job worker |
| Graph diff view | Graph change over time | Medium | **Done:** snapshots under project `graph_snapshots/`, `POST …/graph-diff`, list endpoint; optional highlight-in-D3 still open |
| Plugin/webhook system | External subscriptions | High | **Partial:** registry `uploads/webhooks/registry.json`, `POST/GET/DELETE /api/hooks/webhooks`, signed `X-MiroFish-Signature`, debounced `simulation.completed` / `simulation.failed`, **3× POST retries** + **DLQ** append to `uploads/webhooks/dlq/<subscription_id>.jsonl` on final failure; no inbound plugin API or DLQ replay UI |

---

## Recommended Execution Order

### Phase 1 — Security hardening (required only for hosted/shared deployments)

1. Bind proxy ports to `127.0.0.1` or add auth
2. Sanitize error responses (replace `str(e)` with generic messages)
3. Apply simulation ID validation to all endpoints
4. ~~Fix duplicate `_get_cors_origins()`~~ **Done**

### Phase 2 — Code health (**largely done** for backend + several frontend items)

1. ~~Delete dead `Process.vue`~~
2. Split `report_agent` (**done** into modules); simulation API package (**done**); mega-Vue splits **optional**
3. Shared layout (**useWorkflowLayout** + patterns)
4. Retry / print / runner locks (**done**)
5. Threading locks on `SimulationRunner` (**done**)

### Phase 3 — Testing foundation (**expanded**)

1. Grow backend tests beyond smoke (**ongoing** — hooks, webhooks, DLQ, graph layout Vitest, mocked `plan_outline`, platform completion)
2. CI test + lint steps (**verify** workflow includes pytest + frontend)
3. Vitest (**done** baseline)
4. Templates API unwrap (**done**)

### Phase 4 — Performance & DX (**largely done**; verify MCP backoff)

1. Pinia (**done** baseline)
2. Debounce D3 + graph layer refresh (**done**); incremental updates + identical-payload skip (**done** via `graphLayout.js`); strict enter/update/exit **optional**
3. Parallel report sections (**opt-in env**)
4. Docker/packaging (**uv**, lockfiles, healthchecks **done**)

### Phase 5 — Features & polish (**substantially advanced**)

1. **SSE:** simulation **`/run-status/stream`** + Step3; report **`agent-log/sse`** / **`console-log/sse`** + Step4 (`VITE_REPORT_LOG_SSE`); **`POST /api/report/chat/stream`** for narrative streaming
2. **Comparison:** report **`/report/compare`** + section alignment + Compare nav; simulation-level compare **`/simulation/compare`** now done
3. **Tools & integrations:** **`/tools`** (bundles, snapshots/diff, batch, webhooks client); **`/templates/edit`**; **GraphPanel** Cypher query; **README** integrations section; **Accessibility + Prettier** (**partial** — Home upload keyboard/labels; remaining JSDoc/TS polish and optional splits only)

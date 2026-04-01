# Frontend codemap

**Last updated:** 2026-04-01

**Entry points:** `frontend/src/main.js`, `frontend/src/App.vue`, `frontend/vite.config.js` (dev proxy `/api` → backend)

## Routes (`frontend/src/router/index.js`)

| Path | View | Notes |
| ---- | ---- | ----- |
| `/` | `Home.vue` | Landing, upload / template flow |
| `/process/:projectId` | `MainView.vue` | Five-step workflow (graph → env → simulation → report → interaction) |
| `/simulation/:simulationId` | `SimulationView.vue` | Simulation overview |
| `/simulation/:simulationId/start` | `SimulationRunView.vue` | Live run (SSE when enabled) |
| `/simulation/compare` | `SimulationCompareView.vue` | Side-by-side simulations |
| `/report/:reportId` | `ReportView.vue` | Report + outline / logs |
| `/report/compare` | `ReportCompareView.vue` | Two-report compare |
| `/interaction/:reportId` | `InteractionView.vue` | Agent interviews |
| `/tools` | `WorkflowToolsView.vue` | Bundles, snapshots, batch sims, webhook registration |
| `/templates/edit` | `TemplateEditorView.vue` | Template JSON editor when backend allows writes |

## API client modules (`frontend/src/api/`)

| File | Backend area |
| ---- | ------------ |
| `graph.js` | `/api/graph/*` |
| `simulation.js` | `/api/simulation/*` |
| `report.js` | `/api/report/*` |
| `templates.js` | `/api/templates/*` |
| `hooks.js` | `/api/hooks/*` |
| `index.js` | Shared Axios instance (`VITE_API_BASE_URL`, interceptors) |

Unit tests alongside clients: `*.test.js` (Vitest).

## Notable UI areas

- Workflow steps: `Step1GraphBuild.vue` … `Step5Interaction.vue`
- Graph visualization: `GraphPanel.vue`, D3 in graph-related components
- Pinia stores and composables under `frontend/src/stores/`, `frontend/src/composables/`

## Related

- [backend.md](./backend.md) — REST surface those clients call  

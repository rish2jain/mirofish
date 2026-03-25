# API Reference

Generated from Flask route definitions. Base URL: `http://localhost:5001`

<!-- AUTO-GENERATED: api-endpoints -->

## Health & Frontend

| Method | Path               | Description              |
| ------ | ------------------ | ------------------------ |
| GET    | `/health`          | Health check (includes LLM backend info) |
| GET    | `/<path>`          | Serve frontend SPA       |

## Graph API (`/api/graph`)

| Method | Path                              | Description                               |
| ------ | --------------------------------- | ----------------------------------------- |
| GET    | `/project/<project_id>`           | Get project details                       |
| GET    | `/project/list`                   | List all projects                         |
| DELETE | `/project/<project_id>`           | Delete a project                          |
| POST   | `/project/<project_id>/reset`     | Reset project state                       |
| POST   | `/ontology/generate`              | Upload documents + requirement, generate ontology |
| POST   | `/build`                          | Build graph from ontology                 |
| GET    | `/task/<task_id>`                 | Query async task status                   |
| GET    | `/tasks`                          | List all tasks                            |
| GET    | `/nodes`                          | Get graph nodes                           |
| GET    | `/edges`                          | Get graph edges                           |
| GET    | `/data/<graph_id>`                | Retrieve full graph data                  |
| DELETE | `/delete/<graph_id>`              | Delete a graph                            |

## Simulation API (`/api/simulation`)

| Method | Path                                      | Description                                |
| ------ | ----------------------------------------- | ------------------------------------------ |
| GET    | `/entities/<graph_id>`                    | Get filtered entities from graph           |
| GET    | `/entities/<graph_id>/<entity_uuid>`      | Get single entity detail                   |
| GET    | `/entities/<graph_id>/by-type/<type>`     | Get entities by type                       |
| POST   | `/create`                                 | Create new simulation                      |
| POST   | `/prepare`                                | Prepare simulation (profiles + config)     |
| POST   | `/prepare/status`                         | Check preparation progress                 |
| GET    | `/<simulation_id>`                        | Get simulation metadata                    |
| GET    | `/list`                                   | List simulations                           |
| GET    | `/history`                                | Simulation history (for homepage)          |
| GET    | `/<simulation_id>/profiles`               | Fetch agent personas                       |
| GET    | `/<simulation_id>/profiles/realtime`      | Live profile generation stream             |
| GET    | `/<simulation_id>/config/realtime`        | Live config generation stream              |
| GET    | `/<simulation_id>/config`                 | Get simulation config                      |
| GET    | `/<simulation_id>/config/download`        | Download config file                       |
| GET    | `/script/<script_name>/download`          | Download simulation script                 |
| POST   | `/generate-profiles`                      | Generate profiles for entities             |
| POST   | `/start`                                  | Start simulation                           |
| POST   | `/stop`                                   | Stop running simulation                    |
| POST   | `/delete`                                 | Delete simulation                          |
| GET    | `/<simulation_id>/run-status`             | Real-time simulation progress              |
| GET    | `/<simulation_id>/run-status/detail`      | Detailed run status                        |
| GET    | `/<simulation_id>/actions`                | Action history (with filtering)            |
| GET    | `/<simulation_id>/timeline`               | Summarized simulation timeline             |
| GET    | `/<simulation_id>/agent-stats`            | Agent statistics                           |
| GET    | `/<simulation_id>/posts`                  | Retrieve simulated posts                   |
| GET    | `/<simulation_id>/comments`               | Retrieve simulated comments                |
| POST   | `/interview`                              | Interview a single agent                   |
| POST   | `/interview/batch`                        | Batch interview agents                     |
| POST   | `/interview/all`                          | Interview all agents                       |
| POST   | `/interview/history`                      | Get interview history                      |
| POST   | `/env-status`                             | Check simulation environment status        |
| POST   | `/close-env`                              | Close simulation environment               |
| POST   | `/fork`                                   | Fork simulation with modified params (A/B) |
| GET    | `/<simulation_id>/cost-estimate`          | Estimated token cost for simulation        |

## Report API (`/api/report`)

| Method | Path                                      | Description                                |
| ------ | ----------------------------------------- | ------------------------------------------ |
| POST   | `/generate`                               | Generate simulation report (async)         |
| GET/POST | `/generate/status`                      | Query report generation progress           |
| GET    | `/<report_id>`                            | Get report details                         |
| GET    | `/by-simulation/<simulation_id>`          | Get report by simulation ID                |
| GET    | `/list`                                   | List all reports                           |
| GET    | `/<report_id>/download`                   | Download report (Markdown)                 |
| DELETE | `/<report_id>`                            | Delete report                              |
| POST   | `/chat`                                   | Chat with report agent (ReACT)             |
| GET    | `/<report_id>/progress`                   | Real-time report generation progress       |
| GET    | `/<report_id>/sections`                   | Get generated sections                     |
| GET    | `/<report_id>/section/<index>`            | Get single section content                 |
| GET    | `/check/<simulation_id>`                  | Check report status for simulation         |
| GET    | `/<report_id>/agent-log`                  | Get agent execution log                    |
| GET    | `/<report_id>/agent-log/stream`           | Get complete agent log                     |
| GET    | `/<report_id>/console-log`               | Get console output log                     |
| GET    | `/<report_id>/console-log/stream`        | Get complete console log                   |
| POST   | `/compare`                                | Compare two reports side-by-side           |
| GET    | `/<report_id>/pdf`                        | Export report as branded PDF               |
| POST   | `/tools/search`                           | Graph search tool (debug)                  |
| POST   | `/tools/statistics`                       | Graph statistics tool (debug)              |

## Templates API (`/api/templates`)

| Method | Path                | Description                     |
| ------ | ------------------- | ------------------------------- |
| GET    | `/`                 | List all simulation templates   |
| GET    | `/<template_id>`    | Get a single template by ID     |

<!-- /AUTO-GENERATED: api-endpoints -->

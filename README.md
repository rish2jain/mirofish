# MiroFish

A swarm intelligence prediction engine. Upload documents describing any scenario, and MiroFish simulates thousands of AI agents reacting on social media to predict how events will unfold.

**Live:** [synth.scty.org](https://synth.scty.org)

> Fork of [666ghj/MiroFish](https://github.com/666ghj/MiroFish) — fully translated to English, local graph storage with embedded KuzuDB by default, Claude/Codex/Gemini CLI support added.

## What it does

1. **Upload reality seeds** — PDFs, markdown, or text files (news articles, policy drafts, financial reports, anything)
2. **Describe what to predict** — natural language prompt (e.g., "Predict public reaction to this policy over 60 days"), or pick a consulting template
3. **MiroFish builds a world** — extracts entities and relationships into a knowledge graph, generates AI agent personas with distinct personalities and opinions
4. **Agents simulate social media** — dual-platform simulation (Twitter + Reddit) where agents post, reply, like, argue, and follow each other
5. **Get a prediction report** — AI analyzes all simulation data and produces findings. Chat with the report agent, interview individual agents, or export as PDF.
6. **Fork and compare** — clone a simulation with different parameters to run A/B scenarios side by side

[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.gg/ePf5aPaHnA)
[![X](https://img.shields.io/badge/X-Follow-000000?style=flat-square&logo=x&logoColor=white)](https://x.com/mirofish_ai)
[![Instagram](https://img.shields.io/badge/Instagram-Follow-E4405F?style=flat-square&logo=instagram&logoColor=white)](https://www.instagram.com/mirofish_ai/)

## Changes from upstream

| Area                   | Upstream                       | This fork                                                        |
| ---------------------- | ------------------------------ | ---------------------------------------------------------------- |
| **Language**           | Chinese UI + prompts           | Full English (60+ files translated)                              |
| **LLM providers**      | Alibaba Qwen only              | OpenAI, Anthropic, Claude CLI, Codex CLI, Gemini CLI             |
| **LLM auto-detection** | Manual config only             | CLI-first orchestrator auto-detects local CLIs at startup        |
| **Graph database**     | Hosted graph service           | Local KuzuDB (embedded, free)                                    |
| **Entity extraction**  | Managed extraction pipeline    | LLM-based extraction (uses your own model)                       |
| **Auth**               | Requires API keys              | Can use Claude/Codex/Gemini CLI subscriptions (no API cost)      |
| **Templates**          | None                           | Consulting templates (regulatory impact, M&A, crisis comms)      |
| **Scenario forking**   | None                           | Clone simulations with changed parameters for A/B comparison     |
| **PDF export**         | None                           | Branded PDF/HTML report export                                   |
| **MCP server**         | None                           | Claude Code integration via MCP tools                            |

## Quick start

### Prerequisites

- Node.js 18+
- Python 3.11-3.12
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- At least one of: [Claude CLI](https://claude.ai/code), [Codex CLI](https://github.com/openai/codex), [Gemini CLI](https://github.com/google-gemini/gemini-cli), or an LLM API key

### Setup

```bash
cp .env.example .env
# Edit .env — or leave LLM_PROVIDER blank for auto-detection
npm run setup:all
npm run dev
```

- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:5001>

### Docker

```bash
cp .env.example .env
docker compose up -d --build
```

Docker builds the Vue frontend, serves it from the Flask app, and exposes the combined app on port `5001` inside the container.

## LLM providers

Set `LLM_PROVIDER` in `.env`, or **leave it blank** to auto-detect local CLIs in priority order (Claude → Codex → Gemini → API fallback):

| Provider      | Config                                    | Cost                                |
| ------------- | ----------------------------------------- | ----------------------------------- |
| *(auto)*      | Leave `LLM_PROVIDER` blank                | Uses first CLI found on PATH        |
| `claude-cli`  | Just set `LLM_PROVIDER=claude-cli`        | Uses your Claude Code subscription  |
| `codex-cli`   | Just set `LLM_PROVIDER=codex-cli`         | Uses your Codex CLI subscription    |
| `gemini-cli`  | Just set `LLM_PROVIDER=gemini-cli`        | Uses your Gemini CLI subscription   |
| `openai`      | Set `LLM_API_KEY` + `LLM_MODEL_NAME`     | Pay-per-token                       |
| `anthropic`   | Set `LLM_API_KEY` + `LLM_MODEL_NAME`     | Pay-per-token                       |

```env
# Example: auto-detect (recommended)
# LLM_PROVIDER=

# Example: use Codex CLI explicitly
LLM_PROVIDER=codex-cli

# Example: use OpenAI API
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL_NAME=gpt-4o-mini
```

## CLI proxies (Docker)

For Docker deployments, each CLI is wrapped in an OpenAI-compatible HTTP sidecar with bounded concurrency:

| Proxy          | Port  | CLI command                          |
| -------------- | ----- | ------------------------------------ |
| `codex-proxy`  | 11435 | `codex exec --skip-git-repo-check`   |
| `claude-proxy` | 11436 | `claude -p --output-format json`     |
| `gemini-proxy` | 11437 | `gemini -p`                          |

Each proxy exposes `POST /v1/chat/completions`, `GET /v1/models`, and `GET /health`. Configured via `*_PROXY_WORKERS` and `*_PROXY_TIMEOUT` env vars.

The proxy containers mount the host CLI binary and auth state, so make sure the CLI is installed and authenticated on the host first. Outside Docker, MiroFish calls CLIs directly (no proxy needed).

## Consulting templates

Pre-built simulation templates in `backend/templates/`:

- **Regulatory Impact Analysis** — predict public/market reaction to regulatory changes
- **M&A Reaction Forecast** — predict stakeholder reaction to mergers and acquisitions
- **Crisis Communications** — simulate crisis lifecycle and communication strategy effectiveness

Templates pre-fill the simulation requirement and suggest entity types. Select from the dropdown in the upload flow, or use the API: `GET /api/templates/`.

## MCP server (Claude Code integration)

`mcp-server/` exposes MiroFish as tools for Claude Code:

```bash
cd mcp-server && npm install
```

The `.mcp.json` at project root enables auto-discovery. Available tools:

- `list_templates` — list simulation templates
- `run_simulation` — full pipeline (create → prepare → start)
- `get_report` — fetch or generate a report
- `chat_with_report` — chat with the report agent
- `inject_variable` — fork a simulation with changed parameters
- `get_simulation_status` — check simulation progress

Example prompt in Claude Code:

> "Use the regulatory_impact template on draft_guidance.pdf with 15 rounds, then summarize key risks."

## Architecture

```text
frontend/          Vue 3 + Vite + D3.js (graph visualization)
backend/
  app/
    api/           Thin Flask REST endpoints (graph, simulation, report, templates)
    core/          LLM orchestrator, workbench session, task tracking
    resources/     Adapters for projects, documents, Kuzu, simulations, reports
    tools/         Composable workbench operations (ingest, build, prepare, run, report)
    services/      Core business logic (15 modules)
    utils/         LLM client, cost estimator, file parser, retry, logging
  templates/       Consulting simulation templates (JSON)
  scripts/         OASIS simulation runner scripts (Twitter + Reddit)
claude-proxy/      OpenAI-compatible sidecar for Claude CLI (Docker)
codex-proxy/       OpenAI-compatible sidecar for Codex CLI (Docker)
gemini-proxy/      OpenAI-compatible sidecar for Gemini CLI (Docker)
mcp-server/        MCP server for Claude Code integration
```

The backend is being refactored toward a pi-style shape: one workbench session core, pluggable resource adapters, composable tools, and thin API shells.

## How the pipeline works

```text
Document upload → LLM ontology extraction → Knowledge graph (KuzuDB)
    → Entity filtering → Agent persona generation (LLM)
    → OASIS dual-platform simulation (Twitter + Reddit subprocess)
    → Graph memory updates → Report generation (ReACT agent)
    → Interactive chat / agent interviews / PDF export
    → Scenario fork → A/B comparison
```

## Acknowledgments

- [MiroFish](https://github.com/666ghj/MiroFish) by 666ghj — original project
- [OASIS](https://github.com/camel-ai/oasis) by CAMEL-AI — multi-agent social simulation framework
- [KuzuDB](https://github.com/kuzudb/kuzu) — embedded graph database

## License

AGPL-3.0

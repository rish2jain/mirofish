# Environment Variables

Generated from `.env.example`. Variables marked **Required\*** are only required when no CLI tool is available on PATH.

<!-- AUTO-GENERATED: env -->

## LLM Configuration

| Variable           | Required | Default                     | Description                                                                      |
| ------------------ | -------- | --------------------------- | -------------------------------------------------------------------------------- |
| `LLM_PROVIDER`     | No       | *(auto-detect)*             | `openai`, `anthropic`, `claude-cli`, `codex-cli`, `gemini-cli`, or blank for auto |
| `LLM_API_KEY`      | *        | —                           | API key for OpenAI or Anthropic (not needed for CLI providers)                    |
| `LLM_BASE_URL`     | No       | `https://api.openai.com/v1` | API base URL (override for OpenRouter, proxies, etc.)                             |
| `LLM_MODEL_NAME`   | No       | `gpt-4o-mini`               | Model identifier sent to the provider                                             |

## CLI Proxy Configuration (Docker only)

| Variable               | Required | Default | Description                                |
| ---------------------- | -------- | ------- | ------------------------------------------ |
| `CODEX_PROXY_WORKERS`  | No       | `4`     | Max concurrent Codex CLI subprocesses      |
| `CODEX_PROXY_TIMEOUT`  | No       | `180`   | Codex CLI timeout in seconds               |
| `CLAUDE_PROXY_WORKERS` | No       | `4`     | Max concurrent Claude CLI subprocesses     |
| `CLAUDE_PROXY_TIMEOUT` | No       | `120`   | Claude CLI timeout in seconds              |
| `GEMINI_PROXY_WORKERS` | No       | `4`     | Max concurrent Gemini CLI subprocesses     |
| `GEMINI_PROXY_TIMEOUT` | No       | `180`   | Gemini CLI timeout in seconds              |

## Graph Database

| Variable        | Required | Default          | Description                                  |
| --------------- | -------- | ---------------- | -------------------------------------------- |
| `GRAPH_BACKEND` | No       | `kuzu`           | Storage backend: `kuzu` or `json`            |
| `KUZU_DB_PATH`  | No       | `./data/kuzu_db` | Path to the embedded KuzuDB directory        |
| `DATA_DIR`      | No       | `./data/json_graphs` | Path to JSON graph storage (if `json` backend) |

## OASIS Simulation

| Variable                   | Required | Default | Description                           |
| -------------------------- | -------- | ------- | ------------------------------------- |
| `OASIS_DEFAULT_MAX_ROUNDS` | No       | `10`    | Default number of simulation rounds   |

## Report Agent

| Variable                            | Required | Default | Description                                  |
| ----------------------------------- | -------- | ------- | -------------------------------------------- |
| `REPORT_AGENT_MAX_TOOL_CALLS`      | No       | `5`     | Max tool calls per ReACT agent response      |
| `REPORT_AGENT_MAX_REFLECTION_ROUNDS`| No       | `2`     | Max reflection iterations per section        |
| `REPORT_AGENT_TEMPERATURE`          | No       | `0.5`   | LLM temperature for report generation        |

## Flask

| Variable             | Required | Default     | Description                                                         |
| -------------------- | -------- | ----------- | ------------------------------------------------------------------- |
| `FLASK_DEBUG`        | No       | `false`     | Enable Flask debug mode                                             |
| `FLASK_HOST`         | No       | `0.0.0.0`  | Bind address                                                        |
| `FLASK_PORT`         | No       | `5001`      | Listen port                                                         |
| `EXPOSE_BINARY_PATH` | No       | *(unset)*   | If set, `/health` includes full CLI binary path instead of boolean  |

## Accelerated LLM (optional)

| Variable              | Required | Default | Description                                     |
| --------------------- | -------- | ------- | ----------------------------------------------- |
| `LLM_BOOST_API_KEY`   | No       | —       | API key for a separate "boost" model             |
| `LLM_BOOST_BASE_URL`  | No       | —       | Base URL for the boost provider                  |
| `LLM_BOOST_MODEL_NAME`| No       | —       | Model name for the boost provider                |

<!-- /AUTO-GENERATED: env -->

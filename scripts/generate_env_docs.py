#!/usr/bin/env python3
"""Generate docs/ENV.md from .env.example.

The output is intentionally conservative: it preserves the current section/table
layout while making the documentation reproducible from a single script.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"
OUTPUT = ROOT / "docs" / "ENV.md"


@dataclass(frozen=True)
class EnvRow:
    name: str
    required: str
    default: str
    description: str


@dataclass(frozen=True)
class EnvSection:
    title: str
    rows: tuple[EnvRow, ...]


DOC_SECTIONS: tuple[EnvSection, ...] = (
    EnvSection(
        "LLM Configuration",
        (
            EnvRow("LLM_PROVIDER", "No", "*(auto-detect)*", "`openai`, `anthropic`, `claude-cli`, `codex-cli`, `gemini-cli`, or blank for auto"),
            EnvRow("LLM_API_KEY", "*", "—", "API key for OpenAI or Anthropic (not needed for CLI providers)"),
            EnvRow("LLM_BASE_URL", "No", "https://api.openai.com/v1", "API base URL (override for OpenRouter, proxies, etc.)"),
            EnvRow("LLM_MODEL_NAME", "No", "gpt-4o-mini", "Model identifier sent to the provider"),
        ),
    ),
    EnvSection(
        "CLI Proxy Configuration (Docker only)",
        (
            EnvRow("CODEX_PROXY_WORKERS", "No", "4", "Max concurrent Codex CLI subprocesses"),
            EnvRow("CODEX_PROXY_TIMEOUT", "No", "180", "Codex CLI timeout in seconds"),
            EnvRow("CLAUDE_PROXY_WORKERS", "No", "4", "Max concurrent Claude CLI subprocesses"),
            EnvRow("CLAUDE_PROXY_TIMEOUT", "No", "120", "Claude CLI timeout in seconds"),
            EnvRow("GEMINI_PROXY_WORKERS", "No", "4", "Max concurrent Gemini CLI subprocesses"),
            EnvRow("GEMINI_PROXY_TIMEOUT", "No", "180", "Gemini CLI timeout in seconds"),
        ),
    ),
    EnvSection(
        "Graph Database",
        (
            EnvRow("GRAPH_BACKEND", "No", "kuzu", "Storage backend: `kuzu` or `json`"),
            EnvRow("KUZU_DB_PATH", "No", "./data/kuzu_db", "Path to the embedded KuzuDB directory"),
            EnvRow("DATA_DIR", "No", "./data/json_graphs", "Path to JSON graph storage (if `json` backend)"),
        ),
    ),
    EnvSection(
        "OASIS Simulation",
        (EnvRow("OASIS_DEFAULT_MAX_ROUNDS", "No", "10", "Default number of simulation rounds"),),
    ),
    EnvSection(
        "Report Agent",
        (
            EnvRow("REPORT_AGENT_MAX_TOOL_CALLS", "No", "5", "Max tool calls per ReACT agent response"),
            EnvRow("REPORT_AGENT_MAX_REFLECTION_ROUNDS", "No", "2", "Max reflection iterations per section"),
            EnvRow("REPORT_AGENT_TEMPERATURE", "No", "0.5", "LLM temperature for report generation"),
        ),
    ),
    EnvSection(
        "Flask",
        (
            EnvRow("FLASK_DEBUG", "No", "false", "Enable Flask debug mode"),
            EnvRow("FLASK_HOST", "No", "0.0.0.0", "Bind address"),
            EnvRow("FLASK_PORT", "No", "5001", "Listen port"),
            EnvRow("EXPOSE_BINARY_PATH", "No", "*(unset)*", "If set, `/health` includes full CLI binary path instead of boolean"),
        ),
    ),
    EnvSection(
        "Accelerated LLM (optional)",
        (
            EnvRow("LLM_BOOST_API_KEY", "No", "—", 'API key for a separate "boost" model'),
            EnvRow("LLM_BOOST_BASE_URL", "No", "—", "Base URL for the boost provider"),
            EnvRow("LLM_BOOST_MODEL_NAME", "No", "—", "Model name for the boost provider"),
        ),
    ),
)


def _load_example_values() -> dict[str, str]:
    values: dict[str, str] = {}
    line_re = re.compile(r"^\s*#?\s*([A-Z0-9_]+)\s*=\s*(.*)$")
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        m = line_re.match(line)
        if not m:
            continue
        name, value = m.group(1), m.group(2).strip()
        if name not in values:
            values[name] = value
    return values


def _render_table(rows: tuple[EnvRow, ...], example_values: dict[str, str]) -> str:
    lines = [
        "| Variable | Required | Default | Description |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        default = row.default
        if default == "—":
            formatted_default = "—"
        elif default in {"*(auto-detect)*", "*(unset)*"}:
            formatted_default = default
        else:
            display = default
            if display == "" and row.name in example_values:
                display = example_values[row.name]
            formatted_default = f"`{display}`" if display else "—"
        lines.append(
            f"| `{row.name}` | {row.required} | {formatted_default} | {row.description} |"
        )
    return "\n".join(lines)


def generate() -> str:
    example_values = _load_example_values()
    parts = [
        "# Environment Variables",
        "",
        "Generated from `.env.example` via `scripts/generate_env_docs.py`. Variables marked **Required*** are only required when no CLI tool is available on PATH.",
        "",
        "<!-- AUTO-GENERATED: env -->",
        "",
    ]
    for section in DOC_SECTIONS:
        parts.append(f"## {section.title}")
        parts.append("")
        parts.append(_render_table(section.rows, example_values))
        parts.append("")
    parts.append("<!-- /AUTO-GENERATED: env -->")
    parts.append("")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write docs/ENV.md in place")
    parser.add_argument("--check", action="store_true", help="Fail if docs/ENV.md is out of date")
    args = parser.parse_args()

    output = generate()
    if args.write:
        OUTPUT.write_text(output, encoding="utf-8")
        return 0

    if args.check:
        try:
            current = OUTPUT.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(
                "docs/ENV.md is missing. Run scripts/generate_env_docs.py --write.",
                file=sys.stderr,
            )
            return 1
        if current != output:
            print("docs/ENV.md is out of date. Run scripts/generate_env_docs.py --write.", file=sys.stderr)
            return 1
        return 0

    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

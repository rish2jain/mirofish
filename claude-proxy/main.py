#!/usr/bin/env python3
"""
claude-proxy: OpenAI-compatible HTTP proxy for Claude CLI.
Wraps `claude -p --output-format json` in a FastAPI server.
"""

import asyncio
import json
import os
import time
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="claude-proxy")

MAX_WORKERS = int(os.environ.get("CLAUDE_PROXY_WORKERS", "4"))
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_PROXY_TIMEOUT", "120"))
semaphore = asyncio.Semaphore(MAX_WORKERS)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: Optional[str] = "claude"
    messages: list[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    response_format: Optional[dict] = None


def build_prompt(messages: list[Message], response_format: Optional[dict] = None) -> str:
    parts: list[str] = []
    for msg in messages:
        if msg.role == "system":
            parts.append(f"SYSTEM INSTRUCTIONS:\n{msg.content}")
        elif msg.role == "user":
            parts.append(f"USER: {msg.content}")
        elif msg.role == "assistant":
            parts.append(f"ASSISTANT: {msg.content}")

    if response_format and response_format.get("type") == "json_object":
        parts.insert(
            1,
            "IMPORTANT: Respond with valid JSON only. No markdown, no explanation, just pure JSON.",
        )

    return "\n\n".join(parts)


def parse_claude_output(raw: str) -> str:
    """Extract result text from Claude CLI JSON output."""
    try:
        output = json.loads(raw)
        return output.get("result", raw).strip()
    except (json.JSONDecodeError, AttributeError):
        return raw.strip()


async def call_claude(prompt: str) -> str:
    """Run claude CLI subprocess asynchronously."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            "--output-format",
            "json",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=502, detail="Claude CLI error: binary not found") from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()),
            timeout=CLAUDE_TIMEOUT,
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise HTTPException(
            status_code=504,
            detail=f"Claude CLI timed out after {CLAUDE_TIMEOUT}s",
        ) from exc

    if proc.returncode != 0:
        err = stderr.decode()[:300]
        raise HTTPException(status_code=502, detail=f"Claude CLI error: {err}")

    return parse_claude_output(stdout.decode())


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    prompt = build_prompt(req.messages, req.response_format)
    async with semaphore:
        content = await call_claude(prompt)

    response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    return {
        "id": response_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model or "claude",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": "claude", "object": "model", "created": 0, "owned_by": "anthropic"}],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "workers": MAX_WORKERS}

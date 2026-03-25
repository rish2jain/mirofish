# syntax=docker/dockerfile:1
# Shared runtime for claude-proxy and gemini-proxy (FastAPI + uvicorn + Node for vendor CLIs).
#
# Build from repository root, for example:
#   docker build -f docker/cli-proxy.Dockerfile --target claude-proxy -t mirofish-claude-proxy .
#   docker build -f docker/cli-proxy.Dockerfile --target gemini-proxy -t mirofish-gemini-proxy .
#
# Override pins: docker build --build-arg FASTAPI_VERSION=... -f docker/cli-proxy.Dockerfile --target claude-proxy .

ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} AS cli-proxy-runtime

WORKDIR /app

# curl + nodejs: installed without `package=version` pins so bookworm security updates apply on rebuild.
# (APT does not support wildcards in version specifiers; exact pins break when the base image’s suite moves.)
# When the base image changes or install fails: inspect available versions with
#   docker run --rm python:3.11-slim bash -lc 'apt-get update && apt-cache madison curl nodejs'
# If you must pin again, add ARGs and use full `curl=<exact>` / `nodejs=<exact>` from madison; record the
# tested lines in docs/RUNBOOK.md (Docker / cli-proxy) for the next maintainer.

# Claude Code and Gemini CLIs are Node.js tools; nodejs supplies the runtime for the `claude` / `gemini` binaries.
ARG FASTAPI_VERSION=0.135.2
ARG UVICORN_VERSION=0.42.0
ARG PYDANTIC_VERSION=2.12.5

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
        fastapi==${FASTAPI_VERSION} \
        "uvicorn[standard]==${UVICORN_VERSION}" \
        pydantic==${PYDANTIC_VERSION}

FROM cli-proxy-runtime AS claude-proxy
COPY claude-proxy/main.py .
EXPOSE 11436
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["curl", "-f", "http://127.0.0.1:11436/health"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "11436", "--workers", "1"]

FROM cli-proxy-runtime AS gemini-proxy
COPY gemini-proxy/main.py .
EXPOSE 11437
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["curl", "-f", "http://127.0.0.1:11437/health"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "11437", "--workers", "1"]

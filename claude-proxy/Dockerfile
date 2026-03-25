# Build this image from the repository root — shared install logic lives in docker/cli-proxy.Dockerfile.
#
#   docker build -f docker/cli-proxy.Dockerfile --target claude-proxy -t mirofish-claude-proxy .
#
# `docker compose build claude-proxy` is configured the same way (see docker-compose.yml).

FROM alpine:3.20
RUN printf '%s\n' \
  'Do not `docker build` this directory alone.' \
  'From repo root: docker build -f docker/cli-proxy.Dockerfile --target claude-proxy -t mirofish-claude-proxy .' \
  >&2 && exit 1

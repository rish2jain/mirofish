#!/bin/sh
set -eu

CLAUDE_ROOT="/home/deploy/.local/share/claude"
CLAUDE_STABLE="$CLAUDE_ROOT/current"

if [ -d "$CLAUDE_ROOT/versions" ] && [ ! -e "$CLAUDE_STABLE" ]; then
  latest_version="$(find "$CLAUDE_ROOT/versions" -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null | sort -V | tail -n 1 || true)"
  if [ -n "$latest_version" ]; then
    mkdir -p "$CLAUDE_ROOT"
    ln -sfn "$latest_version" "$CLAUDE_STABLE"
  fi
fi

exec "$@"

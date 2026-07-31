#!/usr/bin/env bash
# Refresh the Graphify knowledge graph in graphify-out/ — only when it is stale.
#
#   scripts/update_graph.sh           refresh only if source is newer than the graph
#   scripts/update_graph.sh --force   rebuild regardless
#   scripts/update_graph.sh --check   report staleness only (exit 1 if stale)
#
# `graphify update` is AST-only: no API key, no LLM cost. It runs extraction and
# then clustering in one pass (clustering is skipped only with --no-cluster).
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
GRAPH="$ROOT/graphify-out/graph.json"

# Directories whose shape the graph models. Doc/config/test-only edits do not
# meaningfully change it, so they do not trigger a rebuild.
SOURCE_DIRS=(backend app-front-end/src web-front-end/src packages)

mode=refresh
case "${1-}" in
  --force) mode=force ;;
  --check) mode=check ;;
  "") ;;
  *) echo "usage: $0 [--force|--check]" >&2; exit 64 ;;
esac

if ! command -v graphify >/dev/null 2>&1; then
  echo "graphify: not installed or not on PATH." >&2
  echo "Install it, or skip the graph — it is an optional navigation aid." >&2
  exit 2
fi

is_stale() {
  [ -f "$GRAPH" ] || return 0
  local d newer
  for d in "${SOURCE_DIRS[@]}"; do
    [ -d "$ROOT/$d" ] || continue
    newer="$(find "$ROOT/$d" \
      \( -name node_modules -o -name __pycache__ -o -name dist \) -prune -o \
      -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' \) \
      -newer "$GRAPH" -print -quit)"
    [ -n "$newer" ] && return 0
  done
  return 1
}

if [ "$mode" = check ]; then
  if is_stale; then echo "graph is stale"; exit 1; fi
  echo "graph is current"; exit 0
fi

if [ "$mode" != force ] && ! is_stale; then
  echo "graph is current — nothing to do"
  exit 0
fi

echo "refreshing graphify-out/ (AST-only)..."
graphify update "$ROOT"

#!/usr/bin/env bash
set -euo pipefail

# Build the lattice CLI as a standalone binary for macOS / Linux.
#
# Usage:
#   ./release/build.sh            # default build
#   ./release/build.sh --with-llm # include openai + anthropic SDKs
#
# Output: dist/lattice

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

WITH_LLM=false
for arg in "$@"; do
  case "$arg" in
    --with-llm) WITH_LLM=true ;;
  esac
done

echo "==> Ensuring build dependencies..."
pip install pyinstaller -q

if [ "$WITH_LLM" = true ]; then
  echo "==> Installing lattice with LLM extras..."
  pip install -e "$ROOT[llm]" -q
else
  echo "==> Installing lattice..."
  pip install -e "$ROOT" -q
fi

echo "==> Building standalone binary..."
pyinstaller "$ROOT/release/lattice.spec" \
  --distpath "$ROOT/dist" \
  --workpath "$ROOT/build" \
  --noconfirm \
  --clean

BINARY="$ROOT/dist/lattice"
if [ -f "$BINARY" ]; then
  chmod +x "$BINARY"
  echo ""
  echo "==> Build complete!"
  echo "    Binary: $BINARY"
  echo "    Size:   $(du -h "$BINARY" | cut -f1)"
  echo ""
  echo "    Test:   $BINARY --help"
else
  echo "ERROR: Build failed — binary not found at $BINARY" >&2
  exit 1
fi

#!/usr/bin/env bash
# format.sh — auto-format all frontend files using Prettier
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

cd "$FRONTEND_DIR"

if ! command -v npx &>/dev/null; then
  echo "Error: npx not found. Install Node.js to run Prettier." >&2
  exit 1
fi

echo "Formatting frontend files..."
npx prettier --write "**/*.{js,css,html}"
echo "Done."

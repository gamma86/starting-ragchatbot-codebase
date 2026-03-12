#!/usr/bin/env bash
# check-quality.sh — verify frontend code meets formatting standards (no writes)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

cd "$FRONTEND_DIR"

if ! command -v npx &>/dev/null; then
  echo "Error: npx not found. Install Node.js to run quality checks." >&2
  exit 1
fi

PASS=true

echo "=== Prettier format check ==="
if npx prettier --check "**/*.{js,css,html}"; then
  echo "✓ All files are properly formatted."
else
  echo "✗ Formatting issues found. Run scripts/format.sh to fix them."
  PASS=false
fi

echo ""
if $PASS; then
  echo "All quality checks passed."
  exit 0
else
  echo "Quality checks failed. See above for details."
  exit 1
fi

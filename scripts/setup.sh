#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --frozen --extra dev
npm ci --ignore-scripts
if command -v flutter >/dev/null 2>&1; then
  (cd apps/jarvis_app && flutter pub get --enforce-lockfile)
fi

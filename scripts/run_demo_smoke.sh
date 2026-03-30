#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost}"
API_PREFIX="${API_PREFIX:-/api}"
MANIFEST_PATH="${MANIFEST_PATH:-tests/data/demo_manifest.json}"
API_KEY_VALUE="${API_KEY:-}"
SKIP_HISTORY="${SKIP_HISTORY:-0}"
NO_BUILD="${NO_BUILD:-0}"

if [[ -z "${API_KEY_VALUE}" ]]; then
  echo "API key is required. Set API_KEY or pass API_KEY in env."
  exit 2
fi

if [[ "${NO_BUILD}" == "1" ]]; then
  docker compose up -d
else
  docker compose up -d --build
fi

CMD=(
  python scripts/demo_smoke.py
  --base-url "${API_BASE_URL}"
  --api-prefix "${API_PREFIX}"
  --api-key "${API_KEY_VALUE}"
  --manifest "${MANIFEST_PATH}"
)

if [[ "${SKIP_HISTORY}" == "1" ]]; then
  CMD+=(--skip-history-check)
fi

"${CMD[@]}"

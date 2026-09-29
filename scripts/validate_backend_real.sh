#!/usr/bin/env bash
set -euo pipefail

# Keep the existing CI entry point and use the same evaluated workflow as the UI.
if [[ -z "${IMAGE_PATH:-}" || ! -f "$IMAGE_PATH" ]]; then
  echo "ERROR: set IMAGE_PATH to a real JPG/PNG/WEBP portrait." >&2
  exit 2
fi

args=("$IMAGE_PATH" --base-url "${API_BASE_URL:-http://127.0.0.1:8000}"
      --style-id "${STYLE_ID:-soft_lifestyle_illustration}")
if [[ "${VALIDATE_REFINEMENT:-1}" != "1" ]]; then
  args+=(--no-refine)
fi
if [[ -n "${POLL_ATTEMPTS:-}" ]]; then
  args+=(--timeout "$((POLL_ATTEMPTS * ${POLL_SECONDS:-3}))")
fi
exec python scripts/smoke_portrait.py "${args[@]}"

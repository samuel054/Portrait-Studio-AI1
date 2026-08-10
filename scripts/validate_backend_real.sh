#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
IMAGE_PATH="${IMAGE_PATH:-}"
STYLE_ID="${STYLE_ID:-soft_lifestyle_illustration}"
POLL_SECONDS="${POLL_SECONDS:-3}"
POLL_ATTEMPTS="${POLL_ATTEMPTS:-120}"
VALIDATE_REFINEMENT="${VALIDATE_REFINEMENT:-1}"
PORTRAIT_API_KEY="${PORTRAIT_API_KEY:-}"

if [[ -z "$IMAGE_PATH" || ! -f "$IMAGE_PATH" ]]; then
  echo "ERROR: set IMAGE_PATH to a real JPG/PNG/WEBP portrait." >&2
  exit 2
fi

AUTH=()
if [[ -n "$PORTRAIT_API_KEY" ]]; then
  AUTH=(-H "X-API-Key: $PORTRAIT_API_KEY")
fi

json_get() {
  local expr="$1"
  python -c "import json,sys; data=json.load(sys.stdin); print($expr)"
}

request_json() {
  local method="$1"; shift
  curl --fail-with-body --silent --show-error -X "$method" "${AUTH[@]}" "$@"
}

echo "[1/9] health"
health="$(request_json GET "$API_BASE_URL/health")"
echo "$health" | json_get 'data["status"]'

echo "[2/9] readiness (ComfyUI must be reachable)"
ready="$(request_json GET "$API_BASE_URL/ready")"
ready_status="$(echo "$ready" | json_get 'data["status"]')"
comfy_ready="$(echo "$ready" | json_get 'data["checks"]["comfyui"]')"
if [[ "$ready_status" != "ready" || "$comfy_ready" != "True" ]]; then
  echo "ERROR: backend is not ready with ComfyUI: $ready" >&2
  exit 3
fi

echo "[3/9] create real portrait job"
job_response="$(curl --fail-with-body --silent --show-error \
  "${AUTH[@]}" \
  -F "file=@${IMAGE_PATH}" \
  -F "style_id=${STYLE_ID}" \
  -F "candidate_count=2" \
  "$API_BASE_URL/v1/portrait-jobs")"
job_id="$(echo "$job_response" | json_get 'data["job"]["id"]')"
echo "job_id=$job_id"

echo "[4/9] poll generation + identity evaluation"
job_status=""
session_id=""
for ((attempt=1; attempt<=POLL_ATTEMPTS; attempt++)); do
  status_response="$(request_json GET "$API_BASE_URL/v1/portrait-jobs/$job_id?refresh=true")"
  job_status="$(echo "$status_response" | json_get 'data["job"]["status"]')"
  echo "attempt=$attempt status=$job_status"
  if [[ "$job_status" == "failed" ]]; then
    echo "ERROR: portrait job failed: $status_response" >&2
    exit 4
  fi
  if [[ "$job_status" == "awaiting_selection" ]]; then
    session_id="$(echo "$status_response" | json_get 'data["job"]["candidate_session_id"]')"
    break
  fi
  sleep "$POLL_SECONDS"
done
if [[ -z "$session_id" ]]; then
  echo "ERROR: job did not reach awaiting_selection after $POLL_ATTEMPTS attempts." >&2
  exit 5
fi
echo "candidate_session_id=$session_id"

echo "[5/9] verify candidate session and select candidate"
session_response="$(request_json GET "$API_BASE_URL/v1/candidate-sessions/$session_id?include_images=false")"
candidate_id="$(echo "$session_response" | json_get 'data["session"]["candidates"][0]["id"]')"
selection_payload="$(printf '{"candidate_id":"%s"}' "$candidate_id")"
selection_response="$(curl --fail-with-body --silent --show-error \
  "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "$selection_payload" \
  "$API_BASE_URL/v1/candidate-sessions/$session_id/selection")"
selected_id="$(echo "$selection_response" | json_get 'data["selected_candidate"]["id"]')"
if [[ "$selected_id" != "$candidate_id" ]]; then
  echo "ERROR: selected candidate mismatch." >&2
  exit 6
fi

echo "[6/9] submit accepted feedback"
feedback_payload="$(printf '{"candidate_id":"%s","rating":5,"accepted":true,"reasons":["real-integration-smoke"],"comment":"Automated real backend integration validation."}' "$candidate_id")"
request_json POST \
  -H 'Content-Type: application/json' \
  -d "$feedback_payload" \
  "$API_BASE_URL/v1/candidate-sessions/$session_id/feedback" >/dev/null

echo "[7/9] optional real refinement"
if [[ "$VALIDATE_REFINEMENT" == "1" ]]; then
  refine_payload="$(printf '{"style_id":"%s","operation":"lighting","instruction":"Add slightly softer studio lighting while preserving identity.","strength":0.15,"candidate_count":1}' "$STYLE_ID")"
  refine_response="$(request_json POST \
    -H 'Content-Type: application/json' \
    -d "$refine_payload" \
    "$API_BASE_URL/v1/candidate-sessions/$session_id/refine")"
  refine_prompt_id="$(echo "$refine_response" | json_get 'data["generation"]["request_payload"]["prompt_id"]')"
  refine_status=""
  for ((attempt=1; attempt<=POLL_ATTEMPTS; attempt++)); do
    refine_poll="$(request_json GET "$API_BASE_URL/v1/generations/$refine_prompt_id?include_images=false")"
    refine_status="$(echo "$refine_poll" | json_get 'data["generation"]["status"]')"
    echo "refine_attempt=$attempt status=$refine_status"
    if [[ "$refine_status" == "failed" ]]; then
      echo "ERROR: refinement generation failed: $refine_poll" >&2
      exit 7
    fi
    if [[ "$refine_status" == "completed" ]]; then
      break
    fi
    sleep "$POLL_SECONDS"
  done
  if [[ "$refine_status" != "completed" ]]; then
    echo "ERROR: refinement did not complete." >&2
    exit 8
  fi
else
  echo "refinement validation skipped"
fi

echo "[8/9] final render"
render_response="$(request_json POST \
  -H 'Content-Type: application/json' \
  -d '{"output_format":"png","quality":95,"allow_upscale":false}' \
  "$API_BASE_URL/v1/candidate-sessions/$session_id/render")"
render_content_type="$(echo "$render_response" | json_get 'data["render"]["content_type"]')"
if [[ "$render_content_type" != "image/png" ]]; then
  echo "ERROR: unexpected render content type: $render_content_type" >&2
  exit 9
fi

echo "[9/9] verify completed workflow"
final_response="$(request_json GET "$API_BASE_URL/v1/portrait-jobs/$job_id?refresh=false")"
final_status="$(echo "$final_response" | json_get 'data["job"]["status"]')"
if [[ "$final_status" != "completed" ]]; then
  echo "ERROR: expected completed workflow, got $final_status" >&2
  exit 10
fi

echo "REAL BACKEND INTEGRATION PASS"
echo "job_id=$job_id session_id=$session_id candidate_id=$candidate_id"

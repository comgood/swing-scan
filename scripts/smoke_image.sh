#!/usr/bin/env bash
# Run a built API image on 127.0.0.1 and smoke test it (health + one template scan).
# Usage: scripts/smoke_image.sh <image>. The Lambda Web Adapter in the image is a Lambda
# extension and stays idle outside Lambda; it forwards to this same uvicorn on port 8000.
set -euo pipefail

IMAGE="${1:?usage: scripts/smoke_image.sh <image>}"
PORT="${SMOKE_PORT:-8000}"
WAIT_SECONDS="${SMOKE_WAIT_SECONDS:-90}"
NAME="swing-scan-smoke-$$"
URL="http://127.0.0.1:$PORT"

cleanup() {
  local status=$?
  if [[ $status -ne 0 ]]; then
    echo "--- container logs ---" >&2
    docker logs "$NAME" >&2 || true
  fi
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  exit $status
}
trap cleanup EXIT

docker run -d --name "$NAME" -p "127.0.0.1:$PORT:8000" "$IMAGE" >/dev/null

for ((i = 0; i < WAIT_SECONDS; i++)); do
  if curl --fail --silent --max-time 2 "$URL/api/v1/health" >/dev/null; then
    break
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$NAME")" != "true" ]]; then
    echo "container exited before it answered /api/v1/health" >&2
    exit 1
  fi
  sleep 1
done

scripts/smoke.sh "$URL"

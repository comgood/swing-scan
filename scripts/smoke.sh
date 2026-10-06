#!/usr/bin/env bash
# Smoke test a deployed API (spec 0001). Usage: scripts/smoke.sh https://<function-url>
# Scope feature 8 adds one small scan call to this check.
set -euo pipefail

API_URL="${1:?usage: scripts/smoke.sh <api-url>}"
API_URL="${API_URL%/}"

body="$(curl --fail --silent --show-error --max-time 30 "$API_URL/api/v1/health")"
echo "health: $body"
grep -q '"status":"ok"' <<<"$body"
grep -q '"data_mode":"synthetic"' <<<"$body"
echo "smoke test passed"

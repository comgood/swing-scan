#!/usr/bin/env bash
# Smoke test an API (spec 0001): health, then one scan on the first template (feature 8).
# Usage: scripts/smoke.sh https://<function-url>   (or http://127.0.0.1:8000 for a local image)
set -euo pipefail

API_URL="${1:?usage: scripts/smoke.sh <api-url>}"
API_URL="${API_URL%/}"

body="$(curl --fail --silent --show-error --max-time 30 "$API_URL/api/v1/health")"
echo "health: $body"
grep -q '"status":"ok"' <<<"$body"
grep -q '"data_mode":"synthetic"' <<<"$body"

templates="$(curl --fail --silent --show-error --max-time 30 "$API_URL/api/v1/templates")"
template_id="$(jq -r '.[0].id' <<<"$templates")"
scan_body="$(jq -c '{rule: .[0].rule}' <<<"$templates")"

out="$(mktemp)"
trap 'rm -f "$out"' EXIT
status="$(curl --silent --show-error --max-time 60 -o "$out" -w '%{http_code}' \
  -H 'content-type: application/json' -d "$scan_body" "$API_URL/api/v1/scan")"
if [[ "$status" != "200" ]]; then
  echo "scan on template $template_id answered $status, expected 200:" >&2
  head -c 2000 "$out" >&2
  exit 1
fi
# A deploy with no data answers 200 with no rows, and one with dead indicator columns answers
# 200 with null operands: both must fail the smoke test, not pass it.
if ! jq -e '(.rows | length) > 0 and all(.rows[].operands[]; type == "number")' "$out" >/dev/null; then
  echo "scan on template $template_id answered 200 with no usable rows:" >&2
  head -c 2000 "$out" >&2
  exit 1
fi
echo "scan $template_id: 200, as_of $(jq -r '.as_of' "$out"), $(jq '.rows | length' "$out") rows"
echo "smoke test passed"

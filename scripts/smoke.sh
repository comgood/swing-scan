#!/usr/bin/env bash
# Smoke test an API (spec 0001, doc 02 section 9 CD smoke): health, one scan on the first
# template, and one exit lab backtest with 5 configs. Prints the first call and warm health
# timings (right after a deploy the first call is a cold start) and fails if any response
# body is at or over the size budget (Lambda's 6 MB response limit, B-13 and X-7).
# Usage: scripts/smoke.sh https://<function-url>   (or http://127.0.0.1:8000 for a local image)
set -euo pipefail

API_URL="${1:?usage: scripts/smoke.sh <api-url>}"
API_URL="${API_URL%/}"
# No Accept-Encoding is sent, so the API answers uncompressed: the worst case for the limit.
MAX_BYTES="${SMOKE_MAX_BYTES:-6000000}"

out="$(mktemp)"
trap 'rm -f "$out"' EXIT

# call <label> <expected status> <curl args...>: body lands in $out, prints status, time, size.
call() {
  local label="$1" expected="$2"
  shift 2
  local meta status seconds bytes
  meta="$(curl --silent --show-error --max-time 60 -o "$out" \
    -w '%{http_code} %{time_total} %{size_download}' "$@")"
  read -r status seconds bytes <<<"$meta"
  if [[ "$status" != "$expected" ]]; then
    echo "$label answered $status, expected $expected:" >&2
    head -c 2000 "$out" >&2
    exit 1
  fi
  if ((bytes >= MAX_BYTES)); then
    echo "$label body is $bytes bytes, over the $MAX_BYTES byte budget" >&2
    exit 1
  fi
  echo "$label: $status in ${seconds}s, $bytes bytes"
}

call "health (first call)" 200 "$API_URL/api/v1/health"
grep -q '"status":"ok"' "$out"
grep -q '"data_mode":"synthetic"' "$out"
call "health (warm)" 200 "$API_URL/api/v1/health"

call "templates" 200 "$API_URL/api/v1/templates"
templates="$(cat "$out")"
template_id="$(jq -r '.[0].id' <<<"$templates")"

scan_body="$(jq -c '{rule: .[0].rule}' <<<"$templates")"
call "scan $template_id" 200 -H 'content-type: application/json' -d "$scan_body" \
  "$API_URL/api/v1/scan"
echo "  as_of $(jq -r '.as_of' "$out"), $(jq '.rows | length' "$out") rows"

# Five exit lab configs (doc 02 section 9), the same set as FIVE_CONFIGS in the X-7 acceptance test.
backtest_body="$(jq -c '{
  rule: .[0].rule,
  configs: [
    {name: "Baseline", exits: [{type: "time", bars: 10}]},
    {name: "Stop and time", exits: [{type: "stop_pct", pct: 8}, {type: "time", bars: 10}]},
    {name: "ATR, target, time", exits: [
      {type: "stop_atr", k: 2, n: 14}, {type: "target", pct: 15}, {type: "time", bars: 20}]},
    {name: "Trail", exits: [{type: "trail_pct", pct: 10}, {type: "time", bars: 30}]},
    {name: "MA exit", exits: [
      {type: "close_below_ma", ma: "ema", n: 21}, {type: "stop_pct", pct: 8}]}
  ]
}' <<<"$templates")"
call "backtest $template_id, 5 configs" 200 -H 'content-type: application/json' \
  -d "$backtest_body" "$API_URL/api/v1/backtest"
echo "  mode $(jq -r '.mode' "$out")"

echo "smoke test passed"

#!/usr/bin/env bash
# Smoke test an API (spec 0001, doc 02 section 9 CD smoke): health, one scan on the first
# template, and one exit lab backtest with 5 configs. Prints the first call and warm health
# timings (the first call pays for image optimisation, see below) and fails if any response
# body is at or over the size budget (Lambda's 6 MB response limit, B-13 and X-7). The scan
# must also come back usable: a 200 with no rows, or with null operands, fails.
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

# Named for what it is: run from a deploy, this first call lands on a freshly pushed image and
# pays for Lambda optimising it, so it runs several seconds longer than the cold start a visitor
# meets on an idle function (measured separately, infra/README section 6). It is the worst case,
# not the number doc 01's "cold start <= 10 s" judges.
call "health (first call after update)" 200 "$API_URL/api/v1/health"
grep -q '"status":"ok"' "$out"
grep -q '"data_mode":"synthetic"' "$out"
call "health (warm)" 200 "$API_URL/api/v1/health"

call "templates" 200 "$API_URL/api/v1/templates"
templates="$(cat "$out")"
template_id="$(jq -r '.[0].id' <<<"$templates")"

# Dataset and indicator health, deterministically: `close > 0` holds for every live ticker, so a
# loaded market must return rows with numeric operands. A template scan cannot prove this, because
# a day with no 52 week breakouts is a legitimate empty answer and a market whose indicator
# columns are all null also answers 200 with no rows. This rule tells the two apart.
probe_body='{"rule":{"name":"smoke probe","conditions":[{"left":{"kind":"ind","ind":"close",
  "n":null,"offset":0,"mult":1},"op":">","right":{"kind":"value","value":0}}]}}'
call "scan probe (close > 0)" 200 -H 'content-type: application/json' \
  -d "$(jq -c . <<<"$probe_body")" "$API_URL/api/v1/scan"
if ! jq -e '(.rows | length) > 0 and all(.rows[].operands[]; type == "number")' "$out" >/dev/null; then
  echo "the market is missing or its indicator columns are dead: close > 0 matched nothing" >&2
  head -c 2000 "$out" >&2
  exit 1
fi
echo "  as_of $(jq -r '.as_of' "$out"), $(jq '.rows | length' "$out") rows match close > 0"

scan_body="$(jq -c '{rule: .[0].rule}' <<<"$templates")"
call "scan $template_id" 200 -H 'content-type: application/json' -d "$scan_body" \
  "$API_URL/api/v1/scan"
# No row count is required here: a template may honestly have no hits on the last session. Any
# row it does return must carry numeric operands; the probe above owns dataset health.
if ! jq -e 'all(.rows[].operands[]; type == "number")' "$out" >/dev/null; then
  echo "scan on template $template_id returned rows with null operands:" >&2
  head -c 2000 "$out" >&2
  exit 1
fi
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

# X-7 on the deployed API (spec 0009 AC-11): the slowest template with the six configs of
# SIX_CONFIGS in engine/tests/sim/test_lab_budget.py. Reported, never gated: it answers 200 in
# about 17 s warm (6.04 s in process on a CI runner, so the Lambda is about 2.7x slower per trade
# walk) and clears the function's 30 s timeout by over 10 s.
#
# The 25 s below is X-7's own budget, because X-7's wording names this exact call. It was set
# from measurement: the function reads 16.5 s to 18.9 s warm and varies about 15% between runs,
# so 25 s fails a real regression while leaving the timeout clear. The in process budget in
# test_lab_budget.py is the tighter proxy that catches a regression first.
#
# Still reported rather than gated: a deploy that answers correctly should not go red on one
# noisy timing sample over a shared network path, and `/check verify` reads this number.
# shortcut: reported not gated, so a real slowdown is only seen by someone reading the deploy
# log; gate it once two deploys in a row show margin against 25 s.
# shortcut: the six configs are duplicated from the Python test; move both to one JSON fixture
# when anything about them changes (spec 0009 AC-11 rule 2).
X7_BUDGET_S="${SMOKE_X7_BUDGET_S:-25}"
x7_body="$(jq -c '{
  rule: .[1].rule,
  configs: [
    {name: "Baseline", exits: [{type: "stop_pct", pct: 8}, {type: "time", bars: 20}]},
    {name: "ATR stop and target", exits: [
      {type: "stop_atr", k: 2, n: 14}, {type: "target", pct: 15}, {type: "time", bars: 30}]},
    {name: "MA exit, no stop", exits: [{type: "close_below_ma", ma: "ema", n: 21}]},
    {name: "Trailing 10%", exits: [{type: "trail_pct", pct: 10}, {type: "time", bars: 40}]},
    {name: "Wide target, no stop", exits: [{type: "target", pct: 60}]},
    {name: "Stop, target, time", exits: [
      {type: "stop_pct", pct: 5}, {type: "target", pct: 10}, {type: "time", bars: 15}]}
  ]
}' <<<"$templates")"
x7_id="$(jq -r '.[1].id' <<<"$templates")"

# measure <label>: one call, no gate. Prints status, seconds and bytes, or why it failed.
measure() {
  local label="$1" meta status seconds bytes
  # 45 s, past the function's own 30 s timeout, so a timeout is seen as a 502 rather than
  # curl giving up first and reporting nothing.
  meta="$(curl --silent --show-error --max-time 45 -o "$out" \
    -w '%{http_code} %{time_total} %{size_download}' \
    -H 'content-type: application/json' -d "$x7_body" "$API_URL/api/v1/backtest" || echo "000 0 0")"
  read -r status seconds bytes <<<"$meta"
  echo "$label: $status in ${seconds}s, $bytes bytes"
  X7_STATUS="$status"
  X7_SECONDS="$seconds"
}

echo "X-7 measurement on $x7_id, 6 configs (reported, not gated):"
measure "  first call"
measure "  warm"
if [[ "$X7_STATUS" != "200" ]]; then
  echo "  X-7 MISSED: answered $X7_STATUS, so the 6 config lab does not complete on this deploy" >&2
elif awk "BEGIN{exit !($X7_SECONDS > $X7_BUDGET_S)}"; then
  echo "  X-7 MISSED: warm ${X7_SECONDS}s over the ${X7_BUDGET_S}s budget" >&2
else
  echo "  X-7 warm ${X7_SECONDS}s budget ${X7_BUDGET_S}s sha ${GITHUB_SHA:-local}"
fi

echo "smoke test passed"

# /check verify research honesty guards · PASS

**Date**: 2026-10-08 · **Feature**: scope 13 · **Spec**: [0004](../specs/0004-research-honesty-guards/index.md), checked against the ratified text in PR #17 (`orch/13-ratify-spec-0004`) · **Criteria**: doc 01 U-2, U-4, U-8 · **Code**: `apps/web/src/features/honesty/` at `f8e1c81` (main)

**PASS: all 9 acceptance criteria met, every specced surface built.** One caveat on evidence. AC-8's live mode was driven by a stub health endpoint, because the real API refuses `DATA_MODE=live` today (see "How it ran" below).

Next: feature 13 has no `Review it` box. You could mark it `done` once the owner signs off spec 0004's six assumed decisions (PR #17).

## How it ran

You can run these again yourself. The scripts are in the overnight scratchpad, not in the repo.

1. `make build-web` on `main` (`f8e1c81`), then the export in `apps/web/out` served with clean URLs (`/ui` serves `ui.html`, as Vercel does) on `127.0.0.1:3101`.
2. The real API with `uv run uvicorn api.main:app` on `127.0.0.1:8000` (synthetic mode). For live mode, a stub on the same port answered `GET /api/v1/health` with `{"data_mode": "live"}`.
3. **Real browser**: headless Google Chrome 154 driven over the DevTools protocol, at 375 px and 320 px. It measured sideways scroll, walked the Tab order and pressed Enter on the demo button, and took screenshots.
4. **Headless DOM**: jsdom ran the built Next bundles for `/ui`. It read every trial counter state, clicked the live demo 10 times, reset it, and ran axe on the honesty section.
5. **Library run**: the shipped `trial-store.ts` was run under Node against jsdom's real `localStorage` and `sessionStorage`, plus an opaque origin where storage access throws `SecurityError`. This is how a blocked browser behaves.

## Per criterion

| AC | Verdict | Evidence |
|---|---|---|
| AC-1 numbers only tweaks share N | met ✅ | Library run: `p252` then `p100` under one structure key gave `{1,1}` then `{2,2}`, and localStorage holds `["p252","p100"]` under `swing-scan:trials:v1:<key>`. Gallery demo in jsdom: each tweak advanced N by 1, from 1 to 11 |
| AC-2 identical re run adds nothing | met ✅ | Library run: re recording `p252` stayed at `{2,2}`. A pair from an earlier session (sessionStorage cleared) gave `{2,1}`: it counted once toward M and not again toward N |
| AC-3 M sums pairs across structure keys | met ✅ | Library run: a second structure key gave `{1,3}`. An exit lab run with 3 configs (1 already seen) gave `{3,5}`. The session set holds all 5 pair keys |
| AC-4 line wording | met ✅ | Gallery in jsdom and Chrome: "Trial #6 for this rule structure · 14 this session", in `role="status"` with `aria-live="polite"` |
| AC-5 warning at 10, word for word | met ✅ | Chrome: 9 presses of Enter on the demo button gave "Trial #10 … · 10 this session" with the warning (screenshot `ui-demo-warning-375.png`). jsdom: no warning from trial 1 to trial 9, warning at 10 and 11. Library run: `isOverTrialLimit` is false at 9 and true at 10 |
| AC-6 storage unavailable | met ✅ | Library run: an opaque origin throws `SecurityError` on storage access, and `recordTrial` returns `null`. Gallery "Storage unavailable" state: the status line is empty and the static warning shows (screenshot `ui-honesty-320.png`) |
| AC-7 procedure note, word for word | met ✅ | jsdom: `<p data-slot="procedure-note">` reads "Trade mode isolates the exit effect. Pick the exit on IS, read OOS once, then confirm with a single portfolio backtest." in `text-sm text-foreground`, which is body text, not fine print |
| AC-8 live badge on every page (U-2) | met ✅ (stub) | Chrome and jsdom with the live stub: the shell banner on `/` and `/ui` reads "Live data: current S&P 500 members only (survivors). Results are biased upward.", and the header reads "API ready (data: live, …)". With the real API (synthetic), both pages show "Synthetic market: not real prices" |
| AC-9 gallery, keyboard, axe, 375 px | met ✅ | Chrome: `scrollWidth` equals `innerWidth` on `/` and `/ui` at 375 px and at 320 px, and no element in the honesty section overflows. The first Tab from the section lands on "Run a numbers only tweak", which shows a 2 px solid focus outline. Enter drives the demo. axe in jsdom on the section: 0 violations |

**Specced surfaces**: `recordTrial`, `useTrialCount`, `RunTrialCounter`, `TrialCounter`, `ProcedureNote` and the `/ui` gallery section are all present and exercised. Missing: none. Not applied: none.

## Not exercised in the app (by design)

- `RunTrialCounter` with the browser's own stores is not placed on any page yet. Feature 9 places it on the portfolio report, and feature 12 places it (with `ProcedureNote`) on the exit lab. The gallery demo uses in memory stores so it never touches your real counts. The real storage path was exercised through the library run above. Once features 9 and 12 land, you may want to check it on their pages too.
- Live mode against the real API is blocked until feature 14 lets the API serve `DATA_MODE=live`.

## For /check review

- The gallery and the screenshots render in dark mode (headless Chrome followed the OS). Light mode was not captured. Contrast is already covered by the design.md table.
- The jsdom run needed small shims (Node's `fetch`, `AbortSignal`, streams, and `document.currentScript`) to run the Next bundles. These are harness only; no app code changed.

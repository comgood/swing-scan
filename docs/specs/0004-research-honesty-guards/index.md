# 0004. Count trials per rule structure in browser storage, keyed by the backtest response

**Date**: 2026-10-07 (assumed by /develop) · ratified by /architect 2026-10-08
**Status**: Accepted (owner signed off 2026-10-08)
**Authorized by**: Kenneth Wu (owner), through the FE lane brief, during /develop; ratification run
unattended overnight, every open question took /architect's recommended answer (listed below)

## Summary

This spec settles how the web app keeps you honest while you research: a trial counter that says
how many variants of one rule structure you have tried, a warning once you pass 10, and a one line
procedure note under the exit lab table. Everything lives in your own browser (localStorage for the
long count, sessionStorage for this session's total), and the browser never computes any key
itself: it reads `structure_key` and `pair_keys` straight from the backtest response (spec 0002).
The code already exists in `apps/web/src/features/honesty/`; this ratification confirms the
assumption it was built on and records why. Features 9 and 12 place the parts on their reports.

## Assumed decisions (signed off by the owner, 2026-10-08)

The owner could not answer during this run. Each question below took /architect's recommended
answer; all six match what was built, so no code change follows from ratifying.

1. **What `M` counts.** Distinct pair keys run in this browser session, across every structure
   key. A re run of an identical pair adds nothing. A pair first seen in an earlier session counts
   once toward `M` and not again toward `N`. Runner up: count every completed run (rejected, a re
   run would inflate the total and contradict U-4's "re running an identical pair doesn't add").
2. **What "storage unavailable" means.** If reading or writing either store throws, both counters
   hide and the static warning shows. A stored value that does not parse is treated as empty and
   overwritten, which is not "unavailable". Runner up: degrade each counter on its own (rejected,
   half a counter line reads as a real number and hides that the count is incomplete).
3. **Storage layout.** One localStorage entry per structure key,
   `swing-scan:trials:v1:<structure_key>`, a JSON array of pair keys; one sessionStorage entry,
   `swing-scan:session-trials:v1`, a JSON array of pair keys. No cap. Runner up: one localStorage
   map of every structure key (rejected, each run would rewrite the whole history).
4. **When a run completes.** When a 200 backtest response (portfolio or exit lab) is on screen.
   An exit lab run with k configs records up to k pairs. Recording is idempotent. Runner up:
   count on request send (rejected, a failed or cancelled run is not a trial you looked at).
5. **Display.** "Trial #N for this rule structure · M this session" in a polite live region; the
   U-4 warning word for word in a `warning` `Banner` at `N ≥ 10` and whenever storage is
   unavailable; the U-8 note as one line of body text with an info icon, never fine print.
6. **U-2.** The existing `DataModeBanner` in the app shell (spec 0003 AC-4) covers the live badge
   on every page; this feature adds nothing for it.

## Requirements

**User stories**:
- As a researcher, I want to see how many variants of one rule structure I have tried, so I notice
  when I am fitting noise.
- As a researcher, I want a clear reminder of the honest procedure under the exit lab table, so I
  pick on IS and read OOS once.

**Acceptance criteria** (the contract):
- **AC-1**: Two runs with the same `structure_key` and different `pair_keys` (numbers tweaked)
  count toward the same `N` (U-4, R-9).
- **AC-2**: Re running an identical pair adds nothing to `N` or `M` (U-4).
- **AC-3**: `M` counts distinct pairs across every structure key this session (U-4).
- **AC-4**: The line reads "Trial #N for this rule structure · M this session" (U-4).
- **AC-5**: At `N ≥ 10` the overfit warning shows word for word (U-4): "You've tested many
  variants of this rule structure; the best IS result is likely overfit. Read OOS once and treat
  the result as a hypothesis." `N` counts distinct pairs, so an exit lab run with k new configs
  advances it by k (its first run reads "Trial #k").
- **AC-6**: With storage unavailable, the counters are hidden and the static warning shows (U-4).
  The static warning is the same AC-5 sentence, shown regardless of `N`.
- **AC-7**: The procedure note renders word for word (U-8): "Trade mode isolates the exit
  effect: every config trades identical entries, so the exit is the only difference. Pick the
  exit on in sample (IS), read out of sample (OOS) once, then confirm with a single portfolio
  backtest."
- **AC-8**: The live badge shows on every page in live mode (U-2), covered by the shell.
- **AC-9**: Every state is in the `/ui` gallery, keyboard usable, axe clean, and holds at 375 px.

## Decision

**Chosen option**: Option 1: browser storage keyed by the response's trial keys.

The counter records the `trial` object of each completed backtest response in localStorage (per
structure key) and sessionStorage (session set), with both stores required and the static warning
as the fallback.

**Implementation skills**: `vercel-react-best-practices` (`vercel-labs/agent-skills`,
`.claude/skills/vercel-react-best-practices/`) · `shadcn` (`shadcn-ui/ui`, `.agents/skills/shadcn/`)

## Rationale

Reasoning and options: see [rationale.md](rationale.md).

## Feature design

**Data model sketch** (browser storage only; no server state, per AGENTS.md "no database"):

| Store | Key | Value | Lifetime |
|---|---|---|---|
| localStorage | `swing-scan:trials:v1:<structure_key>` | JSON array of distinct pair keys (64 char hex) | until you clear site data |
| sessionStorage | `swing-scan:session-trials:v1` | JSON array of distinct pair keys | this tab session |

`v1` in the key lets a later format change start clean without parsing old data.

**State transitions** (per mounted run): `pending` (server render and before the effect) →
`counted` (both stores worked) or `unavailable` (either store threw). A new run (a different
`structure_key|pair_keys` id, the pair keys joined in response order) starts at `pending` again.
`pending` renders an empty live region and no warning.

**API surface** (no new endpoint; consumes spec 0002's contract):

| Surface | Kind | Inputs | Outputs |
|---|---|---|---|
| `recordTrial(trial, stores?)` | function | `Trial` from the response | `{ trialNumber, sessionTotal }` or `null` |
| `useTrialCount(trial, stores?)` | hook | `Trial` | `pending` · `counted` · `unavailable` |
| `<RunTrialCounter trial>` | component | `Trial` | counter line, warning when due |
| `<TrialCounter state>` | component | a state | the same, presentational (gallery) |
| `<ProcedureNote>` | component | none | the U-8 line |

**Value sourcing**:

| Action | Value | Source |
|---|---|---|
| record a run | `structure_key` | `trial.structure_key` in the backtest response (spec 0002, server side `sha256`) |
| record a run | pair keys | `trial.pair_keys` in the response, one per config (spec 0002) |
| show the line | `N` | size of the localStorage set for that structure key after recording |
| show the line | `M` | size of the sessionStorage set after recording |
| warn | threshold 10 | `TRIAL_WARNING_AT`, fixed by doc 01 U-4 |
| warn and note copy | strings | doc 01 U-4 and U-8, word for word |
| "run completed" | the trigger | the caller mounts `RunTrialCounter` only for a 200 response on screen |

**Key invariants**:
- The browser never hashes a rule; keys come only from the response.
- Recording is idempotent: the same pairs recorded twice (strict mode, a remount, a re run) leave
  both sets unchanged.
- Storage is touched only after mount, so the static export's HTML never depends on it.
- Copy is word for word from doc 01; numbers use the shared `formatInt`.

**Security model**: no auth, no server state. The sets hold only opaque hashes of your own rules,
in your own browser. Nothing is sent anywhere.

**Configuration required**: none.

**Critical test scenarios**:
- Happy path: two numbers only tweaks give trial 1 then trial 2, same structure key, verifies **AC-1**, **AC-4**
- Re run: the identical pair leaves `N` and `M` unchanged, including under strict mode, verifies **AC-2**
- Session: pairs under two structure keys sum into one `M`, verifies **AC-3**
- Threshold: trial 9 has no warning, trial 10 shows it word for word, verifies **AC-5**
- Failure: a blocked or full store hides the line and shows the static warning, verifies **AC-6**
- Note: the U-8 copy renders as one line, axe clean, verifies **AC-7**
- Gallery: every state at 375 px, keyboard and axe, verifies **AC-9**
- Shell: the live badge renders in live mode on every page (spec 0003 tests), verifies **AC-8**

## Build plan

All tasks are built (feature 13, commit d63b458); listed so each AC traces to code.

1. Trial store: `recordTrial`, the two set layouts, parse fallback, the both stores rule
   (`trial-store.ts`), satisfies **AC-1**, **AC-2**, **AC-3**, **AC-6**
2. Hook: record after mount, cache per run, server snapshot `pending` (`use-trial-count.ts`),
   satisfies **AC-2**
3. Components: `TrialCounter`, `RunTrialCounter`, `ProcedureNote` with the fixed copy,
   satisfies **AC-4**, **AC-5**, **AC-6**, **AC-7**
4. `/ui` gallery section with every state, satisfies **AC-9**; the live badge is the existing
   shell `DataModeBanner` (spec 0003), confirmed, not rebuilt, satisfies **AC-8**
5. Not this feature: feature 9 places `RunTrialCounter` on the portfolio report; feature 12 places
   it on the exit lab report and `ProcedureNote` directly under the exit lab table.

## Consequences

**Positive**:
- Zero cost and zero backend: matches the no database, no auth stack.
- One source of truth for keys (the engine), so the browser and the API can never disagree.

**Negative / tradeoffs**:
- The count is per browser: another device, a private window, or clearing site data starts at 0.
  The counter is a nudge, not an audit trail.
- If the localStorage write succeeds and the sessionStorage write then throws, `N` has grown but
  the run shows "unavailable"; a later re run of that pair then never adds it to `M`. Accepted as
  rare (a full quota in private mode) and harmless.
- Two tabs recording at the same moment can race (read, modify, write) and drop one pair.
  Accepted for a nudge.
- A response with an empty `pair_keys` records nothing and just shows the current totals (or
  "Trial #0" for a new structure). Spec 0002 sends one key per config, so a valid response never
  does this; no extra guard is added.
- No cap: a heavy researcher's sets grow without bound (about 66 bytes per pair, so thousands of
  trials stay far below the usual 5 MB quota).

**Neutral**:
- A change to the key format (spec 0002) changes every key, so old counts stop matching; bump
  `v1` in the storage keys at the same time.

## Follow-up

- [x] Owner sign-off on the six assumed decisions above, then set the status to follow the
  feature lifecycle (`In Progress` until feature 13 is `done`, then `Accepted`).
- [ ] Feature 9 places `RunTrialCounter` near the assumptions header of the portfolio report.
- [ ] Feature 12 places `RunTrialCounter` on the exit lab report and `ProcedureNote` directly under
  its table.
- No mismatch found between this spec and `apps/web/src/features/honesty/` (checked against the
  code and its tests on 2026-10-08), so ratifying asks for no code change.

# 0004 · Research honesty guards

**Status**: Assumed
**Date**: 2026-10-07
**Authorized by**: Kenneth Wu (owner), through the FE lane brief, during /develop

## Owed decision

Doc 01 U-4 and doc 02 §7.5 fix the trial counter's key, its increment rule, the copy, the
threshold and the fallback, but leave four things open:

1. What the session total `M` counts, and whether re running a pair adds to it.
2. What "storage unavailable" means when only one of the two stores fails.
3. How the seen pairs are laid out in localStorage and sessionStorage.
4. When a run "completes" for the counter, and where the counter and procedure note sit.

## Assumption built on

1. **Session total.** `M` is the number of distinct pair keys (`trial.pair_keys`) run in this
   browser session, across every structure key, kept as a set in sessionStorage. Re running an
   identical pair in the same session adds nothing, the same rule as `N`. A pair first seen in an
   earlier session but run again now counts once toward `M` (it is a trial you looked at this
   session) and not again toward `N`.
2. **Unavailable.** If reading or writing either localStorage or sessionStorage throws (blocked
   storage, a full quota in private mode, no `window`), both counters are hidden and the static
   U-4 warning shows. A stored value that does not parse is treated as empty and overwritten;
   that is not "unavailable".
3. **Layout.** localStorage holds one entry per structure key,
   `swing-scan:trials:v1:<structure_key>`, a JSON array of seen pair keys. sessionStorage holds
   `swing-scan:session-trials:v1`, a JSON array of pair keys seen this session. `N` is the length
   of that structure key's array after the run is recorded. No cap: 64 character keys stay well
   inside storage limits for a week of research.
4. **Run completes** means a 200 backtest response (portfolio or exit lab) is on screen. The
   browser never hashes anything: `structure_key` and `pair_keys` come from the response
   (spec 0002). An exit lab run with k configs records k pairs, so it can add up to k to `N`.
   Recording is idempotent, so a repeated render or React strict mode never double counts. The
   counter sits in the portfolio report (feature 9) and the exit lab report (feature 12), near the
   assumptions header; the procedure note sits directly under the exit lab table (feature 12).
5. **Display.** The counter line reads "Trial #N for this rule structure · M this session" and is
   a polite live region. At `N ≥ 10`, and always when storage is unavailable, the U-4 warning
   shows word for word in a `warning` `Banner` (spec 0003). The U-8 procedure note is one line of
   body text with an info icon, never fine print.
6. **U-2.** The live data badge is the existing `DataModeBanner` in the app shell (feature 4,
   spec 0003 AC-4); it renders on every page, so feature 13 adds nothing for it.

## Code area

- `apps/web/src/features/honesty/` (trial store, hook, `TrialCounter`, `RunTrialCounter`,
  `ProcedureNote`, tests)
- `apps/web/src/app/ui/` (gallery section with every state)

## Requirements

- AC-1: Two runs with the same `structure_key` and different `pair_keys` (numbers tweaked) count
  toward the same `N` (U-4, R-9).
- AC-2: Re running an identical pair adds nothing to `N` or `M` (U-4).
- AC-3: `M` counts distinct pairs across every structure key this session (U-4).
- AC-4: The line reads "Trial #N for this rule structure · M this session" (U-4).
- AC-5: At `N ≥ 10` the overfit warning shows word for word (U-4).
- AC-6: With storage unavailable, the counters are hidden and the static warning shows (U-4).
- AC-7: The procedure note renders word for word (U-8).
- AC-8: The live badge shows on every page in live mode (U-2), covered by the shell.
- AC-9: Every state is in the `/ui` gallery, keyboard usable, axe clean, and holds at 375 px.

## Ratify

This decision was recorded by /develop, not deliberated. Run `/architect research honesty guards`
to deliberate and ratify it. Until then it stays flagged as an owed decision; it does not block
marking the feature `done`.

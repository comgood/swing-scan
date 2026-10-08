# 0008. Build the rule builder as typed condition rows over the frozen rule contract

**Date**: 2026-10-08
**Status**: Proposed, pending owner sign-off
**Authorized by**: /architect, run unattended overnight by the orchestrator lane; every open
question took /architect's recommended answer (listed below) and waits for the owner

## Summary

This spec designs scope feature 10: the editor where you build your own entry rule. You get up to
8 condition rows joined by AND; each row picks an indicator (with its window `n`, how many bars
ago, and a multiplier), an operator, and either a number or another indicator on the right. The
two templates load into it as editable starting points. The rule lives in the page link
(`?r=`), so a reload or a shared link reproduces it exactly, and a JSON panel lets you copy or
paste it. The engine already accepts every valid rule (spec 0005), so this is mostly web work: the
FE lane builds it against the mocks now, and the BE lane adds the R-3 to R-7 tests on custom rules
once feature 8's rule evaluator merges.

## Assumed decisions (pending owner sign-off)

The owner could not answer during this run. Each question took /architect's recommended answer;
the runner up is in [rationale.md](rationale.md).

1. **Where it lives.** The builder replaces the read only conditions text in the template
   workspace on `/` (spec 0005 AC-9), in `apps/web/src/features/rule-builder/`, with the scan
   results below it. Runner up: a separate `/builder` page.
2. **State.** One `useReducer` whose state is the contract `Rule` from `@swing-scan/api-client`
   plus a parallel list of stable row ids for React keys. Nothing else holds the rule. Runner up:
   a form library (React Hook Form): a second model of the same data.
3. **URL.** `?r=` is base64url (no padding) of the rule's UTF-8 compact JSON
   (`JSON.stringify` with no spaces), uncompressed. An unedited template keeps the short
   `?template=<id>` link; the first edit switches to `?r=`. Old `?template` links keep working.
   `router.replace`, never a new history entry per keystroke. Runner up: compressed `?r=`
   (lz-string): shorter, but not readable and one more dependency; 8 conditions fit in about
   1.5 KB anyway.
4. **Bad link.** A `?r=` that does not decode or parse to the `Rule` shape loads Breakout and
   shows an inline notice "This link's rule could not be read. Showing the Breakout template."
   A `?r=` that parses but fails server validation loads as is and shows the 422 on its rows.
5. **When it runs.** Loading a template or a link runs the scan at once (U-1). Edits do not; a
   "Run scan" button runs it, and the results show "Results are for the previous rule" until you
   run again. Runner up: auto run after a pause in typing (a scan per pause, and half typed rules
   would flash 422s).
6. **Validation.** The form prevents what the catalog makes impossible (an `n` on a price field,
   a ninth row, removing the last row) and shows range hints from `GET /indicators`; the
   server's 422 is the only judge of validity and is mapped to the field with
   `fieldErrorsFrom422` (U-7). No client copy of the range table beyond what the catalog sends.
7. **Row layout.** Left operand (indicator, `n`, "bars ago" for offset, "×" for mult), operator,
   right side with a Number or Indicator switch. Offset and mult show inline with their defaults
   (0 and 1); at 375 px the parts stack (U-6). No reorder: AND does not care about order.
   Runner up: hide offset and mult behind "More": hides part of the rule from you (ADR-013).
8. **Rows.** "Add condition" adds `close > sma(50)` as a neutral starting row; it is
   disabled at 8 with "A rule has at most 8 conditions". Remove is disabled on the last row.
9. **Right side switch.** Number to Indicator keeps nothing (starts `sma(50)`); Indicator to
   Number starts at 0. Changing an indicator resets `n` to the catalog default (only `rs` has
   one, 126), else 14, and sets `n` to `null` for a price field. 50 and 14 are builder
   constants, not catalog values; 14 is inside every windowed indicator's range (2 to 252, `rsi`
   2 to 50).
10. **JSON panel.** A collapsible panel shows the rule's JSON (pretty printed) with Copy. Paste
    and "Load" replaces the rule if the text parses to the `Rule` shape, else shows "Not a rule"
    and changes nothing. Runner up: live two way editing (cursor fights between the textarea and
    the rows).
11. **Rule name.** A "Name" field, defaulting to the template's name, else "My rule"; 1 to 40
    characters after trimming (the contract's `Name`); the field trims on input, so the rule
    always carries the trimmed value. It never changes the structure key (spec 0002).
12. **Backtest hand off.** A "Backtest this rule" link opens `/backtest?r=…` with the rule as
    it is now (edited, not the last run). Spec 0007 (feature 9, PR #26) reads `?r=` once this
    feature lands.
13. **BE share.** No new endpoint or contract change. After feature 8's evaluator merges, BE adds
    engine and API tests for R-3 to R-7 on custom rules, beyond the two templates.

## Requirements

**User stories**:
- As a researcher, I want to edit a template's conditions or write my own, so I can test my idea.
- As a researcher, I want the link to carry my exact rule, so a reload or a friend sees the same.
- As a researcher, I want an invalid rule to tell me which row and field is wrong, and the range.

**Acceptance criteria**:
- **AC-1** [R-1]: a rule serialised to JSON and parsed again is identical; `?r=` after a reload
  reproduces the same rule, row for row, including offsets, mults and the name.
- **AC-2** [R-1]: an unedited template shows `?template=<id>` (Breakout: no parameter); the first
  edit switches the link to `?r=`; an old `?template` link still loads that template.
- **AC-3**: a `?r=` that cannot be decoded or parsed loads Breakout with the notice in decision 4
  and removes `?r=`.
- **AC-4** [R-8]: after any add, edit or remove, the scan request's `rule` equals the rows
  exactly (UI to JSON parity), and loading JSON into the panel gives rows that serialise back to
  the same JSON.
- **AC-5**: up to 8 rows, at least 1; the add button is disabled at 8 and remove on the last row,
  each with a visible reason.
- **AC-6**: each row edits every contract field: the left operand's `ind`, `n` (only for
  windowed indicators, with the catalog range as a hint), `offset` (0 to 20), `mult` (0.1 to
  10); the operator (`>`, `<`, `>=`, `<=`, crosses above, crosses below); a Number or Indicator
  right side.
- **AC-7** [R-6, U-7]: a 422 shows its message on the exact field its `loc` names (for example
  row 3's right `n`), with the allowed range, and the rule stays as typed.
- **AC-8**: a template or link loads and runs at once, after the gate in spec 0005 AC-10 (the
  parameter is read and, for `?template`, `GET /templates` has loaded; a skeleton until then, no
  wasted scan); edits run only on "Run scan", and stale results are labelled until then.
- **AC-9** [R-10]: no hidden filter: the builder never adds a condition the rows do not show, and
  the templates show their `close > 5` row.
- **AC-10** [U-6]: at 375 px and 320 px rows stack with no sideways page scroll; every control
  has a label; the builder is keyboard usable and axe clean; every state is in the `/ui` gallery.
- **AC-11** [R-3, R-4, R-5, R-7] (BE): engine tests on custom rules: a crosses above is true only
  on the first bar above; `highest(5, offset 1)` excludes today; `close > sma(50)` with 30 bars
  is invalid on all 30; `rs(126)` lies in 0 to 99 and the best 126 day return gets 99.
- **AC-12** [R-6] (BE): through `POST /scan`, each R-6 case (unknown indicator, `n` out of range,
  offset over 20, 9 conditions, an empty list) answers 422 with `loc` and the range in `ctx`.
- **AC-13** [R-9]: covered by spec 0002 AC-9 (`structure_key` ignores numbers); the builder sends
  numbers as typed, so a numbers only edit keeps the key.

## Decision

**Chosen option**: Option 1: contract typed rows in one reducer, URL as the store.

**Implementation skills**: `nextjs-app-router-patterns` (`wshobson/agents`,
`.claude/skills/nextjs-app-router-patterns/`) · `shadcn` (`shadcn-ui/ui`, `.agents/skills/shadcn/`)
· `vercel-react-best-practices` (`vercel-labs/agent-skills`,
`.claude/skills/vercel-react-best-practices/`) · `python-testing-patterns` (`wshobson/agents`,
`.claude/skills/python-testing-patterns/`)

## Rationale

Reasoning and options: see [rationale.md](rationale.md).

## Feature design

**Data model** (browser only; the rule is the contract type):

| Piece | Shape |
|---|---|
| `BuilderState` | `rule: Schemas["Rule"]`, `rowIds: string[]` (same length as `rule.conditions`), `source: { template: string } \| "custom"`, `dirty: boolean` (edited since the last run) |
| actions | `load(rule, source)`, `add()`, `remove(i)`, `setLeft(i, operand)`, `setOp(i, op)`, `setRight(i, operand)`, `setName(name)`, `ran()` |
| URL | `?template=<id>` or `?r=<base64url(compact JSON)>`; never both |

**Files** (`apps/web/src/features/rule-builder/`): `reducer.ts`, `url-codec.ts`
(`encodeRule`, `decodeRule` returning `Rule | null`), `is-rule.ts` (shape guard, no range
checks), `condition-row.tsx`, `operand-fields.tsx`, `rule-builder.tsx`, `json-panel.tsx`, tests
beside each.

**API surface** (existing, spec 0002): `GET /indicators` (catalog: name, label, windowed, `n`
range and default), `GET /templates`, `POST /scan`. No change.

**Value sourcing**:

| Action | Value | Source |
|---|---|---|
| indicator picker | names, labels, `n` ranges and defaults | `GET /indicators` |
| new `n` after an indicator change | default | catalog `n_default`, else 14; none for price fields |
| offset and mult ranges | 0 to 20, 0.1 to 10 | spec 0002 contract (shown as hints; the 422 enforces) |
| new row | `close > sma(50)` | decision 8 |
| template rules | conditions and name | `GET /templates` |
| link | `?r=` | `encodeRule(state.rule)` |
| field errors | message and path | the 422 body through `fieldErrorsFrom422` |
| scan request | `rule` | `state.rule`, unchanged |

**Precise rules the build must not invent**:
- `n` is `null` (never missing) on price fields, matching the templates from `GET /templates`;
  `decodeRule` fills a missing `n` with `null` before the shape check, so AC-1 and AC-4 compare
  equal JSON.
- A number field keeps its text locally; the rule only takes a finite number. An empty or partial
  entry ("", "1.", "-") leaves the last valid value in the rule and marks the field "Enter a
  number"; NaN and Infinity never reach the rule (the contract forbids them).
- `encodeRule` and `decodeRule` use `TextEncoder` and `TextDecoder` around base64url, so names
  with any characters round trip. A `?r=` longer than 8 KB is rejected before decoding (treated
  as a bad link).
- `is-rule.ts` checks: `name` is a string; `conditions` is an array of 1 to 8; each `left` has
  `kind: "ind"`, an `ind` from the catalog's names, `n` a whole number or null, `offset` a whole
  number, `mult` a number; `op` is one of the six; `right` is that or `{kind: "value", value:
  number}`; no unknown keys. Ranges are left to the server.
- The link: after the first edit it is `?r=` for good (a "dirty" flag, no deep comparison with
  the templates); picking a template again returns to `?template`. URL writes are debounced
  300 ms; the state updates at once.
- `as_of` is never sent (spec 0005 AC-6).
- Every number shown (hints, ranges) goes through `src/lib/format.ts`.

**422 path to control** (from `fieldErrorsFrom422`; the shown text is the 422's `msg`, which
carries the range for range errors, for example "must be between 2 and 50"):

| `loc` after `rule` | Shown on |
|---|---|
| `conditions.i.left.ind` / `.n` / `.offset` / `.mult` | that row's left field |
| `conditions.i.op` | that row's operator |
| `conditions.i.right.<field>` or `conditions.i.right.value` | that row's right field |
| `conditions.i.right` or `conditions.i.left` (a bad `kind` tag) | the row's right or left group |
| `conditions.i` (anything else under a row) | the row, as a row level message |
| `conditions` (0 or 9 rows; unreachable from the form) | above the rows |
| `name` | the Name field |
| anything unmatched | above the rows, never dropped |

**Result states**: loading (the existing warm up notice after 1.5 s), ok, stale ("Results are
for the previous rule. Run scan to update."), 422 (fields marked, previous results kept and
labelled stale), error (`ErrorState` with retry), 501 ("Not built yet").

**`/ui` gallery entries**: a default row, an indicator right side, 8 rows (add disabled), one
row (remove disabled), a 422 on a right `n`, the bad link notice, the JSON panel with "Not a
rule", and the stale label.

**Key invariants**:
- The request's `rule` is `state.rule`; there is no second copy to drift (R-8).
- `rowIds.length === rule.conditions.length` after every action.
- `decodeRule(encodeRule(r))` deep equals `r` for every valid `r`.
- The builder never injects a condition or a filter (ADR-013).

**Security model**: no auth. A `?r=` is untrusted input: decoded with `atob` and `JSON.parse`
in a try, checked by the shape guard, rendered as text only, and validated by the server before
any use. No `eval`, no `dangerouslySetInnerHTML`.

**Configuration required**: none.

**Critical test scenarios**:
- Round trip: every template and a rule using every field encode and decode equal, verifies **AC-1**
- Links: edit switches `?template` to `?r`; an old `?template` loads; garbage `?r` falls back, verifies **AC-2**, **AC-3**
- Parity: add, edit and remove rows, then assert the MSW captured `rule` equals the rows, verifies **AC-4**
- Limits: 8 rows disable add, 1 row disables remove, verifies **AC-5**
- 422: `422.rule.n_out_of_range` lands on its row's `n`, `422.rule.unknown_indicator` on its
  `ind`, and `422.rule.too_many_conditions` above the rows; a left versus right `n` case, verifies **AC-7**
- Run: template loads and runs; an edit marks results stale until "Run scan", verifies **AC-8**
- 375 px, keyboard and axe on the builder and its gallery entries, verifies **AC-10**
- Engine: R-3, R-4, R-5 and R-7 fixtures on custom rules; API: each R-6 case, verifies **AC-11**, **AC-12**

## Build plan

Tracer Bullet: one row editable end to end first, then the rest. FE starts now on the mocks; BE
starts when feature 8's evaluator merges.

**FE lane**
0. The builder is its own component in `features/rule-builder/` with its own tests and gallery
   entries, so it does not wait on feature 8's workspace; it is mounted in the workspace (in
   place of the read only conditions text) once feature 8's FE workspace merges.
1. Thread: reducer, one editable row (left indicator and `n`, operator, number right side), "Run
   scan" posting `state.rule` to the mocked `/scan`, parity test. Satisfies **AC-4**, **AC-8**
2. Full rows: offset, mult, indicator right side, add and remove with limits, catalog hints,
   422 mapping. Satisfies **AC-5**, **AC-6**, **AC-7**, **AC-9**
3. Links and JSON: `url-codec`, `?template` to `?r` switch, bad link fallback, JSON panel, name
   field, "Backtest this rule" link. Satisfies **AC-1**, **AC-2**, **AC-3**
4. Finish: 375 px and 320 px layout, keyboard, axe, `/ui` gallery states; switch to the real API
   at gate G3. Satisfies **AC-10**

**BE lane** (after feature 8's rule evaluator merges)
5. Engine tests for R-3, R-4, R-5 and R-7 on custom rules, and API tests for every R-6 case
   through `/scan`. Satisfies **AC-11**, **AC-12** (AC-13 needs no new work: spec 0002 AC-9)

## Consequences

**Positive**:
- No contract change and no new endpoint: the engine work was done once in feature 8.
- The link is the whole state, so sharing and reload need no storage (ADR-002).

**Negative / tradeoffs**:
- A long rule makes a long link (about 2 KB for 8 conditions); fine for browsers and chat apps,
  ugly to read.
- Results can be stale until you press "Run scan"; the label makes it visible, but it is one more
  click than auto run.
- The form trusts the server for ranges, so a bad `n` is only flagged after a run (with a hint
  shown beforehand).

**Neutral**:
- Feature 9's report page switches from `?template=` to `?r=` when this lands.

## Follow-up

- [ ] Owner sign-off on the thirteen assumed decisions above.
- [ ] Feature 9 FE reads `?r=` on `/backtest` once this feature merges.
- [ ] OR groups stay Stretch (ADR-013); the reducer keeps a flat list.

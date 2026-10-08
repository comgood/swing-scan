# 0008. Rule builder: decision record

## Context

Scope feature 10 lets you build your own entry rule: a flat AND list of up to 8 conditions over the
indicator registry, numbers or indicators on the right side, crosses, offsets and multipliers,
with clear validation, and the two templates as editable starting points. Doc 01 R-1 to R-10,
U-6 and U-7 set the behaviour; doc 02 §5.2 and ADR-013 fix the rule model (flat AND, at most 8,
no hidden filters); spec 0002 freezes the `Rule` contract and its 422 shape (every R-6 case
already returns a `loc` and a range); spec 0005 built the whole engine core, so the engine already
evaluates any valid rule. ADR-002 says state lives in the URL and a JSON panel, not a database.

What is open is almost all on the web side: where the builder lives, how its state is held, how
the rule goes into the link, what happens with a bad link, when a scan runs, how much the form
validates on its own, how a row is laid out, how rows are added and removed, and what the JSON
panel does. On the BE side, only the tests on custom rules (R-3 to R-7) remain.

Forces: the FE lane builds against mocks first (MSW, `contracts/mocks/`); BE work waits for
feature 8's rule evaluator to merge. The web app is a static export (no server routes), must hold
at 375 px (U-6), and must show a 422 on the right field (U-7). One source of truth for the rule
keeps the R-8 parity test meaningful.

## Options considered

### Option 1: Contract typed rows in one reducer, the URL as the store (chosen)

The builder's state is the contract `Rule` itself plus row ids; each row edits its condition in
place; the link carries the rule; the server validates.

**Pros**:
- No second model of the rule, so the request is the state (R-8 by construction).
- Generated types catch any contract drift at compile time.

**Cons**:
- Range hints and messages come mostly from the server, after a run.

### Option 2: A form library with a client schema

React Hook Form with a Zod schema mirroring the contract's ranges.

**Pros**:
- Instant per field errors before a run.

**Cons**:
- A hand written copy of the range table that can drift from the Pydantic contract; the 422
  mapping is still needed, so two validators to keep in step.

### Option 3: A text rule language

Type rules as text (`close > highest(252)[1] and …`) and parse them in the browser.

**Pros**:
- Compact for experts, easy to share.

**Cons**:
- A parser to build and test, harder errors for beginners, and a second grammar beside the JSON
  contract; not what the scope describes.

### Sub decisions (each with its runner up)

| Question | Chosen | Runner up and why not |
|---|---|---|
| Where | replaces the conditions text on `/` | a separate `/builder` page: splits the rule from its results |
| `?r=` encoding | base64url of compact JSON | lz-string compression: shorter but opaque and a new dependency |
| Template links | keep `?template=<id>` until the first edit | always `?r=`: old links and short links lost |
| Bad link | Breakout plus a notice | an error page: a dead end for a shared link |
| Run | on load, then on "Run scan" | auto run on pause: scans per keystroke, flashing 422s |
| Validation | catalog hints, server 422 is the judge | full client schema: a second copy of the ranges |
| Offset and mult | always visible with defaults | behind "More": parts of the rule out of sight (ADR-013 spirit) |
| New row | `close > sma(50)` | an empty row: an invalid request until filled in |
| Reorder | none | up and down buttons: AND ignores order; only the column order changes |
| JSON panel | copy, and paste then "Load" | live two way editing: cursor fights between panel and rows |

## Rationale

Option 1 is the smallest design that meets R-8 by construction: the scan request is the reducer's
state, so UI to JSON parity cannot drift. It reuses what is already built and tested: the
generated `Rule` type, the catalog endpoint for labels and ranges, and `fieldErrorsFrom422` for
U-7. Option 2 would buy instant errors at the cost of a duplicated range table, the classic way a
client and server disagree; the catalog hints give most of that benefit without the copy. Option 3
is a different product.

The URL decisions keep sharing honest and simple: the link is the whole state, short for an
unedited template and exact for anything else, and a bad link degrades to a working page rather
than an error. Running on demand, with stale results labelled, avoids a scan per keystroke on a
Lambda with a cold start, while still giving U-1's instant first scan.

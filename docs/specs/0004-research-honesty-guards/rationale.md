# 0004. Research honesty guards: decision record

## Context

Swing Scan lets you tweak a rule's numbers and rerun in seconds. That speed is also the trap: try
enough variants and one of them looks great on in sample (IS) data by luck. Doc 01 U-4 and doc 02
§7.5 answer this with a trial counter keyed on the rule's structure (numbers stripped), so every
tweak of the same idea counts against it, plus a warning at 10 trials and a static warning when
the counter cannot run. U-8 adds a one line procedure note under the exit lab table.

The docs fix the key, the increment rule, the copy, the threshold and the fallback, but leave four
things open: what the session total counts, what "storage unavailable" means when only one store
fails, how the seen pairs are laid out in storage, and when a run "completes". /develop built the
feature on an assumption for each (status `Assumed`); this record deliberates them.

Forces: the stack has no database, no auth and no background jobs (AGENTS.md), and the web app is
a static export, so any count lives in the browser. The trial keys are already frozen in the
contract (spec 0002, computed server side by `engine/contracts/trial.py`). The cost target is $0.
The counter is a behavioural nudge in a portfolio project, not an audit trail.

## Options considered

### Option 1: Browser storage keyed by the response's trial keys (chosen)

Each 200 backtest response carries `trial.structure_key` and `trial.pair_keys`. The browser adds
the pairs to a per structure key set in localStorage and to a session set in sessionStorage; `N`
and `M` are the set sizes.

**Pros**:
- No backend, no cost, works on the static export.
- The engine is the only place keys are computed, so there is one canonical form.
- Sets make "re running an identical pair adds nothing" true by construction.

**Cons**:
- Per browser: a new device or cleared site data resets the count.
- Two stores can fail independently, which needs a rule (see the assumed decisions).

### Option 2: Hash the rule in the browser

The browser computes `structure_key` and `pair_key` from the rule it sent, with Web Crypto.

**Pros**:
- Works even before a response arrives.

**Cons**:
- Two implementations of the canonical form (Python and TypeScript) that must stay byte equal;
  any drift silently splits one structure into two counters.
- Counts runs that later fail, which are not trials you looked at.

### Option 3: Count on the server

The API keeps per visitor counts.

**Pros**:
- Survives device changes.

**Cons**:
- Needs a database and an identity for the visitor, both ruled out by AGENTS.md and spec 0001.
- Costs money and adds a privacy surface for no research benefit.

### Sub decisions (each with its runner up)

| Question | Chosen | Runner up and why not |
|---|---|---|
| What `M` counts | distinct pairs this session, across structures | every completed run: a re run would inflate it |
| One store fails | hide both, show the static warning | degrade each alone: half a line looks like a real count |
| Layout | one localStorage entry per structure key | one big map: every run rewrites all history |
| When a run completes | 200 response on screen | on send: failed runs would count |
| Session pair seen in an earlier session | counts once toward `M`, not again toward `N` | skip it in `M`: you did look at it this session |

## Rationale

Option 1 is the only one that fits the forces. The no database rule removes Option 3 outright, and
Option 2 duplicates the canonical form across two languages, which is exactly the kind of quiet
drift that would make the counter lie (two structure keys for one idea means the warning never
fires). Taking the keys from the response keeps spec 0002 the single source of truth and means a
run is counted only once you have actually seen its result.

The sub decisions all lean the same way: when in doubt, show less and warn more. Hiding both
counters when either store fails, rather than showing a partial number, keeps the honest fallback
(the static warning) as the default. Counting distinct pairs for `M` keeps `M` consistent with
`N`'s rule, so a re run never looks like more research. The per structure key layout keeps each
write small and lets a corrupt entry damage only one structure's history.

The accepted cost is that the count is per browser. For a nudge in a portfolio project that is the
right trade; the README's "Limits of the research" carries the durable version of the procedure.

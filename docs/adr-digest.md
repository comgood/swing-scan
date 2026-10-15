# ADR digest

Seventeen architecture decisions were recorded before the build, in
[doc 02 §12](02-technical-design-and-roadmap.md#12-architecture-decision-records), each with the
alternatives it beat and a **"revisit when"** trigger. This page tracks what actually happened to
each one, which is the part a decision record usually never gets.

The short version: **fifteen held, one trigger fired and was accepted rather than acted on, and
one checkpoint resolved against the decision's own fallback.** The ones worth reading about are
005, 006 with 016, and 017.

| ADR | Decision | Revisit when | What happened |
|---|---|---|---|
| 001 | API on AWS Lambda (container, Function URL, Web Adapter) | cold start > 8 s, or image > 1 GB | **Held.** Cold start measured **2.66 s** on an idle function (2026-10-14), against a 6 s goal and the 8 s trigger. The post deploy first call is a different and much slower number (9.33 s, then 13.94 s on the same code), because Lambda optimises each new image once; `infra/README.md` §6 keeps the two apart |
| 002 | No database. URL, JSON panel, browser storage | saved rules, or a server side trial log | **Held.** The rule and exit configs round trip through a base64url URL (R-1), and the trial counter lives in browser storage |
| 003 | Public data is synthetic; live data and notes stay local | a licensed data plan exists | **Held,** and enforced rather than trusted: the D-6 guard plus gitleaks run pre commit and in CI, and `data/` and `research/` are gitignored. Verified 2026-10-16 after a real live load left the tree clean |
| 004 | Parquet in the image is the only bar store | data refreshes, or > 200 MB | **Held.** About 10 to 20 MB of synthetic Parquet ships in the image |
| 005 | Synchronous backtests and exit labs | **p95 > 10 s**, or payload near 6 MB | **Trigger fired, deviation accepted.** The 6 config exit lab runs **16.5 to 18.9 s** warm on the deployed function, which is over the 10 s the ADR set as its "move to a queue" line. Nothing was moved to a queue: at 17 s the call still answers inside Lambda's 30 s timeout with 11 s to spare, and X-7's budget was reset to 25 s from that measurement. The payload half of the trigger is nowhere near: 716 KB against the 6 MB cap. **This is a known, deliberate deviation**, not an oversight, and it is the first thing to revisit if the lab gets slower or the universe grows |
| 006 | NumPy and plain Python loops, no Numba | profiling says so | **Held, and profiled rather than assumed.** cProfile over 3.73M bar steps found only ~8% of a warm run in exit logic and ~92% in object and interpreter overhead. Removing the object churn from the per bar path (one reused `BarView`, exits pre split by kind) gave 1.43x locally and 1.31x on Lambda with no logic change. Numba was never needed; see 016 for the vectorised alternative |
| 007 | Adjusted prices only | planted splits, or raw price filters | **Held.** The live loader requests `adjustment=all` |
| 008 | Pluggable `Exit` protocol with one `step()`, portfolio day loop plus per trade loop | R targets (Stretch), intrabar paths | **Held, and load bearing.** `step()` is the only place exit precedence exists, enforced as an engine invariant ("never special case an exit outside it") and relied on by parity: both loops call it, so trade mode and portfolio mode cannot disagree about an exit. This is the decision that made the 006 speed work safe |
| 009 | No auth | hosted live mode | **Held.** Every route is public by design; the demo is read only on synthetic data, and live mode is loopback only (D-5) |
| 010 | IaC deferred to a CLI script; Terraform is Stretch | **first post week task** | **Held, and now due.** Infrastructure is still the scripted AWS CLI steps in `infra/README.md`. The trigger has arrived: this is the oldest outstanding decision debt in the project |
| 011 | Dense in memory arrays | universe > 5k, or > 20 years | **Held.** 500 tickers over 5 years |
| 012 | Trial counter keyed on rule **structure** (numbers stripped) plus a session total, warning at 10 | a database exists | **Held, and exercised.** Research note 0001 reports structure key `5cfef491…` at trial 1, and the exit lab and the portfolio run of the same rule correctly shared that key while contributing different pair keys |
| 013 | Flat AND, at most 8 conditions, no hidden filters | OR groups (Stretch) | **Held.** Price filters are visible conditions, never an implicit `min_price` |
| 014 | Rising edge entries, 10 bar signal cooldown; exit lab is trade mode only, with a random baseline | Stretch item 3 | **Held.** Identical entries across configs is asserted by oracle O19, which is what makes "only the exit changed" a fact rather than a claim |
| 015 | Indicator cache keyed `ind(n)`, LRU 64 per `data_version` | memory pressure | **Held** |
| 016 | Per trade Python loop first; vectorised E × H windows only if X-7 misses | **Day 4 checkpoint** | **Checkpoint resolved 2026-10-15, late.** X-7 did miss its original 10 s, so the fallback was costed properly: both risky pieces were prototyped (`argmax` first true at 38x, shifted `maximum.accumulate` for the trailing high water mark at 12x, zero mismatches over 18,566 entries each), giving **4 to 5 h and about 6 s deployed** — not the 2 h doc 02 estimated. **Not taken.** The rewrite would put a second copy of the exit precedence beside `step()`, which 008 exists to prevent, and nothing breaks at 17 s. The budget was reset from measurement instead. The costing stands if the decision is ever revisited |
| 017 | Random entry baseline: uniform alive (ticker, t), stratified IS/OOS, seed 42 shown, same exits | survivorship free data (Stretch) | **Held, and it earned its place.** In research note 0001 the chosen config's out of sample expectancy quadrupled (1.26% → 5.34%) while its **edge over random fell 78%** (0.026 → 0.006 per bar), because random entries in the same window went 0.40% → 5.01%. Without this column the note would have concluded the rule held up out of sample. It did not; the market did |

## What the triggers were worth

Four of the seventeen carried a number rather than a feeling, and those are the four that did
something:

- **001's 8 s** was met with 2.66 s, and forced a distinction nobody had drawn between a visitor's
  cold start and the slower first call after a deploy.
- **005's 10 s p95** fired, and was overruled on purpose with the reasoning written down.
- **006's "profiling says so"** sent us to a profiler instead of a rewrite, and the profiler said
  the opposite of what was assumed: the cost was object churn, not arithmetic.
- **016's Day 4 checkpoint** was missed as a date and honoured as a gate, eleven days late.

The thirteen with softer triggers ("a database exists", "memory pressure") have simply not been
tested. That is the honest reading: a revisit trigger is only useful if it names a number and
something measures it.

One assumption was flatly wrong and is worth recording beside the decisions, since it shaped two
of them. Doc 02's **A4** asserted that a warm Lambda runs the 6 config lab in under 10 s, "measured
on Day 4". It was never measured on Day 4, and when it finally was, the answer was 24.85 s before
the 006 speed work and 18.94 s after. Doc 02's **A3** assumed Alpaca's free plan included `feed=sip`
from 2016; it does not, so the live set starts 2017-11-15 and holds 43% fewer bars than planned.
Both are struck through and corrected in place rather than quietly edited.

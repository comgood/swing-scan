# 0005. Template scan: rationale

The decision record behind [index.md](index.md). `/develop` builds from `index.md` and skips this file.

## Context

Feature 8 is the first time the product does its core job: run a rule over the market and show what matches. Until now the scan endpoint only validates requests and answers 501. The landing page is the scaffold intro inside the design system's shell. A first visit must open on the Breakout template with today's hits under the synthetic banner (U-1), and the warm scan must answer in under a second for 500 tickers (S-4).

Three forces shape it. First, the scan and the backtest must agree on what an entry is (S-3, and the oracles B-14 to B-16), so the entry signal logic built here is what feature 9 reuses. Second, the contract already lets a request carry any valid rule, with 14 indicators, six operators, offsets and multipliers. Feature 10 adds only the UI to build those rules. Third, the lanes run in parallel: the DI lane is building the synthetic market (feature 7) right now, and the FE lane has to work against the frozen mocks until the real `/scan` lands.

Much is already settled upstream. Doc 02 §6 fixes the indicator cache (Polars over ticker, least recently used, 64 columns per data version), validity, and the entry signal formula. The owner's ruling fixes the window and EMA conventions (doc 02 §5.2). Spec 0002 freezes every request and response shape, the column label grammar, `new_today` with the cooldown, and the row order. Spec 0003 supplies the table, formatters, warm up notice, and error and empty states. What was open is the landing page before the builder exists, how much of the engine to build now, where the market comes from, and a few behaviours around them.

## Options considered

### Option 1: Templates only, minimal engine

Build only the indicators and operators the two templates use, and answer 422 for anything else until feature 10.

**Pros**:
- The smallest build that meets feature 8's own criteria.
- Less code for the owner to review on the critical path.

**Cons**:
- `/scan` would reject rules the frozen contract calls valid, a temporary contract mismatch that QA and FE would have to work around.
- Feature 10 would reopen the engine (crosses, `rs`, `rsi`, `atr`), the riskiest code, during a UI feature.

### Option 2: Full engine core, read only workspace (chosen)

Build all 14 indicators, every operator, validity and the shared entry signal function now, cached per data version. Serve `/scan` on the generated market, and put a template dropdown, the read only conditions and the results table on `/`.

**Pros**:
- One engine, built and tested once, serves the scan, the backtest and the builder.
- The page is useful from the first deploy, and feature 10 replaces only the conditions text.

**Cons**:
- More engine work in feature 8 than its own criteria strictly need.
- `/scan` can't go live until feature 7 merges.

### Option 3: Precomputed template results

Compute both templates' results when the API starts and serve them from memory; compute other rules on demand.

**Pros**:
- The fastest possible first visit, even on a cold start.

**Cons**:
- Two code paths (stored and computed) that must stay identical, which S-3 parity would then have to cover twice.
- `as_of` other than the last session needs the computed path anyway.

## Rationale

Option 2 fits the forces. The contract already promises any valid rule, so building the full compiler now avoids a period where the API rejects valid requests, and it keeps the riskiest code (indicators, crosses, entry signals) in one BE feature under one review. Feature 9 depends on the same entry signal function, and the oracles already pin its behaviour, so building it once here is cheaper than building it twice. Option 1 saves engine work now but moves it into feature 10, where it would land under a UI deadline. Option 3 optimizes a cold start that the warm cache already handles, at the cost of a second path that parity tests must chase.

You confirmed the page and behaviour choices one by one:
- a template dropdown with read only conditions and the table (rather than a builder shell that would design feature 10 early);
- the latest session only;
- pages of 50;
- a "New" badge with new hits first;
- `?template` in the URL;
- feature 7's market with fixtures until then;
- warming the cache at start;
- all indicators and operators now;
- number formats by indicator kind;
- a scan log line.

### Choices made on your behalf (RECOMMEND items)

- **Wilder conventions for `atr` and `rsi`.** Seeded with the simple mean of the first n true ranges or changes, then Wilder smoothing. This is the standard definition charting tools use, so the numbers a visitor checks elsewhere match. Runner up: an exponential seed, which drifts from common tools.
- **`atr` on a ticker's first bar uses `high − low`.** There's no previous close to compare with, and this avoids losing a bar of history. Runner up: start `atr` one bar later.
- **`rs` ranking with ties taking the highest rank.** The top return always gets 99 (R-7), even in a tie. Runner up: ties take the lowest rank, which can leave no ticker at 99.
- **`rs` excludes the benchmark and counts only tickers alive with a valid `ret(n)`** (spec 0002 excludes the benchmark from the `rs` universe). Runner up: count every listed ticker, which mixes in tickers with no return yet.
- **The conditions text reuses spec 0002's column label grammar.** The conditions and the table headers then read the same. Runner up: a prose rendering, a second grammar to keep in step.
- **Operand number formats come from the rule's operand order, not from parsing labels.** The `columns` order is defined from the rule (spec 0002), so the kind is known exactly. Parsing labels would break on new indicators.
- **Switching templates replaces the URL instead of pushing history.** Back then leaves the site instead of stepping through template switches. Runner up: push, which fills history with every switch.
- **The FE caches the templates and the scan per template with `staleTime: Infinity`.** The data doesn't change within a deploy. Runner up: refetch on focus, which wastes Lambda calls.
- **No new rate limiter.** The Lambda's reserved concurrency of 5 and the warm budget bound the cost (spec 0001). Runner up: an API gateway limiter, a new service that needs an ADR.
- **The route keeps answering 501 until a market is loaded.** This keeps spec 0002's meaning of 501 ("not available yet"). Runner up: 503, which the web app doesn't map yet.

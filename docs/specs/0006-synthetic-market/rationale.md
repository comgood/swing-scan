# 0006. Synthetic market: decision record

## Context

Swing Scan must run with no data cost and no vendor licence, in CI and on the deployed demo (doc
02 A2, §3; spec 0001). So the default data mode is an invented market. Doc 02 fixes its shape: 500
invented tickers over about 5 years, regimes, sectors, fat tails, a documented planted momentum
term, about 5% delistings (at least 20), about 5% mid sample listings, adjusted prices only, a
`DEMO-INDEX` benchmark, and the CLI `python -m engine.synthetic --seed 42 --out /data`.

No doc fixes the numbers inside it: the calendar, how regimes are scheduled, how a bear segment is
guaranteed, the momentum term, how the benchmark is built, the ticker scheme, the delisting stories,
the precision, and the version string. These values feed the D-1 to D-3 checks, the golden files,
every scan and backtest, and the published research note. /develop built the generator on an
assumption (status `Assumed`); this record deliberates it.

Forces: AGENTS.md forbids committing `data/` or Parquet and calling vendor APIs in CI; the engine
domain must stay pure (no I/O); the API runs in a Lambda container, where a cold start should not
regenerate data; the project is a portfolio piece whose research note must be honest about any
planted effect.

## Options considered

### Option 1: Seeded NumPy factor model, generated at build time (chosen)

A market factor with scheduled regimes, sector factors, per ticker beta and fat tailed noise, a
planted momentum term, and explicit listing and delisting paths, all from one seeded generator.

**Pros**:
- Every D criterion can be guaranteed by construction, for any seed.
- Realistic enough for the indicators and exits to behave like they do on real data.
- All numbers in one config, versioned.

**Cons**:
- The most code of the options, and a Python loop for the momentum walk (still well under a second).
- Determinism depends on the locked NumPy version and the CPU architecture.

### Option 2: Independent random walk per ticker

Geometric Brownian motion per ticker, no shared factors.

**Pros**:
- Tiny and obviously correct.

**Cons**:
- No regimes and no market wide bear, so D-3 needs a hack.
- No correlation and no edge: every rule's result is pure noise, which makes a dull demo and an
  untestable research note.

### Option 3: Commit a fixed generated dataset

Generate once and check the Parquet files in.

**Pros**:
- No generation at build time; determinism across library versions for free.

**Cons**:
- AGENTS.md forbids committing `*.parquet` and `data/`; tens of MB in git history.

### Option 4: Resample real market data

Block bootstrap of real returns.

**Pros**:
- The most realistic distributions.

**Cons**:
- Needs real data in the build, which breaks the no vendor in CI rule and raises licence questions.

### Sub decisions

| Question | Chosen | Runner up and why not |
|---|---|---|
| Random source | one `default_rng(seed)`, fixed draw order | one generator per ticker: draw order harder to keep stable |
| Calendar | 1,260 weekdays from 2021-01-04, no holidays | exchange calendar: a dependency for no gain |
| Bear | one planted bear, total log return in [−0.45, −0.30] | random only: D-3 fails for some seeds |
| Benchmark | the market factor itself | equal weight of tickers: inherits delistings and the edge |
| Edge | 63 session momentum, coef 0.10, clipped | none: nothing for the research note to find |
| Delisting stories | bankruptcy slide or acquisition jump then flat | no story: exits at prices that tell nothing |
| Version | `synthetic-1`, bumped by hand | content hash: exact but unreadable in the header |
| Determinism scope | same seed, locked libraries, same architecture | pure Python PRNG: portable but slow and more code |

## Rationale

Option 1 is the only option that meets every force at once. Options 3 and 4 break hard repo rules
(no committed data, no vendor calls in CI). Option 2 is simpler but cannot guarantee D-3 without a
special case and, worse, gives the research tools nothing real to find, so the portfolio story
("the tools detect a known effect, and here is the honest caveat") disappears.

Planting the bear and the delistings, instead of hoping randomness provides them, turns D-3 from a
property of seed 42 into a property of the model, which the tests check across several seeds.
Taking the benchmark from the market factor keeps it clean of survivorship and of the planted edge,
so "edge versus benchmark" means what it says.

Scoping determinism to the locked library versions is the honest trade. NumPy does not promise its
`Generator` streams across releases, but `uv.lock` pins the version. Rounding to 4 decimals absorbs most last bit float differences,
but not all: `exp` and `log` can differ between arm64 and x86, and a value near a rounding edge
can flip, so the promise is scoped to the build architecture (x86_64). A library upgrade then becomes a deliberate
data change (bump the version, refresh goldens) rather than a silent drift.

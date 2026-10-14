# 01: Market Research and Product Spec: "Setup Lab" Swing Strategy and Exit Research Workbench

| | |
|---|---|
| **Author** | Product Manager (design team: PM, Senior Architect, Devil's Advocate) |
| **Date** | 2026-10-06 |
| **Status** | **v3.3 (final).** Applies the DA's v4 addendum (§A5) with the lead's rulings on the A4 conflicts: MA exit at next open, structure-keyed trial counter, valid rising edge + cooldown + horizon, ≤ 8 conditions, `02`'s indicator names and MAE rule, per-trade exit-lab metrics + random baseline, IS-only highlight. ≈ 53 h P50 / ≈ 60 h P80. v3.2 cut to ≈ 51 h; v3 added Research mode; earlier versions are in git history. |
| **Companion docs** | `01a-free-data-sources.md` (data), `02-technical-design-and-roadmap.md` (Architect; being re-aligned in parallel), `03-devils-advocate-review.md` |

> **Binding frame:**
> - **$0/month**, non-commercial learning and portfolio project for practising agentic coding.
> - **≤ 1 week** with AI coding agents. Hours are being re-estimated by the Architect (see §5.1).
> - **Public repo.** The public demo is **synthetic data only**. Real data runs **locally only**.
> - **Backtesting is compulsory.** Week 1 now centres on **Research mode**: the **rule builder** and the **exit lab**.

---

## 1. Summary

**Long-term goal (owner):** find **profitable swing strategies and sensible exits**.

**Week-1 deliverable:** *Setup Lab*, a research workbench for that goal:
1. **Build an entry rule** from simple conditions (e.g. `close > highest(252)[1]` AND `volume > 1.5 × avg_volume(50)`), or start from a template.
2. **See today's hits** in a table.
3. **Backtest it** honestly: next-open fills, slippage, equal weight, max N positions, delisting exits.
4. **Compare 2–6 exit strategies on the same entries** (stops, % targets, trailing stops, MA exits, time stops). Use MAE/MFE columns (maximum adverse/favourable excursion: how far each trade went against you and in your favour) to place stops and targets.
5. Every result shows **in-sample vs out-of-sample** columns, an **assumptions header**, a **trial counter**, and (in the exit lab) an **"edge vs random entries"** column.

**Honesty about what week 1 can prove.** Live research runs on Alpaca free data: **~500 *current* S&P 500 names since 2016, survivors only**. That universe is biased upward twice:
- **Survivorship:** dead companies are missing.
- **Index selection:** today's members are partly members *because* they went up.

Plus a third: **one regime**. The OOS window (≈ 2023-07 → 2026-10) is mostly a bull market. The full list is in §8.1. The random-entry baseline (§6.5) cancels much of this shared uplift.

So **week-1 findings are hypotheses, not proof.** They earn confidence only after the Later steps:
- delisted-inclusive data (Massive free, 2 years, plus a growing archive);
- walk-forward testing;
- paper trading forward.

The synthetic market is for **demoing and testing correctness**, not for finding strategies. Its "edge" is planted by us.

**Why it's a good portfolio piece:**
- A real compute engine: a rule language compiled to Polars, an event-driven exit simulator, MAE/MFE.
- A clean full-stack app with $0 deploy and CI.
- Tests that prove the classic backtest traps are avoided: planted delistings, a poisoned-future look-ahead test, and hand-computed oracle trades for every exit type.

**What it is not:** a product, a market-gap claim, or trading advice. Many tools backtest rules (§3). We position it as **"a learning build of an honest entry/exit research loop."**

---

## 2. Persona and jobs-to-be-done

**Primary user: the owner, as researcher.** The owner wants to answer, with evidence:
- J1: *"Does this entry idea have any edge after costs?"*
- J2: *"For a given entry, which exit (fixed stop, ATR stop, target, trailing, MA, time) gives the best risk-adjusted result, and does that hold out of sample?"*
- J3: *"Where should my stop and target sit, given how far trades typically go against and for me?"* (MAE/MFE)
- J4: *"Am I fooling myself by testing too many variants?"* (trial counter, OOS)

**Secondary persona: "Sam", a part-time swing trader** (breakouts, pullbacks, mean reversion; holds days to weeks; uses Finviz free + TradingView). Sam is the user the public demo is shaped for.

---

## 3. Market research (trimmed)

Prices are 2026 list prices from review sites, about ±20%. The full v1 research is in git history.

| Product | Price (USD/mo) | Scanning | Backtesting / exits | Good | Bad |
|---|---|---|---|---|---|
| **TradingView** | Free–$59.95 | Broad screener; Pine Screener limited (1 indicator per screen) | Strong **single-symbol** Pine strategies; any exit you can code | Best charts, huge community | No scan- or portfolio-level tests; coding required |
| **Finviz Free / Elite** | Free / $39.50 | ~70 fixed filters | **Elite backtester**: ~24 yrs, S&P/Russell universes, stops, time exits, SPY benchmark | Fast, cheap | Rigid filters and exits |
| **Trade Ideas** | $89–$254 | Deepest real-time scanner; NL builder | **OddsMaker** scan backtests | True scan-level testing | Day-trading focus, expensive |
| **TrendSpider** | $54–$321 | Multi-timeframe, AI scans | **Best no-code web backtester**; stops, targets, trailing; Group Strategy Tester | Automation | Pricey, dense UI |
| **Portfolio123** | Paid tiers | Factor screens | **Point-in-time sims incl. dead companies** | Rigorous | Fundamentals/quant oriented |
| **MarketInOut** | Low-cost | Large criteria set | **Survivorship-bias-free screen backtester** | Cheap, honest | Dated UI |
| **QuantConnect** | Free tier | Code only | Full engine, **bias-free data** | Professional-grade | Code-first, not a scanner UX |
| **AmiBroker/RealTest + Norgate** | ~$35/mo data + licence | Code | **Gold standard**: portfolio-level, walk-forward, MAE/MFE | Bias-free data | Desktop, Windows, code-heavy |
| **TC2000 / StockCharts** | $20–$100 | Formula/text scans | Limited / none | Fast EOD scanning | No real testing |
| **MarketSurge / Deepvue** | $41–$150+ | Growth-trader screens | **None** | IBD/Minervini-style ratings | No testing |
| **Stock Rover / Koyfin / Barchart / thinkorswim** | Free–$110 | Fundamental-first or broker scanners | Historical screens or per-symbol only | Deep data | Weak for swing research |
| **AI entrants** (QuoTrend, StocksFast, IBKR LLM screener, ChartingLens, Tickeron, Danelfin) | Varies | NL → filters | Mostly none | NL input is table stakes | Opaque scores |

**What we borrow:**
- A **condition-list builder with templates** (TrendSpider-style no-code, Finviz-style simplicity).
- **Exit combinations with first-hit-wins** (TrendSpider, AmiBroker).
- **MAE/MFE analysis**, the classic tool for stop and target placement in AmiBroker/RealTest workflows.
- **Point-in-time honesty** (Portfolio123, MarketInOut, QuantConnect). We're explicit that week-1 live data falls short of it.

**Our differentiating angle (as a learning build, not a market claim):** an **exit lab that compares exits on identical entries, with IS/OOS columns and a trial counter**. Mainstream web scanners don't make this side-by-side exit comparison a first-class screen.

---

## 4. Product vision as a portfolio piece

**Two-minute pitch:**
> "I built a swing-strategy research workbench in a week with AI agents, for $0. You compose an entry rule, see today's hits in a table, then compare up to six exit strategies on the exact same entries, each against random entries run through the same exit. Stops, targets, trailing and MA exits each have a hand-computed oracle test. IS and OOS sit side by side, but only IS is highlighted, so you pick on IS. A trial counter keyed on the rule's structure warns when parameter-tweaking piles up. The public demo runs on a synthetic market with planted delistings, so tests can prove survivorship and look-ahead handling. My real research runs locally on free data, and I'm explicit that it's survivors-only, so findings are hypotheses."

### 4.1 Definition of "portfolio-ready" (release v1.0)
- [ ] The public URL loads with a **"Synthetic market: not real prices"** banner, no sign-up. A template rule → scan → exit-lab run works end to end. Cold start ≤ 10 s; warm backtest < 3 s; warm 6-config exit lab with random baseline < 10 s.
- [ ] Every MUST acceptance criterion in §6 passes in CI (badge in README).
- [ ] Oracle tests for **every MUST exit type** plus the poisoned-future test pass.
- [ ] The README has: a **GIF** of the demo flow, the demo script (§7), an architecture diagram, ADRs, an agent log, an honest tech list, "$0/month" with how, the data-licence statement, and a **"Limits of the research"** section (copied from §8.1).
- [ ] **One published research note run on the synthetic market** (in the repo, linked from the README). It follows the **research-note template (§4.3)**: IS-pick → OOS-once → single portfolio backtest, with trial count, edge vs random and caveats (including the synthetic market's planted edge). The owner keeps **live research notes private** in a gitignored local `research/` folder. Aggregate metrics from live data count as derived data and are **never published**.
- [ ] No real price data or keys in the repo; the guard passes. Tagged `v1.0`.

### 4.3 Research-note template (published synthetic note and private live notes)
1. **Hypothesis:** one sentence, e.g. "For 52-week breakouts, a 10% trailing stop beats a fixed 8% stop per bar held."
2. **Setup:** data mode and version or seed; date range; the IS/OOS split date; entry rule JSON and its structure key; the assumptions header.
3. **IS-pick:** run the exit lab and **choose the exit using IS columns only**: expectancy per bar, edge vs random, MAE/MFE guides from IS. Record why.
4. **OOS-once:** read the OOS columns for the chosen config **once** and record them. If anything is changed after looking, say so, and treat the next run as a new trial (the counter will show it).
5. **Single portfolio backtest:** run the chosen entry + exit **once** in portfolio mode (max N, equal weight). Record CAGR, max DD, exposure and # trades vs the benchmark.
6. **Trials:** the structure-key count and the session total at the time of writing.
7. **Limits:** the relevant items from §8.1. For synthetic notes, state that **the edge is planted**.
8. **Conclusion:** a hypothesis with a confidence level, plus the next step (e.g. "re-test on Massive delisted-inclusive data", "paper-trade 3 months").

### 4.2 Deliberate non-goals (week 1)
Accounts/login, server-side saved rules, alerts, watchlists, OR groups or nesting in rules, natural-language rules, intraday data, fundamentals, short selling, risk-based sizing, parameter sweeps, walk-forward, signal study, Monte Carlo, hosted real data, a demo video.

---

## 5. Scope: MUST, cut order, Stretch/Later

### 5.1 MUST (lead scope v3.3, ≈ 53 h P50 / ≈ 60 h P80)
Hours are the Architect's "v3-fit" figures (`02` §11.1), less the v3.2 deferrals, plus ~2 h of research safeguards (DA v4 A2). **The Architect owns the final estimate.** The DA notes that oracle authoring may take 6 h rather than 4, which is part of the P80.

| # | Item | Hours |
|---|---|---|
| M0 | **Foundation:** scaffold, specs, AGENTS.md, CI, Day-1 deploy (Vercel + Lambda via OIDC), data-leak guard | 7.0 |
| M1 | **Data:** synthetic market + live loader (Alpaca free since 2016, ~500 current S&P 500 + SPY, local only, survivors badge) + guard | 7.0 |
| — | **Oracle tests** (owner-written or approved, before the engine) | 4.0 |
| M2 | **Rule engine:** indicators, rule model → one Polars expression (scan and backtest share it), validity/rising edge, validator, 2 templates, `POST /scan` | 6.5 |
| M4 | **Backtest + pluggable exits:** portfolio-lite engine, 6 exit types (% targets only), MAE/MFE per trade, metrics, IS/OOS, benchmark, poisoned-future test | 5.0 |
| M5 | **Exit lab (trade mode):** entries computed once (cooldown, last-bar rule), per-trade loop over each trade's own bars, `horizon_bars`, endpoint + payload check on Day 4 | 2.0 |
| M6+ | **Research safeguards:** random-entry baseline + "edge vs random"; structure-keyed + session trial counter; expectancy per bar, distinct entry weeks, % by horizon; IS-only guides and highlight | 2.0 |
| M3/M6 UI | Shell + banners, **rule builder** UI, **results table**, exit editor, strategy panel (comparison with IS/OOS, equity curve, trade list with MAE/MFE), **trial counter** | 13.0 |
| M7 | **Ship:** engine review, README + ADRs + agent log + GIF + synthetic research note, tag | 3.5 |
| | Buffer | 3.0 |
| | **Total** | **≈ 53 (P50); ≈ 60 (P80)** |

**Deferred to Stretch (v3.2):** candle chart with hit markers (scan results are a table; the backtest keeps its equity curve), MAE/MFE scatter (MAE/MFE stay as columns), Sentry, **exit-lab portfolio mode** (the single-config backtest stays portfolio-based), **R-based targets** (% targets stay).

### 5.2 Cut order if behind (canonical; cut from the top)
1. **Close-below-MA exit.**
2. **ATR stop.** Keep % stop, % target, trailing stop and time stop.
3. **Trial counter.** Replace it with a static "beware of overfitting" warning.
4. **Live loader.** Moves to Day 8; the public build doesn't need it.

**Never cut:** the rule builder; the backtest; the exit lab (trade mode) with IS/OOS; the oracle and poisoned-future tests; the CI deploy; the README.

### 5.3 Dropped, Stretch and Later
**Stretch (priority order):**
1. **Candle chart with hit markers** (click a result row)
2. **MAE/MFE scatter** (baseline IS trades, percentile guide lines)
3. **Wikipedia "Date added" filter** (live mode, local only): a current S&P 500 member is tradeable only after it joined the index. Removes most of the index-selection look-ahead for current members.
4. **Exit-lab portfolio mode** (CAGR/max DD per config, "% entries shared with baseline")
5. **Signal study:** forward 1/5/10/20-day returns vs base rate
6. **R-based targets** (requires a stop in the config)
7. **Sentry**
8. **Parameter sweep** (one parameter, small grid, IS/OOS heatmap)
9. **Walk-forward** (anchored, 3–5 folds)
10. **Massive free 2-year delisted-inclusive data** + daily archiving
11. **Terraform** for the Lambda resources
12. **OR groups** in the builder

| Dropped since v2.1 | Later |
|---|---|
| RS results column (RS stays as an indicator); ↑/↓ flip-through; trade drill-down | Paper-trading forward test log; server-saved rules (Neon free) |
| Playwright smoke test; demo video (now a GIF) | Risk-based sizing, short side; Monte Carlo, regime breakdown |
| Separate preset screen; presets 3–4 (extra **templates** if time allows) | Fundamentals/earnings (SEC EDGAR), sectors (SIC); nesting in the builder |

---

## 6. MUST feature specs with acceptance criteria

> These map to the Architect's specs: **data (D), rule builder (R), scan (S), backtest and exits (B), exit lab (X), UI and honesty (U)**. IDs were renumbered for v3; v2.1 IDs are retired.

### 6.1 Data (M1)

**Synthetic market (public):**
- 500 invented tickers × 5 years of business days, from a fixed seed.
- Regimes (bull/bear/chop) plus sectors and noise.
- A small, documented momentum term.
- **~5% planted delistings** (bankruptcy decay or acquisition jump) and ~5% mid-sample listings.
- **Adjusted prices only.**
- A `DEMO-INDEX` benchmark.
- Parquet baked into the image. Tickers never match real symbols.

**Live mode (local only):**
- `make load-live` fetches Alpaca free daily bars (`feed=sip`, `adjustment=all`) **from 2016-01-04 to the latest close** for ~500 current S&P 500 names plus **SPY** (the benchmark), into the same schema.
- `DATA_MODE=live` refuses non-localhost hosts.
- `data/` is gitignored.
- The UI shows **"Real data: survivors only, current S&P 500 members. Results are biased upward; treat them as hypotheses."**

| ID | Given / When / Then |
|---|---|
| D-1 | **Given** seed 42, **when** the generator runs twice, **then** the outputs are equal frame-for-frame. |
| D-2 | **Given** generated data, **when** validated, **then** every bar has `low ≤ min(open, close)`, `high ≥ max(open, close)`, `volume > 0`, and no ticker has bars after its `delisted_on`. |
| D-3 | **Given** the generator output, **then** at least one bear segment and ≥ 20 delisted tickers exist. |
| D-4 | **Given** `make load-live` with valid keys, **when** it completes, **then** each loaded ticker's first bar is on or after 2016-01-04 (or its listing date), SPY is present, and the load summary reports ticker count and missing symbols. |
| D-5 | **Given** `DATA_MODE=live` on a non-localhost host, **when** the API starts, **then** it exits with a clear error. |
| D-6 | **Given** a commit containing `*.parquet`/`*.csv` under `data/` or an API-key pattern, **when** pre-commit or CI runs, **then** it fails. |

### 6.2 Rule builder (M2)

**Rule** = a flat **AND-list** of **1–8 conditions**, as JSON. One object drives the scan, the backtest and the exit lab. **The JSON shape and indicator names follow `02` §5.2** (Pydantic is the source of truth; TS types are generated from it).

```json
{
  "name": "52w breakout on volume",
  "conditions": [
    {"left": {"kind": "ind", "name": "close"}, "op": ">", "right": {"kind": "ind", "name": "highest", "params": {"n": 252}, "offset": 1}},
    {"left": {"kind": "ind", "name": "volume"}, "op": ">", "right": {"kind": "ind", "name": "avg_volume", "params": {"n": 50}, "mult": 1.5}},
    {"left": {"kind": "ind", "name": "close"}, "op": ">", "right": {"kind": "num", "value": 5}}
  ]
}
```

- **Operand:** `{"kind": "num", "value": x}` or `{"kind": "ind", "name": …, "params": {…}, "offset": 0–20 bars back (default 0), "mult": 0.1–10 (default 1)}`.
- **Operators:** `>`, `<`, `>=`, `<=`, `crosses_above`, `crosses_below`. `A crosses_above B` at t means `A[t] > B[t]` and `A[t−1] ≤ B[t−1]`.
- **Indicator registry (`02` §5.2):**
  - price fields: `open`, `high`, `low`, `close`, `volume`;
  - `sma(n)`, `ema(n)` (n 2–252), `rsi(n)`, `atr(n)` (n 2–50, Wilder);
  - `highest(n)`, `lowest(n)` (N-day high/low; use `offset: 1` for the prior N days), `avg_volume(n)` (n 2–252);
  - `ret(n)` (N-day % return, n 1–252);
  - `rs(n)`: cross-sectional percentile 0–99 of `ret(n)` among tickers alive on t (n 21–252, default 126).
- **No hidden filters.** There is no implicit `min_price`. Templates include a **visible** `close > 5` condition the user can edit or delete.
- **Validity and warm-up:** each condition is **valid** at t only when all its inputs have enough history (including `offset` and the t−1 value for crosses). The rule is valid at t when all conditions are valid. An invalid rule is never a hit.
- **Templates (MUST):**
  - **52-week-high breakout on volume** (above): `close > highest(252)[1]`, `volume > 1.5 × avg_volume(50)`, `close > 5`.
  - **Pullback to rising 21 EMA:** `ema(21) > ema(21)[5]`, `close > sma(50)`, `low <= 1.01 × ema(21)`, `close > ema(21)`, `close > 5`.
  - RSI(2) and the trend template are optional extra templates (Stretch).
- **Structure key** (for the trial counter, §6.6): the rule with numbers stripped, i.e. indicator names, operators and condition count. `close > highest(252)[1]` and `close > highest(100)[1]` share a key.
- **Persistence:** the rule lives in the **URL** (compact encoded JSON) and in a "copy/paste JSON" panel. No server storage.

| ID | Given / When / Then |
|---|---|
| R-1 | **Given** a valid rule JSON, **when** it is parsed and serialised again, **then** the result is identical (round-trip), and the URL-encoded form reproduces the same rule after reload. |
| R-2 | **Given** the two templates, **when** evaluated on the synthetic data, **then** their hits on every date equal a hand-written reference implementation of the same logic (golden test). |
| R-3 | **Given** a fixture where A goes 9 → 11 vs B = 10, **when** `A crosses_above B` is evaluated, **then** it is true only on the bar where A first exceeds B, and false on later bars where A stays above. |
| R-4 | **Given** `highest(n=5, offset=1)`, **when** evaluated at t, **then** it equals the max high of bars t−5…t−1 (today excluded). |
| R-5 | **Given** a ticker with 30 bars of history and the condition `close > sma(50)`, **when** evaluated, **then** the rule is **invalid** (not a hit) on all 30 bars. |
| R-6 | **Given** an invalid rule (unknown indicator, `n` out of range, `offset` > 20, **9 conditions**, or an empty list), **when** submitted, **then** the API returns 422 with a JSON path to the bad field and the allowed range or values. |
| R-7 | **Given** `rs(126)` on date t, **then** values lie in 0–99 and the ticker with the highest 126-day return has 99. |
| R-8 | **Given** the builder UI, **when** the user adds, edits or removes a condition and runs, **then** the request JSON matches the UI rows exactly (UI ↔ JSON parity test). |
| R-9 | **Given** two rules that differ only in numbers, **when** their structure keys are computed, **then** the keys are equal. **Given** rules that differ in an indicator, operator or condition count, **then** the keys differ. |
| R-10 | **Given** the templates, **then** each contains a visible `close > 5` condition, and **given** a rule without it, **then** no price filter is applied (no hidden `min_price`). |

### 6.3 Scan results (M3)
The scan evaluates the rule on the **last bar t**, over tickers alive on t. Columns: ticker, close, % change, volume ÷ 50-day average, the values of each rule operand, and a "new today" flag (the rule's **rising edge** at t: valid and true at t, **valid and false** at t−1; see §6.4). *(Stretch #1: clicking a row opens a candle chart with volume, 21 EMA, 50 SMA, 200 SMA and **markers where the rule was true** in the last 12 months.)*

| ID | Given / When / Then |
|---|---|
| S-1 | **Given** a rule, **when** scanning as of t, **then** exactly the alive tickers whose rule is valid and true on t are returned. |
| S-2 | **Given** a ticker delisted before t, **then** it never appears. |
| S-3 *(parity)* | **Given** any rule, **when** scanning as of D and backtesting a range containing D, **then** the scan's "new today" hits on D equal the backtest's entry signals on D, after the 10-bar cooldown and ignoring only the last-bar rule (spec 0002). |
| S-4 | **Given** a rule with ≤ 8 conditions, **when** the scan runs warm on the deployed API, **then** it responds in < 1 s for 500 tickers (synthetic). |
| S-5 *(Stretch #1)* | **Given** results, **when** the user clicks a row, **then** the chart opens with hit markers on every bar where the rule was true. |

### 6.4 Backtest and pluggable exits (M4)

**Entry (settled with the Architect; lead ruling):**
- An **entry signal** is the rule's **rising edge**: the rule is **valid and true at t**, and **valid and false at t−1**. "Not yet computable" is not "false", so there is **no edge on the first post-warm-up bar or on a listing day**.
- **No entry on a ticker's last bar** (there is no t+1 to fill on).
- **Cooldown: 10 bars per ticker.** A rising edge within 10 bars of that ticker's previous accepted signal is ignored. The cooldown counts from the *signal*, not the exit, so it is exit-independent and every config sees identical entries.
- Entry at **open(t+1) × (1 + slippage)**.
- Ranking when signals exceed free slots: `rs(126)` descending, then ticker A→Z.
- One position per ticker. **Equal weight** = equity(t close) / `max_positions` (default 10, range 1–20). Fractional shares; no leverage; cash at 0%; $0 commission; slippage 10 bps per side (0–50).

**Exit config** = 1+ exits, **combinable, first hit wins**:

| Exit | Params (default, range) | Level / trigger | Fill |
|---|---|---|---|
| `stop_pct` | p = 8% (1–30%) | `stop = entry_fill × (1 − p)` | `min(open, stop)` if `low ≤ stop` |
| `stop_atr` | k = 2 (0.5–6), n = 14 | `stop = entry_fill − k × ATR(n) at signal bar t` | as above |
| `target` | `pct` = 15% (1–100%). *(Stretch #6: `r` = 3 (0.5–10), `entry_fill + r × (entry_fill − initial_stop)`, requires a stop.)* | `entry_fill × (1 + pct)` | `max(open, target)` if `high ≥ target` |
| `trail_pct` | p = 10% (2–30%) | `trail = (highest high from the entry bar through bar b−1, or entry_fill on bar 1) × (1 − p)`; the level only rises | `min(open, trail)` if `low ≤ trail` |
| `close_below_ma` | type SMA/EMA, n = 21 (5–200) | `close(b) < MA(b)` | **open(b+1)** (decided at the close, executed next open) |
| `time` | N = 10 (1–120) | after N bars held, **entry bar = bar 1** | **close of bar N** |

**Per-bar evaluation order** (bar b of a held position; settled):
1. **Pending MA exit** from the previous close: exit at open(b).
2. **Stops** (`stop_pct`, `stop_atr`, `trail_pct`): use the **highest** active stop level. If `open ≤ level`, exit at open (gap). Else if `low ≤ level`, exit at the level.
3. **Target:** if `open ≥ target`, exit at open. Else if `high ≥ target`, exit at the target. **If the stop and the target are both touched in the same bar, the stop wins** (conservative).
4. **Time:** if b = N, exit at close(b).
5. **Delisting:** if b is the ticker's last bar, exit at close(b).
6. Evaluate the MA condition at close(b) and schedule it for b+1. **(Lead ruling: `close_below_ma` fills at the next open, not the triggering close, because that close is only known afterwards. `02` §5.3 aligns.)**

All exits pay slippage: fill × (1 − 10 bps). On the entry bar, steps 2–5 apply after the open fill (an entry-day stop-out is possible). The end of the test closes positions at the final close (`end_of_test`).

**Per-trade record:**
- ticker, entry/exit date and price, return %, bars held, `exit_reason`;
- **R multiple** (if the config has a stop: `(exit − entry) / (entry − initial_stop)`);
- **MAE %** = `min(low[entry..exit]) / entry_fill − 1`;
- **MFE %** = `max(high[entry..exit]) / entry_fill − 1`;
- MAE/MFE in R when a stop exists.

**Exit-bar rule (`02` §5.3; lead ruling):** held bars include the exit bar, but **the exit bar's extreme is capped at the exit level**. A stop exit contributes no low below the stop fill; a target exit contributes no high above the target. Exits at the open (gap or next-open MA exit) contribute only the open. Close exits (time, delisting, end of test) use the full exit bar.

**Report:**
- Assumptions header.
- Equity curve vs benchmark with the IS/OOS boundary line.
- Metrics with **IS and OOS columns** (last 30% of dates are OOS; trades assigned by entry date): CAGR, max DD, Sharpe, win rate, avg win/avg loss, **expectancy (R, or % when no stop)**, profit factor, avg bars held, # trades, exposure %. Benchmark CAGR/max DD alongside.
- Trade list (≤ 2,000 rows).

| ID | Given / When / Then |
|---|---|
| B-1 *(oracle: % stop)* | **Given** a 1-ticker fixture with a signal on day 3 and day 5's low below an 8% stop, **then** entry = open(4) × 1.001, exit = min(open(5), stop) × 0.999, and P&L matches the hand calculation to 1e-9. |
| B-2 *(oracle: gap through stop)* | **Given** day 5 opens below the stop, **then** the exit fills at open(5) × 0.999, not at the stop. |
| B-3 *(oracle: ATR stop)* | **Given** ATR(14) at the signal bar = 2.0 and k = 2, **then** stop = entry_fill − 4.0, and the exit matches the hand calculation. |
| B-4 *(oracle: % target)* | **Given** a 15% target, **then** target = entry × 1.15; when high ≥ target, exit = max(open, target) × 0.999. **And given** the same bar touches both an 8% stop and the target, **then** the exit is at the stop. |
| B-4R *(Stretch #6, oracle: R target)* | **Given** target 3R with an 8% stop, **then** target = entry × (1 + 0.24). |
| B-5 *(oracle: trailing)* | **Given** highs 10, 12, 11 after entry at 10 and p = 10%, **then** the trail levels on bars 2 and 3 are 9.0 and 10.8, and a low of 10.7 on bar 3 exits at 10.8 × 0.999. |
| B-6 *(oracle: close below MA)* | **Given** close(b) < SMA(21)(b), **then** the exit is at open(b+1) × 0.999 with `exit_reason = ma`. |
| B-7 *(oracle: time)* | **Given** N = 3 and no other exit hit, **then** the exit is at close(entry_bar + 2) × 0.999. |
| B-8 *(oracle: delisting)* | **Given** a held ticker delists, **then** the exit is at its last close × 0.999 with `exit_reason = delisted`. |
| B-9 *(oracle: MAE/MFE)* | **Given** three fixture trades (stop exit whose exit-bar low is below the stop; target exit whose exit-bar high is above the target; time exit), **then** MAE % and MFE % (and in R) equal the hand values, with the exit-bar extreme capped at the exit level for the stop and target trades. |
| B-10 *(look-ahead)* | **Given** all data after T replaced with garbage, **when** both templates are backtested to T with every exit type enabled, **then** trades and equity up to T are identical to the clean run. |
| B-11 | **Given** 15 signals and `max_positions = 10` with no open positions, **then** the top 10 by `rs(126)` are entered at equity/10 each. |
| B-12 *(Stretch #6)* | **Given** a config with `target.r` and no stop, **when** submitted, **then** 422 explains that an R target requires a stop. |
| B-13 | **Given** identical inputs, **when** run twice, **then** results are identical. A full-history synthetic run completes warm in < 3 s with a response < 6 MB. |
| B-14 *(oracle: rising-edge validity)* | **Given** `close > highest(252)[1]` and a ticker whose rule first becomes **valid** on bar 253 and is true there, **then** bar 253 is **not** an entry signal. **And given** the rule is valid and false on bar 260 and true on bar 261, **then** bar 261 is a signal. The same holds for a ticker's listing day in the synthetic data. |
| B-15 *(oracle: last bar)* | **Given** a rising edge on a ticker's last bar (delisting or end of data), **then** no entry is created. |
| B-16 *(oracle: cooldown)* | **Given** rising edges on the same ticker at bars 100, 105 and 112, **then** signals are accepted at 100 and 112 only, in every exit config. |

> **Process requirement:** the owner writes or approves B-1 to B-10 and B-14 to B-16 **before** an agent implements the simulator. `tests/oracle/` is protected in AGENTS.md.

### 6.5 Exit lab (M5, trade mode)
**Inputs:** an entry rule (from the builder), date range, slippage, and **2–6 exit configs**. A single config runs the portfolio-based backtest (§6.4) instead.

Default suggestion set when opened:
1. **Baseline: `time` 10 only.** No stop or target, so MAE/MFE are not truncated.
2. `stop_pct` 8% + `time` 10.
3. `stop_atr` 2× + `target` 15% + `time` 20.
4. `trail_pct` 10% + `time` 30.
5. `close_below_ma` EMA 21 + `stop_pct` 8%.

**Trade mode (week 1): identical entries.**
- Every accepted entry signal (rising edge, cooldown 10, not on a last bar; §6.4) becomes one fixed-notional trade, with no capacity limit. Entries are computed once and shared by every config.
- The cooldown counts from the signal, so it is exit-independent. Trades held longer than 10 bars can still overlap a later trade on the same ticker; the footnote discloses this.
- **`horizon_bars` = 60** (disclosed in the assumptions header): a trade still open after 60 bars exits at the close of bar 60 with `exit_reason = horizon`. This is a hidden time exit for long-hold configs, so the table shows **"% exited by horizon"** per config and **warns above 10%**.

**What trade mode is for (and not for):** it isolates **the effect of the exit on these entries**. It ignores capital and slot competition, and correlated drawdowns. **It shows per-trade metrics only: no CAGR, max DD or Sharpe** (an unconstrained curve is not tradeable). Strategy-level numbers come from the single portfolio backtest in the research procedure (§4.3).

**Comparison table:** one row per config, each metric with **IS and OOS columns**.

| Metric | Notes |
|---|---|
| # trades | |
| **Distinct entry weeks** | Number of distinct ISO weeks containing entries. Entries cluster in rallies, so this is the honest sample size. |
| Win rate; avg win / avg loss | |
| **Expectancy** | R when the config has a stop, else % per trade |
| **Expectancy per bar held** | % return per trade ÷ avg bars held. Corrects the bias towards long-hold exits. |
| Profit factor; avg bars held | |
| Avg MAE / avg MFE | %, and R when a stop exists |
| **% exited by horizon** | Warning badge above 10% |
| **Edge vs random** | Strategy expectancy (%) − random-entry expectancy (%) under **the same config**; also shown per bar held |

**Random-entry baseline:**
- Sample the **same number of entries** as the strategy, **separately in IS and OOS**.
- Sample uniformly from eligible (ticker, date) pairs: ticker alive, not its last bar, inside the segment.
- Use a **fixed seed** (shown in the assumptions header).
- Run them through **every config** with the same exits, horizon and slippage.

The table shows a **"Random entries" row** (baseline config) plus the per-config "edge vs random" column. Random entries share the survivor universe and the bull regime, so the **difference** largely cancels those biases. It is the main defence against biased free data.

**Highlighting:** the **best IS value per metric is highlighted**. **OOS values are shown beside it and are never highlighted**, because highlighting the best OOS invites picking on OOS.

**MAE/MFE guide row** (under the table), computed from **the baseline config's IS trades only**: the 75th/90th percentile MAE of winners (stop guide) and the median MFE (target guide).

*Stretch #2, MAE/MFE scatter:* MAE % vs final return % and MFE % vs final return % for baseline IS trades, with the guide lines drawn.

*Stretch #4, portfolio mode:* each config also runs through the portfolio-lite simulator (CAGR, max DD, exposure, "% of entries shared with baseline").

| ID | Given / When / Then |
|---|---|
| X-1 | **Given** an entry rule and any 2–6 configs, **when** run, **then** the entry list (ticker, entry date, entry price) is identical across configs, and honours the rising-edge, cooldown and last-bar rules (B-14 to B-16). |
| X-2 | **Given** 1 or 7 configs, **when** submitted, **then** 1 runs as a plain portfolio backtest and 7 returns 422. |
| X-3 | **Given** a completed run, **then** every metric shows IS and OOS columns. The best **IS** value per metric is highlighted, and **no OOS cell is ever highlighted**. |
| X-4 | **Given** a config without a stop, **then** its expectancy shows in %, R columns show "n/a", and a footnote explains why. |
| X-5 | **Given** a fixture where adding the OOS trades would change the guides, **then** the MAE/MFE guide row (75th/90th percentile winner MAE, median MFE) equals the values from **baseline IS trades only**. |
| X-5S *(Stretch #2)* | **Given** a completed run, **then** the scatter plots baseline IS trades with the percentile guide lines. |
| X-6 *(Stretch #4)* | **Given** portfolio mode, **then** each config shows CAGR, max DD and its "% of entries shared with baseline". |
| X-7 | **Given** 6 configs plus the random baseline on full-history synthetic data, **when** run warm on the deployed API, **then** it completes in < 10 s with a response < 6 MB (aggregates per config; one trade list for the baseline only). *Checked on Day 4, right after the simulator (DA A1).* |
| X-8 | **Given** a trade-mode response, **then** it contains **no CAGR, max DD or Sharpe**, and contains expectancy per bar held, distinct entry weeks and % exited by horizon for every config, matching a hand-checked fixture. |
| X-9 *(oracle: horizon)* | **Given** a `trail_pct` config whose trade is still open after 60 bars, **then** it exits at close(bar 60) × 0.999 with `exit_reason = horizon`. **Given** a config with > 10% of trades exited by horizon, **then** its row shows the warning badge. |
| X-10 *(random baseline)* | **Given** a strategy with 120 IS and 40 OOS entries, **when** run, **then** the random baseline has exactly 120 IS and 40 OOS entries, all on alive tickers and none on a last bar. A re-run with the same seed gives identical random entries. "Edge vs random" equals strategy expectancy − random expectancy under the same config. |

### 6.6 UI and honesty (M6 + UI)

| ID | Given / When / Then |
|---|---|
| U-1 | **Given** a first visit to the public URL, **then** the builder opens with the Breakout template loaded and its scan results shown, under a visible **"Synthetic market: not real prices"** banner. No sign-up. |
| U-2 | **Given** live mode on localhost, **then** every page shows the survivors-only / current-S&P warning badge. |
| U-3 | **Given** any backtest or exit-lab report, **then** an assumptions header lists: fill model, slippage, sizing, max positions, entry rule (rising edge, cooldown 10, no last-bar entry), exit rules per config, `horizon_bars` (trade mode), random seed, delisting rule, OOS split date, data mode and data version or seed. |
| U-4 *(trial counter)* | **Given** a run completes, **then** each **distinct (exact rule + exit config) pair** not seen before is added to the count for the rule's **structure key** (§6.2), stored in localStorage. Re-running an identical pair doesn't add. A **global session total** across all rules is kept in sessionStorage. The report shows "Trial #N for this rule structure · M this session". At **N ≥ 10** it shows: *"You've tested many variants of this rule structure; the best IS result is likely overfit. Read OOS once and treat the result as a hypothesis."* With storage unavailable, the counter is hidden and the static warning is shown. |
| U-5 | **Given** the API is cold, **when** a request is pending > 1.5 s, **then** a "warming up the engine…" state shows. |
| U-6 | **Given** a 375 px viewport, **then** builder rows stack, tables scroll inside their containers, and the page has no horizontal scroll. |
| U-7 | **Given** a 422 from the API, **then** the offending builder row or exit field shows the inline error. |
| U-8 | **Given** an exit-lab report, **then** a note under the table reads: *"Trade mode isolates the exit effect: every config trades identical entries, so the exit is the only difference. Pick the exit on in sample (IS), read out of sample (OOS) once, then confirm with a single portfolio backtest."* |

### 6.7 Settled defaults (single source of truth; lead rulings, `02` aligned)
| Setting | Value |
|---|---|
| Entry signal | Rising edge: rule **valid and true** at t, **valid and false** at t−1. No edge on the first post-warm-up bar or a listing day. No entry on a ticker's last bar. **Cooldown 10 bars** per ticker, from the previous accepted signal. |
| Rule limits | 1–8 conditions (AND only), `offset` 0–20, `mult` 0.1–10, indicator names per `02` §5.2, no hidden `min_price` |
| Fill model | Signal at close(t), entry at open(t+1) |
| Slippage / commission | 10 bps per side / $0 |
| Sizing (portfolio mode) | Equal weight, equity / `max_positions` (10) |
| Ranking (portfolio mode) | `rs(126)` desc, then ticker A→Z |
| Exit precedence | Pending MA exit at **open** → stops (highest level; gap fills at open) → % target → time (close of bar N, entry = bar 1) → delisting (last close). Stop beats target on the same bar. |
| MAE/MFE | Over held bars incl. the exit bar; exit-bar extreme capped at the exit level |
| Trade-mode horizon | `horizon_bars` = 60, disclosed; warn when > 10% of trades exit by horizon |
| Trade-mode metrics | Per-trade only (no CAGR/max DD/Sharpe); plus expectancy per bar, distinct entry weeks, % by horizon, edge vs random |
| Random baseline | Same entry count per segment, uniform over alive (ticker, date), fixed seed, same configs |
| Highlighting | Best IS only; OOS beside it, never highlighted |
| MAE/MFE guides | Baseline config, **IS trades only** |
| OOS | Last 30% of dates, trades by entry date |
| Trial counter | Keyed on rule **structure** (numbers stripped) + global session total; warn at **≥ 10** |
| Prices | Adjusted only |
| Benchmark | `DEMO-INDEX` (synthetic) / SPY (live) |

### 6.8 Terms on screen: keep the word, explain it

The reader is a curious beginner, not a programmer or a professional trader (§2), but the terms are
the data. Renaming `Sharpe` or `MAE` to something friendlier would leave a reader who knows the
field unable to tell what a column holds, and a reader who does not still unable to look it up. So
**the label keeps the real term, and the UI explains it in one plain line next to it.**

Three rules for every builder:

1. **Never substitute a term that names a real quantity.** Expectancy, R, MAE, MFE, profit factor,
   CAGR, max drawdown, Sharpe, exposure, win rate, slippage, horizon, bars, IS, OOS: all keep their
   names.
2. **Explain it once, where it appears.** A form field uses its existing description slot; a table
   header carries a short `title` on an `abbr` (plus a readable tooltip) and the group header spells
   an abbreviation out in full the first time, "In sample (IS)". No new machinery, no glossary page
   the reader has to go and find.
3. **Rename only a label that names nothing.** "Bars ago", "Window (n)" and "Multiplier (×)"
   describe form inputs, not quantities, and a beginner cannot guess them. They keep their wording
   and gain an explanation; the gap they leave behind when hidden is removed.

The explanations, as the UI should word them:

| Term (keeps its label) | The one line beside it |
|---|---|
| Expectancy (%) | What one average trade made or lost, in percent. |
| Expectancy (R) | The same, counted in multiples of the risk you took (R = the distance to your stop). |
| Expectancy per bar | Expectancy divided by how long the trade was held, so quick trades and slow ones compare. |
| Profit factor | Everything the winners made divided by everything the losers lost. Above 1 is a profit. |
| Win rate | The share of trades that ended in profit. |
| MAE (worst adverse move) | The deepest a trade went against you before it closed. |
| MFE (best favourable move) | The furthest a trade went in your favour before it closed. |
| Distinct entry weeks | How many separate weeks the trades started in. A high count means the result is not one lucky week. |
| Exited by horizon | The share of trades still open at the horizon, which were closed at that bar's close rather than by a real exit. |
| Horizon (bars) | A trade still open after this many bars is closed at that bar's close. |
| Bars ago | 0 is today's bar, 1 is the bar before it. |
| Window (n) | How many bars the indicator averages or looks back over. |
| Multiplier (×) | Scales the value. 1 leaves it unchanged. |
| Slippage (bps) | Assumed trading cost per side. 10 bps is 0.1%. |
| CAGR | The yearly growth rate the equity curve works out to. |
| Max drawdown | The worst fall from a previous peak in equity. |
| Sharpe | Return divided by how much it bounced around; higher is steadier. |
| Exposure | The share of the test period with money in the market. |
| IS / OOS | In sample, the stretch you choose on, and out of sample, the later stretch you read once. |
| Edge vs random | This config's value minus the same config run on random entries. |
| Best IS | The best in sample value of that metric across the configs. Out of sample is never marked. |

Changed wording, the short list. Everything else on screen keeps the words it has:

- `/backtest` is called **Testing** in the navigation, because the page runs the backtest and the
  exit lab, and "Backtest" named only half of it.
- The "Compare with" select disappears; picking a plain number becomes an option in the right side
  dropdown (§6.2, builder usability).
- Form hints become full sentences, and the engine's warning messages become full sentences that
  say the consequence. Terms and numbers inside them do not change.

Unchanged, deliberately: every number format, every honesty statement, and the footer "Portfolio
project. Not investment advice."

---

## 7. Demo script (2–3 min; recorded as a GIF on the synthetic market, and used live in interviews)
1. **0:00–0:15.** Public URL. Synthetic banner: "free vendor data can't be shown publicly, so this is a generated market with planted delistings."
2. **0:15–0:45.** The builder opens on the **Breakout** template. Change volume `mult` 1.5 → 2.0, add `rsi(14) < 75`, and show the URL updating and the JSON panel.
3. **0:45–1:00.** Scan results table: "new today" flags and operand values per ticker.
4. **1:00–1:20.** Single-config backtest: assumptions header, equity curve vs `DEMO-INDEX` with the IS/OOS line, the trade list filtered to `exit_reason = delisted`.
5. **1:20–2:10.** **Exit lab** with the 5 default configs. Then:
   - "Same entries; only the exit changes."
   - Point to the **"edge vs random"** column and the "Random entries" row: "random entries in the same market go through the same exits; this difference is the part that isn't just market drift."
   - Read **expectancy per bar** next to plain expectancy: the trailing stop looks best per trade but not per bar held.
   - Only IS is highlighted. Glance at the OOS beside it, once.
   - Read the MAE/MFE guide row (IS trades only): "90% of winning trades never went below −6%, so an 8% stop is loose."
   - Tweak the breakout `n` 252 → 100 and re-run: the trial counter moves to **"Trial #10 for this rule structure"** and the overfitting warning appears.
6. **2:10–2:35.** Repo: the oracle tests for each exit type, the poisoned-future test, CI → Lambda via OIDC.
7. **2:35–3:00.** README:
   - "Limits of the research" (§8.1);
   - the research procedure: IS-pick → OOS-once → single portfolio backtest;
   - the published synthetic research note (live notes stay private);
   - the agent log;
   - $0.

---

## 8. Data (free-source angle)
Details are in `01a-free-data-sources.md`.
- **Public demo, GIF, CI and fixtures:** synthetic only.
- **Live research (local):** Alpaca free plan, daily SIP bars since 2016-01-04, `adjustment=all`, 200 calls/min. ~500 names × ~2,700 bars ≈ 1.35M bars, a few minutes to fetch. **Personal, non-commercial use only.** Never committed, never hosted, never shown in the GIF.
- **Known biases:** see §8.1 (shown in the UI badge and copied to the README).
- **Path to stronger evidence (Later):**
  - **Massive free, 2-year Grouped Daily** (delisted-inclusive), plus nightly archiving to grow it;
  - walk-forward;
  - a paper-trading forward log.
- Public data usable later: SEC EDGAR (fundamentals, earnings dates, SIC), FRED (risk-free rate), the Nasdaq Trader symbol list. Wikipedia's S&P 500 "Date added" column (CC BY-SA) is Stretch #3, local only.

### 8.1 Limits of the research (copied to the README)
All of these point the same way: **results look better than reality**.
1. **Survivorship (live):** Alpaca free returns no bars for delisted names. Companies that died since 2016 are missing.
2. **Index-selection look-ahead (live):** the universe is *today's* S&P 500. Many names were added *because they rose*. A 2017 breakout in a company that joined the index in 2023 is a trade nobody could have screened for in 2017. This bias hits momentum and breakout rules, i.e. the templates, hardest, and is probably larger than plain survivorship. *Mitigation: random-entry baseline (cancels much of it); Stretch #3 "Date added" filter.*
3. **One regime in OOS (live):** OOS is the last 30% of 2016+ data, roughly **2023-07 → 2026-10**, mostly a bull market for US equities. A long-only momentum rule can "pass" OOS without being robust.
4. **Short history:** 2016+ contains only a few sharp drawdowns (2018 Q4, 2020, 2022).
5. **Multiple testing:** many entry tweaks × up to 6 exits. Every look at OOS makes it less out-of-sample. *Mitigation: IS-only highlight, OOS-once procedure, structure-keyed trial counter.*
6. **Trade mode ignores capital:** no slot competition, no correlated drawdowns; distinct entry weeks are the honest sample size. *Mitigation: the single portfolio backtest in the research procedure.*
7. **Synthetic market (public demo):** **the edge is planted** (a documented momentum term). Templates will look good there by construction. Synthetic results demonstrate the method and the engine's correctness, never a strategy.
8. **Costs are simple:** 10 bps slippage, no commission, no borrow, no taxes; fills at the open or at stop/target levels.

**Therefore:** every finding is a **hypothesis**. Confidence requires delisted-inclusive data (Stretch #10), walk-forward (Stretch #9) and a paper-trading forward test (Later).

---

## 9. Why there is no monetisation
A $0 learning and portfolio project with one real user (the owner). Billing, accounts and data licensing would teach little about the core skills.

*If it were commercial:* display/redistribution data licences (~$500–2,000/month) would dominate costs. Pricing would sit against Finviz Elite (~$25–40) and TrendSpider (~$54+). Marketing hypothetical results would need legal review. See v1 in git history.

---

## 10. Success metrics (learning, research and portfolio)

| Outcome | Measure | Target |
|---|---|---|
| Shipped | `v1.0` tag with all §4.1 checks ticked | ≤ 7 calendar days |
| Effort | Hours logged vs the Architect's estimate | Within +10% |
| Correctness | MUST acceptance criteria passing in CI; an oracle test per MUST exit type | 100%; engine line coverage ≥ 90% |
| Research | Published synthetic research note demonstrating the method; private live notes in local `research/`, each written as a hypothesis with IS/OOS, trial count and caveats | 1 published by v1.0; ≥ 3 private live notes within a month |
| Research discipline | Share of notes following the §4.3 procedure (IS-pick → OOS-once → single portfolio backtest), reporting edge vs random and trial count | 100% |
| Agentic-coding learning | Agent log: tasks delegated, mistakes caught by tests or review | ≥ 15 tasks; ≥ 3 caught mistakes documented |
| Understanding | Owner can explain the exit-precedence rules and every oracle case without notes | Self-check plus one peer walkthrough |
| Cost | AWS + Vercel bill | $0; the $1 budget alarm never fires |
| Portfolio signal | Feedback from 2–3 engineers or recruiters on README + GIF | "Would discuss in an interview" from ≥ 2 |

---

## 11. Risks and open questions

| Risk | Mitigation |
|---|---|
| **Scope v3.3 is ≈ 53 h P50 / ≈ 60 h P80 vs a ~48 h week** | Cut order §5.2; the Day-4 performance checkpoint (X-7) right after the simulator; per-trade loop in trade mode. |
| Exit precedence bugs (the most error-prone code) | Settled order (§6.4), an oracle per exit type, owner reads every engine diff |
| An agent writes wrong code *and* matching wrong tests | Owner-approved oracles in protected `tests/oracle/` |
| Overfitting through the exit lab (6 configs × many entry tweaks) | IS-only highlight, OOS-once procedure (§4.3), structure-keyed trial counter (warn ≥ 10), random-entry baseline, "hypothesis" framing |
| Live findings mistaken for proof | Survivors/current-S&P badge, §8.1 "Limits of the research" in the README, edge vs random, Later data path |
| Rule builder grows (OR, nesting, more indicators) | Flat AND-list and 12 indicators fixed for week 1; OR groups are Stretch #12 |
| Exit-lab payload or time exceeds Lambda limits | Aggregates per config; one trade list for the baseline; X-7 budget |
| Accidental real-data leak | `data/` and `research/` gitignored, guard (D-6), localhost-only live mode, GIF and published note made on synthetic data |

**Open questions:**
1. ~~Publishing aggregate metrics from live data~~. Resolved (lead): treated as derived data, never published. The published note uses the synthetic market; live notes stay in gitignored `research/`.
2. ~~Trial-warning threshold~~. Resolved (lead): ≥ 10 on the structure key, plus a global session total.
3. Fractional shares in the portfolio backtest: acceptable? (Recommended: yes, documented.)

**Day 1: verify:**
4. Alpaca market-data terms.
5. GitHub's 60-day scheduled-workflow rule (only if a cron is added).
6. Lambda's 6 MB response limit (drives X-7 and B-13).

---

## 12. Sources
- Competitor research (v1 sources, in git history), key items: TradingView https://cn.tradingview.com/support/solutions/43000742437 ; Finviz Elite https://www.liberatedstocktrader.com/finviz-review/ ; Trade Ideas https://www.stockbrokers.com/review/tools/trade-ideas ; TrendSpider https://daytradingtoolkit.com/reviews/trendspider-review ; MarketSurge/alternatives https://chartinglens.com/blog/best-marketsurge-alternatives ; Deepvue https://beginnersinai.org/deepvue-ai-terminal-review/ ; Norgate https://nexusfi.com/d/data-providers/norgate-data/ ; AI entrants https://walnutinvest.com/resources/best-ai-stock-screeners
- DA corrections: Portfolio123 https://daytradingz.com/portfolio123-review/ ; MarketInOut https://marketinout.com/home/faq.php ; QuantConnect https://www.quantconnect.com/
- Survivorship bias: https://www.luxalgo.com/blog/survivorship-bias-in-backtesting-explained
- Data: Alpaca https://docs.alpaca.markets/docs/about-market-data-api ; https://docs.alpaca.markets/us/docs/market-data-faq ; Massive licensing https://massive.com/knowledge-base/article/which-plan-do-i-need-to-show-massive-data-in-my-app
- Review: `docs/03-devils-advocate-review.md`

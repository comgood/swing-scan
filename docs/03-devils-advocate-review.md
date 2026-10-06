# 03: Devil's Advocate Review

| | |
|---|---|
| **Author** | CEO / Devil's Advocate (design team: PM, Senior Architect, Devil's Advocate) |
| **Date** | 2026-10-06 |
| **Reviews** | `01-market-research-and-product-spec.md`, `01a-free-data-sources.md`, the PM's 1-week MUST list, `02-technical-design-and-roadmap.md`, and the Architect's planned $0 stack |
| **Status** | **Review v3 + v4 addendum** (top section, covering Research mode at ≈ 51 h). Supersedes v1 (commercial frame) and v2 (multi-month portfolio frame). |
| **Scope** | Design only. No code. The drafts were not edited. |

---

## v4 addendum: Research mode (rule builder + exit lab), lead decision ≈ 51 h

*Reviewed: 01 v3.1 and 02 v2.0, against the lead's ≈ 51 h decision.*
- **Deferred:** candle chart, MAE/MFE scatter, Sentry, exit-lab portfolio mode, R-based targets.
- **Kept:** flat-AND rule builder with 12 indicators, 6 exit types, MAE/MFE columns, the trade-level exit lab (2–6 configs, IS/OOS), the trial counter, and the local Alpaca 2016+ loader.
- **Owner's aim:** find profitable swing strategies and sensible exits.
- Sections 1–7 below (v3) still apply, except where this addendum overrides them.

### A1. Is ≈ 51 h realistic? **Optimistic, but a reasonable median.** Plan for a P80 of about 60 h.
- **Evidence:** 02 §11.1 builds up to 53 h. The lead's deferrals take off about 2 h, giving ≈ 51 h. Three items look tight:
  1. **The owner writes 20 oracle tests with hand-computed CSV fixtures in 4 h** (12 min each, T1/T2). Working out gap fills, the trailing stop and MAE by hand, and debugging the fixtures, realistically takes **6–8 h**.
  2. **B1, the simulator with 6 exits, the precedence rules and MAE/MFE, in 3 h.** Agents will write it quickly. Getting all 20 oracle tests green is the slow part.
  3. **F4 Lambda packaging, 2.5 h.** There's already a 3 h timebox with a Cloud Run fallback, which is fine.
- **Riskiest task: the exit engine (B1 + O9–O16).** It's the most correctness-sensitive code, and the agent writes it against tests the owner is writing on the same day. Two problems stack up here:
  - **Precedence:** 01 and 02 disagree on the MA exit fill (A4 #1), so oracle B-6/O13 can't pass for both specs.
  - **Performance:** in trades mode, a Python day loop with 6 configs is about 1–2M position-steps per config set. At realistic per-step overhead (several µs per protocol call), that's **5–20 s, against the 10 s target**.
- **Recommendation:**
  - Treat 51 h as **P50** and publish **P80 ≈ 60 h**, keeping the existing cut order.
  - Move the X-6 performance check from Day 5 to **Day 4, immediately after B1**.
  - In trades mode, **loop per trade over that trade's own bars** (trades are independent), not over every session. That's simpler and much faster, and it shares the same `Exit` classes.

### A2. Research validity: how likely is the owner to fool themselves? **Very likely, without two cheap additions.**
- **Bias stack in live mode** (all point the same way, upward):
  1. **Survivorship.**
  2. **Index-selection look-ahead.** Today's S&P 500 includes names that were *added because they rose*. A 2017 breakout on a company that joined the index in 2023 is a trade you couldn't have screened for in 2017. This bias hits **exactly the momentum and breakout rules** the templates use. It's probably larger than plain survivorship.
  3. **One regime.** OOS is the last 30% of 2016+ data, roughly **2023-07 → 2026-10**, mostly a long-equity bull market. A long-only momentum rule can "pass" OOS without being robust.
  4. **Multiple testing.** 6 exit configs × many entry tweaks, with the OOS columns always visible. Every look at OOS turns it into in-sample, and holdout contamination is cut.
  5. **The trial counter is keyed on the exact rule hash.** **Changing any number in the entry rule (the main way people overfit) resets the count to 1.** As written, the safeguard doesn't catch the most common case.
  6. **MAE/MFE guides from all trades.** The guide lines use IS and OOS trades together, and stop and target placement is then judged on those same trades.
  7. **Synthetic market:** it has a planted momentum term (02 §3.2), so templates *will* look good there. The published research note must say that the edge is planted.
- **Cheapest safeguards (≈ 1.5–2 h total; fund them from buffer):**
  - **(a) Random-entry baseline row in the exit lab (≈ 1–1.5 h). Highest value.** Sample the same number of entries uniformly from alive (ticker, date) pairs with a fixed seed. Run them through **the same exit configs**, and show "edge = strategy − random" per metric. Random entries on the same survivor universe pick up the same survivorship, index-selection and bull-regime uplift, so the *difference* largely cancels those biases. It's the single best defence against biased free data, and it's an excellent interview talking point.
  - **(b) Fix the trial counter key (≈ 15 min).** Key it on the rule's *structure* (indicator names, operators and condition count, with numeric params stripped), and also show a **global session total**. Then parameter tweaks accumulate on the same counter.
  - **(c) Expectancy per bar held, plus MAE/MFE guides from IS trades only (≈ 15–30 min).** See A3.
  - **Optional swap-in (≈ 1 h, live mode only, local):** use Wikipedia's **"Date added"** column for current S&P 500 members (CC BY-SA, used locally only) so a ticker is only tradeable after it joined the index. That removes most of bias 2 for current members. It's lower priority than (a), which covers most of the same ground.
- **Is "first day the rule becomes true" entry sound?** Yes. Rising-edge entry keeps the scan's "new today" and the backtest in parity, and it stops a persistently true rule from re-entering every day. **But there's a bug in the spec as written:** 01 R-5 makes a condition *false* during warm-up. So the **first valid bar after warm-up** (about 252 bars into the data for `highest(252)`, i.e. early 2017 in live mode, and similarly at every mid-sample listing in synthetic data) **becomes a rising edge for every ticker where the rule holds**. That gives a burst of spurious entries. **Fix:** a rising edge requires the rule to be *validly evaluated and false* at t−1, so "not yet computable" doesn't count as false. Also: a signal on a ticker's **last bar** (no t+1) gives no entry. Write both as acceptance criteria.
- **Is the exit precedence sound?** Mostly yes, and conservative where it should be:
  - The tightest stop wins.
  - A gap through the stop fills at the open.
  - The stop beats the target in the same bar.
  - The trailing level uses highs through t−1.
  - ATR is taken from the signal bar.
  - The time exit is at the close of bar N.

  **One real problem: `close_below_ma`.** 01 fills at the **next open** (decided at the close, executed at the next open). 02 (§7.2 step 3, O13) fills at **the same close that triggered it**. Filling at a close whose value is only known *after* that close is a mild look-ahead and systematically flatters MA exits against the stop exits. **Adopt 01's next-open fill.**

### A3. Exit lab: is trade-level comparison (no slot limits) valid? **Valid for isolating the exit effect, not for picking a strategy.**
- **What it gets right:** identical entries (asserted by O19), so differences in expectancy, win rate and MAE/MFE are caused by the exit alone. That's the correct design for the question "which exit is better for *these* entries?" 02's ADR-014 reasoning is right.
- **What it misses:**
  1. **Holding-time bias.** Exits that hold longer (trailing, MA) show bigger per-trade expectancy but tie up capital longer. Per-trade expectancy alone favours them. **Add expectancy ÷ avg bars held** (return per bar of capital use) as a column.
  2. **Capital and slot competition.** In a real account, a quick stop frees a slot for the next signal. Trade-level mode can't show that (option value, turnover, exposure).
  3. **Correlated losses and drawdown path.** Entries cluster on the same dates (breakouts fire together in rallies), so trades aren't independent. The trade count overstates the effective sample, and the portfolio drawdown is invisible. *Cheap disclosure:* show "distinct entry weeks" next to "# trades".
  4. **The unconstrained equity curve in 02** (compounding the mean daily return of open trades) **isn't a tradeable curve.** It's effectively 100% invested whenever any trade is open, so its CAGR, max DD and Sharpe are misleading. **Remove those three from the exit-lab table** and keep per-trade metrics only.
  5. **The `horizon_bars` cap (default 60) in 02** is a hidden extra time exit. It truncates long-hold exits (trailing, MA) more than short ones. Show the "% exited by horizon" per config and warn above 10%.
  6. **Same-ticker overlap:** 01 allows overlapping trades on one ticker; 02 de-duplicates with `cooldown_bars` = 10. Pick one. Recommendation: rising edges plus a cooldown, documented.
- **Procedure to put in the README** (no code needed): choose the exit on **IS**, read **OOS once**, then run the chosen entry + exit **once as a single portfolio-mode backtest**. That mode already exists, so this costs nothing and covers point 2.

### A4. Inconsistencies between 01 v3.1 and 02 v2.0
| # | Topic | 01 | 02 | Resolve to |
|---|---|---|---|---|
| 1 | MA exit fill | Next open (B-6) | Same close (§7.2, O13) | **Next open** |
| 2 | Lead deferrals | Still has chart (M3, S-5, demo step 3), scatter (X-5), Sentry (M7), exit-lab portfolio block (X-6), R targets (B-4, B-12); total 55 h | Still has the portfolio toggle, `target.r`, O11, ADR-014 overlap metric; total 53 h | Both patch to the ≈ 51 h decision |
| 3 | Trial counter | Counts configs; warns at **> 20** | Counts distinct config+sim hashes; warns at **≥ 5** | A2(b) key; one threshold (suggest ≥ 10 on the structure key) |
| 4 | Entry definition | Rising edge; same-ticker overlap allowed | "Every signal" + cooldown 10 + horizon 60; rising edge not stated | Rising edge (valid t−1) + cooldown; horizon disclosed |
| 5 | Rule limits | ≤ 10 conditions; offset 0–20 | ≤ 8 conditions; offset 0–252; implicit `min_price` 5 | Pick one set; `min_price` visible as a condition |
| 6 | Indicator names | `highest_high`, `lowest_low`, `return` | `highest`, `lowest`, `ret` | One registry (02's Pydantic is the source of truth); 01 updates its examples |
| 7 | MAE/MFE exit bar | "Exit at open: only that open counts" | Exit-bar extreme capped at the exit level | 02's rule (covers both cases); one oracle |
| 8 | Exit-lab metrics | Trade-level: per-trade metrics only | Trades mode also shows CAGR, max DD, Sharpe on the unconstrained curve | Per-trade only (A3 #4) |
| 9 | "Best" highlight | Best IS and best OOS highlighted separately | Best **OOS** expectancy highlighted | Highlight IS only, with OOS shown beside it. Highlighting the best OOS invites picking on OOS |
| 10 | Demo artefact | GIF (4.2 lists "demo video" as a non-goal) | GIF | GIF is fine; owner to confirm it replaces the video |

### A5. MUST-fix lists (v4)

**PM (01):**
1. Patch 01 to the ≈ 51 h lead decision: remove the chart (M3 chart, S-5, demo step 3), the scatter (X-5 keeps the guide numbers only), Sentry, the exit-lab portfolio block (X-6), and R targets (B-4 R part, B-12). Update the totals and the demo script.
2. Add acceptance criteria for **rising edge = valid-and-false at t−1** (no edge on the first post-warm-up bar or a listing day) and **no entry on a ticker's last bar**.
3. Keep **next-open** for `close_below_ma` and make it the agreed rule with the Architect. Agree a single set of values for the trial-counter key and threshold, the condition and offset limits, indicator names, the MAE/MFE exit-bar rule, and cooldown versus overlap (A4).
4. Add acceptance criteria for the **random-entry baseline row**, **expectancy per bar held**, **distinct entry weeks**, **% exited by horizon**, and **MAE/MFE guides from IS trades only**. Highlight the best **IS** config only.
5. Add to "Limits of the research": index-selection look-ahead, OOS ≈ 2023–2026 bull regime, and the synthetic market's planted edge. Add the **IS-pick → OOS-once → single portfolio backtest** procedure to the research-note template.

**Architect (02):**
1. Change `close_below_ma` to fill at **open(t+1)** (§7.2, O13). Implement the rising-edge validity rule in the compiler and the last-bar no-entry rule. Add both to the poisoned-future and oracle tests.
2. Patch 02 to the lead's deferrals: remove the portfolio toggle from the exit lab, `target.r`, O11 and the overlap metric. Keep portfolio mode for single backtests only.
3. Exit-lab output: **remove CAGR, max DD and Sharpe** of the unconstrained curve. Add expectancy per bar held, distinct entry weeks, and % exited by horizon (warn above 10%).
4. Build the **random-entry baseline** (same count, seeded, same exits, "edge vs random" column) and the **structure-keyed + global trial counter**. Budget ≈ 1.5–2 h from buffer.
5. Run trades mode **per trade over its own bars**, and move the 6-config performance check to Day 4 right after B1, before the UI depends on it.
6. Re-baseline: oracle authoring at **6 h** (not 4), 51 h as **P50** and ≈ 60 h as **P80**. State which items move to the cut line if Day 4's checkpoint slips.

---

> **Binding frame (from the owner):**
> - This is a **learning and portfolio project for practising agentic coding**. It will never be sold and has no paying users.
> - **$0/month.**
> - **Public repo.**
> - **Ready in under one week:** about 40–50 focused hours, built with AI coding agents.
> - **Backtesting is compulsory.**
> - The demo is a **synthetic public demo**, plus a **personal real-data mode**, plus a **recorded video**.
>
> Everything is judged on **learning value, CV signal, demo-ability, and hours and cost**.
>
> **Severity:** **Critical** = blocks shipping in one week or breaks $0/ToS; **High** = costs a day or more; **Medium** = costs hours; **Low** = polish.

---

## 1. Verdict: **Go, with a much smaller build**

A one-week build *can* produce a strong portfolio piece. The pitch: **"Pick a swing setup, tweak its parameters, see today's hits on a chart, and backtest it honestly (next-open fills, costs, delisted names included, out-of-sample shown separately), deployed for $0 with CI and tests."** That shows TypeScript/React, Python, a real compute engine, a cloud deploy, CI/CD and test discipline. The backtester with a planted-delisting test is the interview talking point.

What has to go: almost everything in 01 and 02. Both are designed for 6–24 months.
- **The Architect's $0 stack** (Lambda + SQS + R2 + Neon + Clerk + HCP Terraform + Grafana + GitHub Actions cron) is **still too much for one week**. It has 8 services to wire up before the first feature, and most are unnecessary when the public data is synthetic and static.
- **The PM's 38 h MUST list** is the right *shape*, but it's under-estimated by about 40–60% because it leaves out scaffolding, the API, the UI shell and integration (Section 4).

---

## 2. Product critique (01, 01a)

### P-1. 01's MVP is about 30× too big for a week. **Critical**
- **Evidence:** About 30 "Must" items, a 20-year bias-free database, a visual builder, market health, alerts, a scorecard, share links, billing.
- **Recommendation:** The week-1 product is **"Setup Lab, minimal"**:
  - 2–4 preset scans with editable parameters;
  - a results table with a chart;
  - **one** backtest form, the portfolio simulation, kept lite (Section 4);
  - one honesty feature: an in-sample/out-of-sample split shown side by side.

  Everything else is "Later". **One imaginary persona:** a part-time swing trader asking "does my setup actually work?"

### P-2. Pick ONE backtest form: portfolio-lite, not the signal study. **High**
- **Evidence:** A signal study (forward returns vs base rate) is easier to vectorise, but it doesn't look like a "backtest" to a recruiter. It has no equity curve and no trade list. A full portfolio simulator with 4 exit types and risk sizing is a week on its own.
- **Recommendation:** Build a **portfolio-lite simulator**:
  - entry at the next open;
  - **two exits only**, a stop (% or ATR) and a time stop;
  - **equal-weight sizing** with max N positions;
  - slippage at 10 bps a side;
  - forced exit at the last close on delisting;
  - an equity curve against a benchmark, a trade list, CAGR, max drawdown, win rate, number of trades;
  - IS/OOS as a single date split.

  It's a Python day loop with no Numba, around 1,260 days × 500 tickers, so it runs in under a second. The signal study is a stretch goal.

### P-3. The free-data research (01a) is accurate but irrelevant for the public build. **Medium**
- **Evidence:** 01a correctly finds that every free *price* source is licensed for **personal, non-commercial use only**. Massive's KB says a Business plan is needed as soon as "anyone else" can see the data, "including testers and internal staging users", during development too, and it covers derived values (verified). Free depth is about 2 years including delisted names (Massive Grouped Daily), or 2016+ survivors only (Alpaca).
- **Recommendation:** In week 1, use **one** real source: **Alpaca free** (a paper account is enough; multi-symbol bars endpoint; 200 calls/min; `adjustment=all` returns split- and dividend-adjusted bars). About 500 current S&P 500 tickers × 5 years takes **a few minutes** to fetch. **That history depth is fine for a learning backtester**, provided the UI labels personal mode "survivors only: results are biased upward". Saying so is itself an honesty point.
  - Drop Massive, Stooq, Tiingo, SEC, FRED and the Nasdaq calendar for week 1. Fundamentals, earnings, RS-vs-universe and sectors are "Later". **SEC SIC codes** stay the recommended sector source when sectors return.

### P-4. A frozen sample of *real* prices in the public demo is redistribution. **Critical**
- **Evidence:** Committing or serving 50–100 real tickers from Alpaca or Massive, even frozen and even few, means displaying vendor data to third parties. A smaller list doesn't change who sees it. Backtest results computed from those prices are derived data and fall under the same rule. A **public repo** makes it worse: a committed Parquet file is redistribution to anyone who clones it.
- **Recommendation:** **The public demo uses synthetic data only. Real data never leaves the owner's machine.**
  - Personal mode in week 1 is **local-only** (`DATA_MODE=live` runs only on localhost). That's simpler and safer than a deployed login-gated mode, and it removes Clerk from week 1.
  - `data/` is in `.gitignore`. CI and test fixtures are synthetic.
  - **Record the video in synthetic mode.** If a few seconds of personal mode appear, show the workflow, not tables of real prices.

### P-5. The PM's 1-week MUST list is about 38 h on paper and about 55–60 h in reality. **Critical**

| PM item | PM est. | Realistic | Comment |
|---|---|---|---|
| Synthetic generator, 500 × 10 yrs | 5 h | 4 h | Keep. **Use 5 years** (enough for IS/OOS). Plant delistings. Splits are a stretch: if the engine works on adjusted prices, planted splits test only the generator. |
| Personal mode (Alpaca, local) | 3 h | 3–4 h | Keep, but it's **the first thing to cut** if behind |
| 4 presets + RS column | 6 h | 5 h | Start with **2 presets** (breakout, pullback), add 2 if on time. Make RS **"6-month return percentile within the demo universe"** (one line in Polars), not IBD-style. |
| Chart with hit markers | 4 h | 4 h | Keep. It's the best visual in the demo. Lightweight Charts. |
| Portfolio backtest (4 exits, risk sizing, ...) | 12 h | 18–24 h | **Cut target and trailing-MA exits, and replace fixed-risk sizing with equal weight.** That brings it to about 10–12 h (P-2). |
| Correctness tests | 3 h | 4 h | Keep, **test-first**: 3 hand-computed micro cases (stop hit, time exit, delisting), plus a poisoned-future test (1 h, high CV value) |
| Deploy, README, video | 5 h | 6 h | Deploy on **Day 1**, not Day 7 |
| **Missing:** repo scaffold, AGENTS.md, CI, API endpoints, UI shell, results table, backtest form and results page, integration and debugging | **0 h** | **14–18 h** | This is why the 38 h figure doesn't hold |
| **Total** | **38 h** | **≈ 55–60 h as listed; ≈ 42–46 h with the cuts above** | |

**Cut first, in order:**
1. target and trailing exits, and risk sizing;
2. presets 3–4;
3. planted splits;
4. personal mode;
5. trade drill-down on the chart.

**Competitor corrections (kept for product thinking and interviews).** "Nobody backtests scans in a browser" is false:
- **Portfolio123** has point-in-time simulations that include dead companies;
- **MarketInOut**'s screen backtester is survivorship-bias-free;
- **QuantConnect** is a free web IDE with bias-free data;
- **Finviz Elite** has a 24-year backtester with stops, time exits and an SPY benchmark (verified).

The README should position the project as "a learning build of the scan-to-backtest loop with honest defaults", not as a market gap.

*If it were commercial (one line only):* data licensing ($500–2,000/month for display rights), pricing and marketing-claims rules would dominate. None of that applies here.

---

## 3. Technical critique (02 and the planned $0 stack)

### T-1. 02's cost model ($230/month + licence) contradicts $0. **Critical** (resolved in direction)
- **Evidence:** ECS, RDS, ElastiCache and ALB aren't free. Since **15 July 2025**, new AWS accounts get **$100–200 of credits and a free plan lasting up to 6 months**, then pay-as-you-go. Only about 30 "always free" services remain, Lambda among them (verified). ECS + RDS would burn the credits and then bill monthly.
- **Recommendation:** No ECS, RDS, ElastiCache or ALB. The Architect's revised shape already drops them. Good.

### T-2. The Architect's $0 stack is still too many moving parts for one week. **Critical**

| Component | Verdict for week 1 | Why |
|---|---|---|
| Vercel Hobby (Next.js) | **Keep** | $0, personal non-commercial use fits, PR previews free |
| FastAPI on **AWS Lambda + Function URL** (container image, Lambda Web Adapter or Mangum) | **Keep** (AWS on the CV) | Always-free tier. **Fallback:** Google Cloud Run free tier if Lambda packaging eats more than 3 h. Render free is simpler, but its about 30–60 s cold start ruins a live demo. |
| SQS | **Cut** | A 500 × 5-year backtest runs in about 1 s, so call it synchronously |
| GitHub Actions **nightly cron** | **Cut** | Synthetic data is static, and personal mode is a manual local script. Also, **GitHub disables scheduled workflows in public repos after 60 days without repo activity**, so a cron-fed demo would quietly go stale. |
| Neon Postgres | **Cut** | No user accounts and no saved scans: presets and parameters live in the **URL query string** (shareable links for free). Neon free (0.5 GB) is the first "Later" addition. |
| Cloudflare R2 | **Cut** | Synthetic Parquet is about 10–20 MB. **Bundle it in the container image** (generated at build time from a fixed seed). |
| Clerk | **Cut** | Personal mode is local-only (P-4) |
| Resend | **Cut** | No alerts |
| HCP Terraform | **Stretch (Day 7)** | IaC is a real CV signal, but in week 1 it adds 3–5 h of yak-shaving. If time allows, Terraform only the Lambda function, Function URL, ECR repo and IAM OIDC role, with an S3 or local backend. |
| Sentry free | **Keep (30 min)** | A cheap observability line on the CV |
| Grafana / OTel | **Cut** | Low payoff in one week |
| GitHub Actions CI/CD | **Keep** | lint, typecheck and tests on PR; on main, build the image, push to ECR via **OIDC** (no static keys), update Lambda. Vercel deploys itself. |

**Resulting week-1 stack:** Next.js + TS + Tailwind on Vercel Hobby. FastAPI + Polars + NumPy in a Docker image on AWS Lambda (Function URL). Synthetic Parquet baked into the image. GitHub Actions CI/CD with OIDC. pytest (+ Hypothesis if time allows), Vitest, one Playwright smoke test, Sentry. **Cost:** $0 for Vercel and Lambda. ECR is a few cents a month for an image under 1 GB once the free-plan credits end; keep the image small and set an **AWS Budgets alarm at $1**.

### T-3. Lambda limits and cold starts. **Medium**
- **Evidence:**
  - Lambda allows 15 min and up to 10 GB memory. Function URLs avoid API Gateway's 29 s cap.
  - The synchronous response payload limit is **6 MB**.
  - A container image with Polars + NumPy + FastAPI cold-starts in roughly 2–5 s.
  - The workload (500 tickers × 1,260 days) needs a few hundred MB and about 1 s.
- **Recommendation:**
  - Set memory to 1,024–2,048 MB (more memory also means more CPU).
  - Load the Parquet once at module import.
  - Cap the trade list (e.g. 2,000 rows) and downsample the equity curve to stay under 6 MB.
  - Show a "warming up" state in the UI.
  - Skip Numba. Its JIT compile would add seconds to cold starts, and the loop doesn't need it.
  - Measure the cold start on Day 1 and record it in the README.

### T-4. One store for bars; memory is no longer an issue. **Low** (resolved)
- **Evidence:** v1 found that 25 years × 25k securities as dense arrays needs about 8.8 GB. At 500 × 1,260 that's about 2.5 MB per column.
- **Recommendation:** Parquet is the single bar store, Polars reads it, and there's no Postgres copy. Put the "how this scales" note (sparse layout, liquid universe, chunking) in an ADR. Interview material for free.

### T-5. Corporate actions and simulator rules need explicit decisions. **High**
- **Recommendation:**
  - The engine runs on **adjusted prices only** (synthetic data is generated adjusted; Alpaca with `adjustment=all`). Raw-price filters are "Later", and that's documented.
  - On a **delisting**, exit at the last close (synthetic delistings are planted, and there's a test).
  - When the stop and the target are hit in the same bar, **assume the stop first**. With no target exit this can't happen, but write the rule down anyway.
  - **Signal at close(t), fill at open(t+1)**, enforced by the poisoned-future test.
  - Slippage defaults to 10 bps a side.
  - Calendar: synthetic business days. Personal mode uses Alpaca's trading days as given.

### T-6. Holdout "contamination" and the trial counter. **Low** (cut)
- **Recommendation:** Week 1 shows IS and OOS metrics side by side, using the last 30% of dates as OOS. The trial counter and contamination state are "Later".

### T-7. Not yet shaped for agentic coding. **Critical**
- **Evidence:** 02's tasks are 4–40 h, with no acceptance criteria, no AGENTS.md and no review gates. The repo already has `/audit`, `/scope`, `/architect`, `/develop`, `/test`, `/check` and `/sync` installed (`.claude/skills/`, `skills-lock.json`).
- **Recommendation (a one-week version of the process):**
  1. **Day 1, 30 min:** `/audit` creates AGENTS.md: commands, layout, "never commit `data/`", "never call live vendor APIs in CI", and "don't edit `tests/oracle/` without the owner".
  2. **One short spec per feature** (`/architect`, about 15 min each): goal, API contract, **Given/When/Then acceptance criteria**, test command, out-of-scope list. Four specs in total: data/synthetic, scan, backtest, UI.
  3. **Task size of 1–2 h** per agent run.
  4. **Test-first for the engine:** the owner writes or approves the 3 hand-computed oracle cases and the poisoned-future test *before* an agent implements the simulator. This guards against an agent writing matching wrong code and wrong tests.
  5. **Review gates:** CI green, then `/check review` on engine PRs, then the owner reads the engine diff line by line. UI diffs can be skimmed.
  6. **Parallelism:** web and engine agents work in separate worktrees against the agreed API contract (OpenAPI → generated TS types).
  7. Keep a short **agent log** (what was delegated, what broke, what the tests caught). It's the most valuable part of the README for "agentic coding" roles.

### T-8. Employability claims should be honest. **Low**
- **Recommendation:** The README lists what is actually there: Next.js/React/TS, Python/FastAPI/Polars, Docker, AWS Lambda + ECR + IAM OIDC, GitHub Actions CI/CD, pytest/Vitest/Playwright, Sentry, and agentic workflow. Terraform appears only if it was done. The 02 job-market figures are directional (SO survey usage, small posting samples), so don't cite them in the README.

---

## 4. Day-by-day plan (about 6–7 h/day)

| Day | Build | Done when |
|---|---|---|
| **1** | Monorepo (pnpm Next.js + uv FastAPI), AGENTS.md via `/audit`, CI (lint, typecheck, tests). **Synthetic generator** (500 tickers × 5 yrs, seeded GBM with regimes, planted delistings, a `DEMO-INDEX` benchmark) → Parquet. **Deploy hello-world** to Vercel and to Lambda via CI with OIDC. | Both URLs live. CI green. Cold start measured. |
| **2** | Indicators (SMA/EMA, ATR, 20-day high, volume average, 6-month return percentile) in Polars. **2 presets** with editable parameters. `GET /scan`. Results table UI with parameters in the URL. | A scan returns hits on the deployed site |
| **3** | **Backtest engine, test-first:** oracle cases + poisoned-future test written and approved first, then the simulator (next open, stop + time exit, equal weight, max N, slippage, delisting exit) and metrics | All oracle tests pass |
| **4** | `POST /backtest`. Backtest page: parameter form, equity curve vs benchmark, metrics table with **IS/OOS side by side**, trade list | A backtest runs end to end on the deployed site |
| **5** | **Chart** (Lightweight Charts) with scan-hit markers. Click a trade to see entry and exit on the chart. Presets 3–4 if on time. Sentry. | The demo script runs end to end |
| **6** | **Personal mode:** local Alpaca loader script → Parquet, `DATA_MODE=live` limited to localhost, "survivors only" badge. Playwright smoke test. README: architecture diagram, ADRs (no DB, sync Lambda, synthetic data, NumPy over Numba), agent log. | A local real-data run works. README complete. |
| **7** | Buffer and bug fixes. **Record the 3-minute video** (synthetic mode). Stretch: Terraform for the Lambda resources, signal study, planted splits. | Video linked in README. Tag v1.0. |

**Cut line if behind:** drop personal mode (Day 6) → trade-on-chart drill-down → presets 3–4 → IS/OOS split.

**Never cut:** synthetic data, one preset scan with a chart, the portfolio-lite backtest with oracle tests, the CI deploy, the README, the video.

---

## 5. Cross-document inconsistencies (still open)

| # | Topic | Conflict | Resolution |
|---|---|---|---|
| X-1 | Timeline | 01: 4–6 months; 02: 52 weeks; owner: 1 week | Section 4 plan |
| X-2 | Backtest form | 01: signal study is the hero; 02 and PM list: portfolio simulator | Portfolio-lite; signal study as a stretch |
| X-3 | History | 01: 20+ yrs bias-free; 01a: 2 yrs bias-free / 2016+; PM list: 10 yrs synthetic | Synthetic 5 yrs; personal mode 5 yrs survivors only, labelled |
| X-4 | Public data | PM option: a frozen sample of real tickers | Synthetic only (P-4) |
| X-5 | Personal mode | Owner: login-gated; PM list: local-only | **Local-only in week 1**; login-gated deployment is "Later" |
| X-6 | Slippage | 01: 10 bps; 02: 5 bps | 10 bps |
| X-7 | Delisting | 01: last price; 02: −30% haircut | Last close (synthetic delistings are clean by construction) |
| X-8 | Sizing | PM list: fixed risk; 02: three modes | Equal weight |
| X-9 | Stack | Architect $0 shape: 8+ services | Section 3 T-2 |

---

## 6. Required changes

### 6.1 Product Manager MUST:
1. **Rewrite 01 for the binding frame:** a learning/portfolio/$0/one-week build, one persona, and a **3-minute demo script**. Reduce pricing, KPIs, market sizing and monetisation to a one-line "if it were commercial" note.
2. **Adopt the cuts to the MUST list** (P-5):
   - portfolio-lite (stop + time exits, equal weight);
   - 2 presets with 2 more as stretch;
   - RS as a 6-month return percentile;
   - synthetic data 5 years with planted delistings, splits as stretch.
3. **Public data is synthetic only.** Remove the "frozen sample of real tickers" option. Personal mode is local-only, and the video is recorded in synthetic mode (P-4).
4. **Trim 01a to week 1:** Alpaca (local personal mode) only. Mark Massive, SEC/EDGAR (including SIC codes for sectors later), FRED and Nasdaq as "Later". State that 2016+ survivors-only history is acceptable when labelled (P-3).
5. **Settle the defaults:** next-open fills, 10 bps slippage, last-close delisting exit, stop first on same-bar conflicts, last 30% of dates as OOS (T-5, X-6 to X-8).
6. **Write Given/When/Then acceptance criteria** for the four specs: data, scan, backtest, UI (T-7).
7. **Keep the competitor corrections** (Portfolio123, MarketInOut, QuantConnect, Finviz Elite) as README and interview context, and drop the "nobody does this" claim.

### 6.2 Architect MUST:
1. **Replace the roadmap with the 7-day plan** (Section 4) and its cut line. Re-estimate the PM list honestly (≈ 42–46 h after cuts).
2. **Shrink the $0 stack:** Vercel Hobby + FastAPI on Lambda (Function URL) + synthetic Parquet baked into the image + GitHub Actions CI/CD with OIDC + Sentry. **Drop SQS, cron, Neon, R2, Clerk, Resend and Grafana from week 1. Terraform is a Day-7 stretch.** Put Cloud Run as the fallback in an ADR. Set an AWS Budgets alarm at $1.
3. **Handle the Lambda limits:** 1–2 GB memory, load data at import, cap the trade list and downsample the equity curve to stay under 6 MB, warm-up UI state, cold start measured on Day 1 (T-3).
4. **Specify the simulator** as portfolio-lite, in NumPy with a day loop and no Numba. Use adjusted prices only, signal at close and fill at the next open, delisting exit at the last close (T-5).
5. **Owner-approved oracle tests and the poisoned-future test come first.** Add AGENTS.md via `/audit`, 4 short specs via `/architect`, 1–2 h agent tasks, and review gates (CI, `/check review`, owner reads engine diffs). Protect `tests/oracle/` (T-7).
6. **Licence hygiene in a public repo:** `data/` is gitignored, CI and fixtures are synthetic, `DATA_MODE=live` refuses to run anywhere but localhost, and no recorded HTTP cassettes are made from vendor data (P-4).
7. **Keep the valid long-term points as short ADRs, not as week-1 work:** single bar store (Parquet), how memory scales (sparse layout, liquid universe), corporate actions and raw-price filters, holdout contamination, and when to add a DB, a queue or auth. Make the employability claims match what was actually built (T-4, T-6, T-8).

---

## 7. Sources

- Massive KB: third-party display needs a Business plan, "including testers and internal staging users", during development; derived values are covered by the same plan rules: https://massive.com/knowledge-base/article/which-plan-do-i-need-to-show-massive-data-in-my-app
- AWS Free Tier change (15 July 2025: credits, 6-month free plan, always-free services): https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/ ; https://spot.rackspace.com/blog/aws-free-tier
- Neon free plan (0.5 GB, 100 CU-hours): https://neon.com/pricing
- Cloudflare R2 free tier (10 GB, zero egress): https://www.spendbase.co/?p=35561
- Upstash free tier: https://upstash.com/docs/Redis/overall/pricing
- Clerk free tier (50k MRU since 2026-02-05): https://clerk.com/articles/clerk-pricing-explained
- Norgate EULA (personal use only): https://norgatedata.com/subscribe/eula.php
- Competitors: Portfolio123 https://daytradingz.com/portfolio123-review/ ; MarketInOut FAQ https://marketinout.com/home/faq.php ; Finviz Elite backtesting https://www.liberatedstocktrader.com/finviz-review/
- Free-data terms and Alpaca/Massive limits: `docs/01a-free-data-sources.md` §2–3 and its sources
- Installed agent skills: `skills-lock.json`, `.claude/skills/`

*Not independently verified in this pass:* Alpaca's redistribution terms (treated as personal-use only), GitHub's 60-day scheduled-workflow rule, Lambda's 6 MB synchronous payload limit and cold-start range. The last three come from my own knowledge of GitHub and AWS docs; re-check them during Day 1.

# Research note 0001: a fixed 8% stop against a 10% trailing stop, on the synthetic market

**Run 2026-10-16 · synthetic market, seed 42 · published note (the live notes stay private)**

> **The edge in this market is planted.** The synthetic generator contains a documented momentum
> term, so a breakout template looks good here by construction. This note demonstrates the
> method and the engine, never a strategy. Nothing here is investment advice.

## 1. Hypothesis

For 52 week breakouts, a 10% trailing stop beats a fixed 8% stop **per bar held**.

That was the hypothesis doc 01 §4.3 uses as its worked example, and it is the intuitive one: a
trailing stop banks gains that a fixed stop gives back. This note tests it and **it is false on
this market**, for a reason worth keeping.

## 2. Setup

| | |
|---|---|
| Data | `synthetic-1`, seed 42, 500 tickers plus `DEMO-INDEX`, 2021-01-04 → 2025-10-31 |
| Entry | the `breakout_52w` template, unmodified: `close > highest(252)[1]` **and** `volume > 1.5 × avg_volume(50)` **and** a price filter |
| IS / OOS split | **2024-05-22** (the last 30% of sessions is OOS, `oos_fraction` 0.3) |
| Entries | **2,780** (1,380 IS, 1,400 OOS) across **185 distinct entry weeks**, hash `83c3dffa…` |
| Horizon | 60 bars (trade mode) |
| Fills | signal close → next open, 10 bps slippage, no commission, equal weight, rising edge entries, 10 bar cooldown, no same ticker overlap |
| Structure key | `5cfef491980150f5…` |

Identical entries across all six configs, which is the whole point of the lab: only the exit
changes. 185 distinct entry weeks is the honest sample size, not 2,780.

## 3. IS pick (IS columns only)

Six configs, chosen to put the hypothesis's two candidates beside four sensible neighbours.

| config | exp / bar % | expectancy % | exp R | win % | profit factor | avg MAE % | avg MFE % | horizon exits % | avg bars |
|---|---|---|---|---|---|---|---|---|---|
| **fixed_8** | **0.038** | **1.264** | **0.158** | 31.30 | 1.238 | −6.68 | 14.00 | 35.87 | 32.8 |
| atr_2 (k=2, n=14) | 0.034 | 0.959 | 0.140 | 25.80 | 1.196 | −5.78 | 12.93 | 27.68 | 27.8 |
| fixed_8 + target 15% | 0.023 | 0.481 | 0.060 | 37.97 | 1.099 | −6.30 | 8.55 | 6.45 | 21.3 |
| **trail_10** | **0.005** | **0.105** | **0.011** | 34.49 | 1.027 | −5.18 | 10.81 | 6.01 | 20.2 |
| fixed_8 + close<SMA21 | −0.002 | −0.036 | −0.005 | 33.55 | 0.990 | −4.98 | 9.67 | 1.45 | 16.1 |
| trail_10 + time 20 | −0.038 | −0.525 | −0.052 | 38.55 | 0.855 | −5.09 | 8.08 | 0.00 | 13.9 |

And against the random entry baseline, which runs random entries in the same market through the
same exits, so the difference is the part that is not just market drift:

| config | strategy exp / bar % | random exp / bar % | **edge / bar** | edge on expectancy (pp) |
|---|---|---|---|---|
| **fixed_8** | 0.038 | 0.013 | 0.026 | **+0.866** |
| atr_2 | 0.034 | 0.014 | 0.020 | +0.553 |
| fixed_8 + target 15% | 0.023 | 0.000 | 0.022 | +0.473 |
| trail_10 | 0.005 | −0.008 | 0.013 | +0.256 |
| fixed_8 + close<SMA21 | −0.002 | −0.046 | **0.044** | +0.291 |
| trail_10 + time 20 | −0.038 | −0.012 | −0.026 | −0.367 |

**Pick: `fixed_8`.** It has the best expectancy per bar (0.038%) and the largest edge on
expectancy (+0.87pp), and it is positive on both. The hypothesis is **rejected**: `trail_10` is
seventh-tenths of nothing per bar (0.005%), about one seventh of the fixed stop's.

Two things the table teaches that a single number would hide:

- **`fixed_8 + close<SMA21` has the largest edge per bar (0.044) and is still not the pick.** Its
  own expectancy per bar is *negative* (−0.002). The edge is large because its random baseline is
  even worse (−0.046). An edge over a losing baseline, while losing, is not a reason to trade
  something. Edge is a second screen, never the first.
- **Every config that cuts trades short wins more often and earns less.** Win rate climbs
  monotonically as the exits get tighter (31% → 38.6%) while expectancy per bar falls (0.038 →
  −0.038). The trailing stop and the MA exit are doing what they promise, protecting open profit,
  and in a planted uptrend that is simply the wrong thing to do.

**MAE and MFE guides (IS winners only):** 75% of winning trades never dipped below **−5.72%**,
90% never below **−6.87%**, and the median winner ran to **+8.35%**. So an 8% stop sits just
outside where 90% of winners ever traded: loose enough not to cut them, which is exactly why the
fixed stop survives here and the tighter exits do not.

## 4. OOS, read once

Read once, for `fixed_8` only, after the pick was fixed.

| | IS | OOS |
|---|---|---|
| trades | 1,380 | 1,400 |
| win rate % | 31.30 | 43.21 |
| expectancy % | 1.264 | **5.335** |
| expectancy per bar % | 0.038 | **0.151** |
| expectancy R | 0.158 | 0.667 |
| profit factor | 1.238 | 2.228 |
| **random** expectancy % | 0.399 | **5.015** |
| **edge on expectancy (pp)** | **+0.866** | **+0.321** |
| **edge per bar** | **0.026** | **0.006** |

**This is the result worth the note.** In absolute terms `fixed_8` looks four times better out of
sample: expectancy goes 1.26% → 5.34%. But the random entry baseline goes 0.40% → **5.01%**. Put
another way, **the edge over random falls by 78% (0.026 → 0.006 per bar) while the headline number
quadruples.** Win rate tells the same story: the strategy goes 31.3% → 43.2%, and random goes
30.1% → **42.7%**, tracking it to within half a point.

Nearly all of the apparent out of sample improvement is the regime, not the rule. A note that
reported only "expectancy 1.26% IS, 5.34% OOS, holds up out of sample" would be wrong in the most
flattering possible direction, and this is precisely the mistake the random baseline column exists
to catch.

## 5. Single portfolio backtest

The same entry and the chosen exit, once, in portfolio mode: 10 positions, equal weight, 10 bps.

| | strategy IS | benchmark IS | strategy OOS | benchmark OOS |
|---|---|---|---|---|
| CAGR % | **10.27** | −3.04 | **51.93** | 22.61 |
| max drawdown % | −33.98 | −38.89 | −25.62 | −29.69 |
| Sharpe | 0.54 | | 1.56 | |
| trades | 48 | | **6** | |
| exposure % | 67.9 | | 99.6 | |
| avg bars held | 162.0 | | 118.5 | |

It beats `DEMO-INDEX` in both windows on both return and drawdown. **Do not believe it**, for a
reason the per trade view cannot show:

**Portfolio mode has no horizon; trade mode does.** The lab closes anything still open at 60
bars, and 35.9% of `fixed_8`'s IS trades hit that. In portfolio mode nothing closes a winner but
the 8% stop, so positions ran an average of **162 bars** and the 10 slots stayed occupied: 99.6%
exposure and **6 trades** in the whole OOS window. Six trades is not a sample, and a strategy that
holds ten names for years is a buy and hold, whatever the entry rule was.

So the two views of the same config disagree, and both are right about different questions. The
honest reading is that `fixed_8` is a reasonable *per trade* exit and an unusable *portfolio*
configuration, and that a config intended for portfolio use needs a time or horizon exit. Picking
one now and re-running would be a **new trial**, so it belongs in the next note, not this one.

## 6. Trials

- Structure key `5cfef491980150f5…`, **trial 1** for this rule structure. The exit lab run and the
  portfolio run share the structure key (same entry rule); the lab contributed 6 pair keys, the
  portfolio run 1.
- Nothing was changed after looking at OOS. The hypothesis was rejected on IS alone, before OOS
  was read.
- One procedural caveat, stated because the tool does not enforce it: a single `/backtest` call
  returns IS and OOS together, so "read OOS once" is a discipline the researcher keeps, not a
  thing the API withholds. The trial counter and the IS only highlight make breaking it visible,
  not impossible.

## 7. Limits

From doc 01 §8.1, the ones that bite here:

1. **The edge is planted** (§8.1 item 7). The generator has a documented momentum term, so a
   breakout rule is being graded on a market built to reward it. This note shows the method
   works, not that the method finds anything.
2. **One regime in OOS** (item 3). The OOS window is a strong uptrend, which is exactly what the
   random baseline collapse in §4 is measuring.
3. **Trade mode ignores capital** (item 6). 185 distinct entry weeks is the sample size, not
   2,780 trades, and §5 shows what happens when capital is applied.
4. **Multiple testing** (item 5). Six exits on one entry rule is six looks. The structure keyed
   counter is at trial 1 only because this is the first run of this structure.
5. **Costs are simple** (item 8). 10 bps slippage, no commission, no borrow, no taxes.
6. **Horizon truncation.** 35.9% of IS and 41.8% of OOS `fixed_8` trades were cut by the 60 bar
   horizon, which the engine warned about on both. Its per bar numbers are therefore a lower
   bound on how long the trades wanted to run.

The two biases that dominate the live dataset, survivorship and index selection look ahead
(items 1 and 2 of §8.1), do **not** apply to this note: the synthetic market has planted
delistings and a fixed universe. They will apply to every live note.

## 8. Conclusion

**The hypothesis is rejected, with moderate confidence on this market and none beyond it.** A 10%
trailing stop does not beat a fixed 8% stop per bar held on the seed 42 synthetic market; it
earns about one seventh as much per bar, and the tighter the exit, the worse the per bar
expectancy and the better the win rate. The MAE guide says why: 90% of winners never traded below
−6.87%, so 8% is loose enough to leave them alone, and anything tighter sells them.

Confidence is limited to this market and mostly by construction, since the edge is planted. The
more durable finding is methodological: **`fixed_8`'s out of sample expectancy quadrupled while
its edge over random entries fell 78%.** Absolute out of sample numbers cannot tell you whether a
rule works. Only the gap to a random baseline run through the same exits can, and here that gap
nearly vanished.

**Next step:** re-run the chosen entry with a time exit added, so the portfolio backtest produces
a usable number of trades (a new trial, in a new note). Then the same procedure on
delisted inclusive data, where survivorship and index selection stop being hypothetical. Until
then this is a demonstration of the engine, not evidence about breakouts.

---

_Reproduce: `make data` (seed 42), `make dev`, then the exit lab on the `breakout_52w` template
with the six configs in §3. Entries hash `83c3dffaac04de95…` pins the entry set; a different hash
means a different market or rule._

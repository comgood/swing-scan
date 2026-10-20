# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Portfolio backtest on `POST /backtest`. You give one entry rule and one exit setup, and the
  engine walks the trading sessions one day at a time: it buys the top ranked new signals into
  free slots at the next open, then runs every position it holds through one shared exit
  function. You get in sample and out of sample numbers side by side, an equity curve against
  the `DEMO-INDEX` benchmark, and a trade list that records how far each trade went against you
  and in your favour, in percent and in R (see spec 0007).
- Four exits for that run: a percent stop, a time exit counted in bars, an exit when a ticker
  you hold delists, and an exit for anything still open on the last session of the window.
  Which one wins on a bar is decided in one place, `step()`, so later exit types drop in
  without touching that order.
- Sizing and slot rules you can check rather than trust: equal weight at equity divided by
  `max_positions`, read at the signal close and capped by the cash you actually hold, one
  position per ticker, fractional shares, no leverage, and slippage on every fill. A slot an
  exit frees today only opens up tomorrow, and cash from an exit on a session never funds an
  entry on that same session, so nothing is sized with money that only exists later in the day.
  The day loop steps by session date, so a ticker with no bar on a session is left where it is
  and keeps its last close, and no bar dated after the session is ever read.
- An assumptions header on every result that repeats every setting the run used: fill model,
  slippage, commission, sizing, the signal cooldown, where the out of sample split falls, and
  the data mode, version and seed. Settings portfolio mode does not use read "not used in
  portfolio mode" (U-3).
- A report page at `/backtest` in the web app: the exit and window form, the assumptions header,
  the in sample and out of sample metrics table with the benchmark beside it, the equity chart
  with the out of sample start marked, a sortable trade list, and the run trial counter.
  Loading, warming up, invalid input, not implemented and "no entries" all render as their own
  state. The page works from the keyboard and holds together at 375 px wide.
- Limits that keep a result small enough to send back: curves are thinned to at most 500 points,
  the trade list keeps the 2,000 most recent trades and says how many there were in total, and
  the numbers are always computed from every trade rather than from the shortened list. A full
  history run on the seed 42 market answers warm well inside the 3 s and 6 MB budget.
- The exit lab. Send `POST /backtest` 2 to 6 exit setups instead of one and you hold the entry
  rule still and compare the exits trade by trade. The entry list is worked out once and shared,
  so the only thing that differs between rows is the exit. Every accepted signal becomes one
  trade of the same size, trades on the same ticker may overlap, and you get per trade numbers
  only, as an in sample and out of sample pair: expectancy in percent and in R, expectancy per
  bar, win rate, average hold, how many distinct weeks you entered in, and the share of trades
  that simply ran out of time at the horizon. There is no CAGR, drawdown or Sharpe anywhere in
  this result, because those belong to a portfolio and not to a pile of equal trades (spec 0009).
- A random entry baseline in the same table. Each setup also runs a seeded sample of random
  entries through its own exits, with exactly as many random trades as the strategy had in each
  segment, so every row can report its edge: the strategy number minus the random one, left
  empty when either side is missing. The seed is yours (`sim.seed`, default 42) and the same
  seed gives you the same sample, so a run is reproducible.
- Reading help that tries not to fool you: the best in sample value of each metric is marked,
  and only ever in the in sample column, never on an out of sample, random or edge number. A
  guide row under the table takes the first setup's in sample trades only and shows how far
  winners dipped against you at the 75th and 90th percentile, measured on depth so the 90th is
  the deeper of the two, next to the median best excursion as a target guide. A setup where more
  than one trade in ten exited at the horizon gets a warning on its row.
- Expectancy in R now survives a setup whose stop is missing on a few trades. An ATR stop has no
  level yet in a ticker's first bars, and random entries land there often, so R is averaged over
  the trades that do have a stop and only reads "n/a" when the setup has no stop at all.
- The exit lab table on `/backtest`, shown when a result comes back in trade mode: one row per
  setup with the in sample and out of sample pairs, a "best IS" marker that does not depend on
  colour, an edge group per row, a "Random entries" row, a disclosure on each row for its own
  random numbers, the procedure note directly under the table, and the trial counter beside the
  assumptions header. The table scrolls inside its box at 375 px wide with the setup column
  pinned.
- Speed work on the per trade loop, since it walks a lot of bars (six setups plus the baseline on
  the `pullback_ema21` template is 222,792 trade walks). Profiling showed the exit rules were
  only about 8% of the time and the rest was interpreter and object churn, so the walker now
  reuses one bar view instead of building one per bar, splits a setup's exits by kind once per
  walk, and skips a precedence step whose list is empty. No precedence rule changed. That gave
  1.43x on a laptop, 2.09x on a CI runner and 1.31x on the deployed function, which took the
  worst case warm call there from 24.85 s to between 16.5 s and 18.9 s (measured 2026-10-15,
  budget 25 s, function timeout 30 s). Every entry is still walked: nothing is sampled away to
  make the number look better. Spec 0009 AC-11 keeps the full record of these readings.

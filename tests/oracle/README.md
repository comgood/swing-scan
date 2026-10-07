# Oracle drafts (scope feature 6)

QA's drafts of the backtest correctness oracles, for you to recompute and approve. Agents never write to `tests/oracle/` (the pre-commit oracle guard and `AGENTS.md`), so the drafts wait here until you move them across.

They were written from doc 01 §6.4 and §6.8, doc 02 §6 and §7, and spec 0002 only, never from engine code (the simulator isn't built yet). They call only the public surface: `engine.api.backtest`, `engine.contracts` and `engine.data.fixtures`.

## What is here

| ID | Test | Fixture | Checks |
|---|---|---|---|
| B-1 | `test_exits.py::test_b1_…` | `fixtures/b01_stop_pct.csv` | % stop fills at `min(open, stop) × 0.999`, P&L to 1e-9 |
| B-2 | `test_exits.py::test_b2_…` | `fixtures/b02_gap_stop.csv` | a gap below the stop fills at the open |
| B-3 | `test_exits.py::test_b3_…` | `fixtures/b03_stop_atr.csv` | ATR stop = fill − k × ATR(14) at the signal bar (ATR exactly 2.0) |
| B-4 | `test_exits.py::test_b4_…` | `fixtures/b04_target.csv` | intraday target, gap target, and the stop beating the target on the same bar |
| B-5 | `test_exits.py::test_b5_…` | `fixtures/b05_trail_pct.csv` | trailing level from the prior highs 10, 12, 11, rising only, exit at 10.8 × 0.999 |
| B-6 | `test_exits.py::test_b6_…` | `fixtures/b06_close_below_ma.csv` | close below SMA(21) exits at the next open |
| B-7 | `test_exits.py::test_b7_…` | `fixtures/b07_time.csv` | time N = 3 exits at close(entry bar + 2) |
| B-8 | `test_exits.py::test_b8_…` | `fixtures/b08_delisting.csv` | a delisting exits at the last close, reason `delisted` |
| B-9 | `test_mae_mfe.py` | `fixtures/b09_mae_mfe.csv` | MAE and MFE in % and R for a gap stop, intraday stop, intraday target and time exit, with the exit bar capped |
| B-10 | `test_look_ahead.py` | seeded random walk, built in `_oracle.py` | garbage after T = bar 400 changes nothing up to T: both templates, all six exits, both loops, the random baseline |
| B-14 | `test_entry_signals.py::test_b14_…` | built in the test | the first valid bar is not an edge; false then true is; a listing day is never an edge |
| B-15 | `test_entry_signals.py::test_b15_…` | built in the test | no entry on a ticker's last bar (delisting or end of data), in both modes |
| B-16 | `test_entry_signals.py::test_b16_…` | built in the test | edges at 100, 105 and 112 give signals at 100 and 112 only, in every exit config |
| X-9 | `test_horizon.py` | built in the test | a trailing trade still open after 60 bars exits at close(bar 60), reason `horizon`, and only that config gets the warning |
| parity | `test_loop_parity.py` | `fixtures/b01_stop_pct.csv` | one trade exits identically in the portfolio and trade loops (doc 02 §7.3) |

Every CSV carries its arithmetic in `#` comments, and each test writes its expected values as arithmetic on fixture prices, so you can recompute without running anything.

## What QA already checked

- **Fixtures load and requests validate:** all 25 engine oracles fail only with `NotYetImplemented: backtest`, the stub's error, and the poison check in B-10 passes. Run `uv run pytest tests/oracle_drafts -q` to see it.
- **Entry signals:** QA's golden reference (`tests/golden/reference.py`) finds exactly the signal bars these tests expect in every fixture: bars 3, 20, 25 and 261, signals at 100 and 112 only, and nothing on a listing day or a last bar.
- **B-10 isn't vacuous:** on its random walk the golden reference finds 12 breakout and 417 pullback signals before T.
- **Exits:** a scratch replay of doc 02 §7.2 on each exit fixture gives the same exit bar, price and reason as the tests, so no earlier bar triggers an exit by accident.
- **Lint and types:** Ruff and `mypy --strict` are clean.

## Readings to confirm while you recompute

Each one is how QA read the docs. If you read it differently, change the test and say so, and it becomes a ruling in `docs/qa/ac-questions.md`.

1. **`bars_held` counts the entry bar as bar 1** (doc 01's time exit rule), so a time exit after N bars has `bars_held = N`.
2. **R:**
   - `r_multiple = (exit_price − entry_price) / R`, using the slipped exit fill.
   - `mae_r` and `mfe_r` divide the raw low or high minus the entry fill by R.
   - `R = entry fill − initial stop` (spec 0002).
3. **B-5 trailing start:** doc 02's example assumes a fill of exactly 10, giving levels 9.0 then 10.8. With 10 bps slippage the fill is 10.01, so the entry bar level is 9.009. On bar 2 the candidate 10 × 0.9 = 9.0 is lower, and the level only rises, so it stays at 9.009. The fixture keeps bar 2's low (9.05) above both, so the test doesn't depend on that detail.
4. **B-6 numbers:** the fixture's SMA(21) at the exit signal is 212 / 21 ≈ 10.095, not the 9.952 in QA's matrix row. The rule tested is the same.
5. **B-9 uses 4 trades** (doc 02 §7.6), one more than doc 01's 3. It adds the gap stop.
6. **B-10 uses a seeded random walk,** because feature 7's synthetic generator has no frozen entry point yet. It backtests to T with `sim.end` and compares the whole response. Swap in the generator once feature 7 lands.
7. **B-14 listing day uses `close > 5`,** since the breakout rule can't be valid on a listing day at all.
8. **X-9 warning:** QA reads `horizon_exits_over_10pct` as computed from each config's strategy trades, not the random baseline's.

## How to approve and promote

1. Recompute the values in each CSV comment and test. Edit anything you disagree with.
2. Move the folder and commit as the owner:
   ```bash
   git mv tests/oracle_drafts tests/oracle
   ORACLE_EDIT_OK=1 git commit -m "test(oracle): approve backtest correctness oracles"
   ```
   The imports are relative, so nothing else changes. Keep this README or delete it.
3. Add the `oracle-approved` label to the PR. CI rejects changes under `tests/oracle/` without it.
4. Hand two DI chores to that lane, since root files belong to it:
   - make `make test-oracle` run `uv run pytest tests/oracle -x`;
   - add the oracle first CI job.

   The oracles fail until feature 9 builds the simulator. So keep `tests/oracle` out of the default `testpaths` until then, or the whole suite goes red. The BE lane runs `make test-oracle` as its target.

Merging the approved oracles opens gate G1 in the scope. G1 unblocks the engine work in features 9 and 11.

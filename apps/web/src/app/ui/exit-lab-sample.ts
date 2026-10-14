// Invented exit lab results for the /ui gallery (spec 0009 FE task 4). Never the API mocks,
// never real prices. Kept beside sample.ts so the exit lab's data stays in one place.
import type { Schemas } from "@swing-scan/api-client";

type TradeMetrics = Schemas["TradeMetrics"];
type TradeLabResult = Schemas["TradeLabResult"];

/** One invented segment: `e` is the expectancy in %, `r` the R value (null without a stop). */
function segment(n: number, e: number, r: number | null, horizon = 0): TradeMetrics {
  return {
    n_trades: n,
    distinct_weeks: Math.round(n * 0.7),
    win_rate_pct: 50 + e * 4,
    avg_win_pct: 5 + e,
    avg_loss_pct: -4.5 + e / 2,
    expectancy_pct: e,
    expectancy_r: r,
    expectancy_per_bar_pct: e / 20,
    profit_factor: 1 + e / 3,
    avg_bars_held: 20 + horizon,
    avg_mae_pct: -5 + e / 4,
    avg_mfe_pct: 7 + e,
    horizon_exit_pct: horizon,
  };
}

function row(name: string, is: number, oos: number, stop: boolean, horizon = 0) {
  const r = (e: number) => (stop ? e / 8 : null);
  const strategy = { is: segment(40, is, r(is), horizon), oos: segment(16, oos, r(oos), horizon) };
  const random = { is: segment(40, is - 1, r(is - 1)), oos: segment(16, oos - 0.5, r(oos - 0.5)) };
  const edge = (s: TradeMetrics, x: TradeMetrics) => ({
    expectancy_pct: (s.expectancy_pct ?? 0) - (x.expectancy_pct ?? 0),
    expectancy_r:
      s.expectancy_r === null || x.expectancy_r === null ? null : s.expectancy_r - x.expectancy_r,
    expectancy_per_bar_pct: (s.expectancy_per_bar_pct ?? 0) - (x.expectancy_per_bar_pct ?? 0),
    win_rate_pct: (s.win_rate_pct ?? 0) - (x.win_rate_pct ?? 0),
  });
  return {
    name,
    strategy,
    random,
    edge: { is: edge(strategy.is, random.is), oos: edge(strategy.oos, random.oos) },
  };
}

const CONFIGS: Schemas["ExitConfig"][] = [
  {
    name: "Demo stop",
    exits: [
      { type: "stop_pct", pct: 6 },
      { type: "time", bars: 15 },
    ],
  },
  { name: "Demo MA, no stop", exits: [{ type: "close_below_ma", ma: "sma", n: 50 }] },
  {
    name: "Demo far target",
    exits: [
      { type: "target", pct: 40 },
      { type: "trail_pct", pct: 12 },
    ],
  },
];

export const SAMPLE_TRADE_LAB: TradeLabResult = {
  mode: "trade",
  assumptions: {
    fill_model: "signal_close_entry_next_open",
    slippage_bps: 10,
    commission_bps: 0,
    sizing: "unit_notional",
    max_positions: null,
    entry_rising_edge: true,
    cooldown_bars: 10,
    cooldown_basis: "signal",
    no_last_bar_entry: true,
    same_ticker_overlap: true,
    horizon_bars: 60,
    seed: 7,
    configs: CONFIGS,
    baseline_config_index: 0,
    delisting_rule: "exit_last_close",
    oos_start: "2024-01-02",
    oos_fraction: 0.3,
    data_mode: "synthetic",
    data_version: "synthetic:v1:demo",
    data_seed: 7,
  },
  oos_start: "2024-01-02",
  trial: {
    structure_key: "2".repeat(64),
    pair_keys: ["gallery-lab-1", "gallery-lab-2", "gallery-lab-3"],
  },
  warnings: [
    {
      code: "horizon_exits_over_10pct",
      config_index: 2,
      message:
        "Demo far target: more than 10% of trades hit the 60 bar horizon, so its results are cut short.",
    },
  ],
  entries: {
    count: 56,
    is_count: 40,
    oos_count: 16,
    distinct_weeks: 39,
    hash: "3".repeat(64),
    random_is_count: 40,
    random_oos_count: 16,
  },
  rows: [
    row("Demo stop", 0.6, 1.2, true),
    row("Demo MA, no stop", 1.1, -0.4, false),
    row("Demo far target", 0.9, 2.1, true, 14),
  ],
  best_is: {
    win_rate_pct: 1,
    avg_win_pct: 1,
    avg_loss_pct: 1,
    expectancy_pct: 1,
    expectancy_r: 2,
    expectancy_per_bar_pct: 1,
    profit_factor: 1,
    avg_mae_pct: 1,
    avg_mfe_pct: 1,
    horizon_exit_pct: 0,
  },
  guides_is: { winner_mae_p75_pct: -2.1, winner_mae_p90_pct: -3.4, mfe_median_pct: 6.4 },
  baseline_trades: [],
  baseline_trades_total: 0,
  baseline_trades_truncated: false,
};

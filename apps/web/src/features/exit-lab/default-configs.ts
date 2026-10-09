// The five exit configs the exit lab opens with (spec 0009 assumed decision 10): the configs of
// `contracts/mocks/backtest.trade_lab.json`, the demo script's "5 default configs". Config 0 is
// the baseline (its IS trades feed the guide row).
import type { ExitConfig } from "@swing-scan/api-client";

export const DEFAULT_CONFIGS: readonly ExitConfig[] = [
  {
    name: "Baseline",
    exits: [
      { type: "stop_pct", pct: 8 },
      { type: "time", bars: 20 },
    ],
  },
  {
    name: "ATR stop and target",
    exits: [
      { type: "stop_atr", k: 2, n: 14 },
      { type: "target", pct: 15 },
      { type: "time", bars: 30 },
    ],
  },
  {
    name: "MA exit, no stop",
    exits: [{ type: "close_below_ma", ma: "ema", n: 21 }],
  },
  {
    name: "Trailing 10%",
    exits: [
      { type: "trail_pct", pct: 10 },
      { type: "time", bars: 40 },
    ],
  },
  {
    name: "Wide target, no stop",
    exits: [{ type: "target", pct: 60 }],
  },
];

// Invented sample data for the /ui gallery. Never the API mocks, never real prices.
import type { IndicatorSpec, Rule } from "@swing-scan/api-client";

import type { TrialCountState } from "@/features/honesty";

export interface SampleRow {
  id: string;
  ticker: string;
  setup: string;
  return_pct: number | null;
  win_rate_pct: number | null;
  expectancy_r: number | null;
  trades: number;
  best: boolean;
}

export const SAMPLE_ROWS: SampleRow[] = [
  {
    id: "1",
    ticker: "ALPHA",
    setup: "Breakout",
    return_pct: 12.4,
    win_rate_pct: 54.2,
    expectancy_r: 0.41,
    trades: 48,
    best: true,
  },
  {
    id: "2",
    ticker: "BRAVO",
    setup: "Pullback",
    return_pct: -3.1,
    win_rate_pct: 41.0,
    expectancy_r: -0.12,
    trades: 39,
    best: false,
  },
  {
    id: "3",
    ticker: "CHARL",
    setup: "Breakout",
    return_pct: null,
    win_rate_pct: null,
    expectancy_r: null,
    trades: 0,
    best: false,
  },
  {
    id: "4",
    ticker: "DELTA",
    setup: "Pullback",
    return_pct: 0.001,
    win_rate_pct: 50.0,
    expectancy_r: 0.0,
    trades: 22,
    best: false,
  },
  {
    id: "5",
    ticker: "ECHO",
    setup: "Breakout",
    return_pct: 7.85,
    win_rate_pct: 61.5,
    expectancy_r: 0.33,
    trades: 26,
    best: false,
  },
  {
    id: "6",
    ticker: "FOXT",
    setup: "Pullback",
    return_pct: 1234.5,
    win_rate_pct: 47.3,
    expectancy_r: 1.32,
    trades: 112,
    best: false,
  },
];

/** Enough rows to show pagination at a page size of 5. */
export const MANY_ROWS: SampleRow[] = Array.from({ length: 13 }, (_, i) => ({
  id: `m${i}`,
  ticker: `T${String(i + 1).padStart(3, "0")}`,
  setup: i % 2 === 0 ? "Breakout" : "Pullback",
  return_pct: i % 5 === 0 ? null : ((i * 37) % 23) - 9.5,
  win_rate_pct: 40 + ((i * 7) % 25),
  expectancy_r: ((i * 13) % 9) / 10 - 0.3,
  trades: 10 + i * 3,
  best: false,
}));

/** Twelve columns, to show a wide table scrolling inside its own box at 375 px. */
export const WIDE_COLUMNS = [
  "ticker",
  "entry_date",
  "entry_price",
  "exit_date",
  "exit_price",
  "return_pct",
  "r_multiple",
  "mae_pct",
  "mfe_pct",
  "bars_held",
  "exit_reason",
  "in_sample",
] as const;

export type WideRow = Record<(typeof WIDE_COLUMNS)[number], string | number | null> & {
  id: string;
};

export const WIDE_ROWS: WideRow[] = [
  {
    id: "w1",
    ticker: "ALPHA",
    entry_date: "2023-03-14",
    entry_price: 101.2,
    exit_date: "2023-03-28",
    exit_price: 108.9,
    return_pct: 7.61,
    r_multiple: 1.52,
    mae_pct: -1.8,
    mfe_pct: 9.4,
    bars_held: 10,
    exit_reason: "target",
    in_sample: "IS",
  },
  {
    id: "w2",
    ticker: "BRAVO",
    entry_date: "2023-05-02",
    entry_price: 54.1,
    exit_date: "2023-05-09",
    exit_price: 51.4,
    return_pct: -4.99,
    r_multiple: -1.0,
    mae_pct: -5.2,
    mfe_pct: 1.1,
    bars_held: 5,
    exit_reason: "stop",
    in_sample: "IS",
  },
  {
    id: "w3",
    ticker: "ECHO",
    entry_date: "2024-01-22",
    entry_price: 2310.0,
    exit_date: null,
    exit_price: null,
    return_pct: null,
    r_multiple: null,
    mae_pct: -0.4,
    mfe_pct: 2.2,
    bars_held: 3,
    exit_reason: "open",
    in_sample: "OOS",
  },
];

/** A FastAPI 422 body shaped like spec 0002's errors, for the field error demo. */
export const SAMPLE_422 = {
  detail: [
    {
      type: "out_of_range",
      loc: ["body", "lookback"],
      msg: "must be between 2 and 260",
      input: 999,
      ctx: { min: 2, max: 260 },
    },
    {
      type: "value_error",
      loc: ["body"],
      msg: "rule needs at least one condition",
      input: null,
      ctx: {},
    },
  ],
};

/** Trial counter states for the honesty section (U-4, spec 0004). Invented counts. */
export const SAMPLE_TRIAL_STATES: { label: string; state: TrialCountState }[] = [
  {
    label: "First trial",
    state: { status: "counted", count: { trialNumber: 1, sessionTotal: 1 } },
  },
  { label: "Counting", state: { status: "counted", count: { trialNumber: 6, sessionTotal: 14 } } },
  {
    label: "Warning at 10",
    state: { status: "counted", count: { trialNumber: 10, sessionTotal: 23 } },
  },
  { label: "Storage unavailable", state: { status: "unavailable" } },
];

/** An invented structure key for the live demo; real keys come from the backtest response. */
export const SAMPLE_STRUCTURE_KEY = "0".repeat(64);

/** A short indicator catalog for the rule builder states (spec 0008); the app reads the API's. */
export const SAMPLE_CATALOG: IndicatorSpec[] = [
  { name: "close", label: "Close", windowed: false, n_min: null, n_max: null, n_default: null },
  { name: "volume", label: "Volume", windowed: false, n_min: null, n_max: null, n_default: null },
  {
    name: "sma",
    label: "Simple moving average",
    windowed: true,
    n_min: 2,
    n_max: 252,
    n_default: null,
  },
  {
    name: "ema",
    label: "Exponential moving average",
    windowed: true,
    n_min: 2,
    n_max: 252,
    n_default: null,
  },
  {
    name: "rsi",
    label: "Relative strength index",
    windowed: true,
    n_min: 2,
    n_max: 50,
    n_default: null,
  },
];

/** An invented two row rule: a number right side, then an indicator right side. */
export const SAMPLE_RULE: Rule = {
  name: "Sample cross",
  conditions: [
    {
      left: { kind: "ind", ind: "close", n: null, offset: 0, mult: 1 },
      op: ">",
      right: { kind: "value", value: 5 },
    },
    {
      left: { kind: "ind", ind: "ema", n: 21, offset: 0, mult: 1 },
      op: "crosses_above",
      right: { kind: "ind", ind: "sma", n: 300, offset: 0, mult: 1 },
    },
  ],
};

/** A 422 on the sample rule's second row, right side `n`. */
export const SAMPLE_BUILDER_422 = {
  detail: [
    {
      type: "out_of_range",
      loc: ["body", "rule", "conditions", 1, "right", "n"],
      msg: "must be between 2 and 252",
      input: 300,
      ctx: { min: 2, max: 252 },
    },
  ],
};

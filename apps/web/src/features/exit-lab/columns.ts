// The exit lab's columns (spec 0009 AC-13, AC-16): every per trade metric as an IS | OOS pair,
// then the "Edge vs random" group. `ranked` metrics are the ones `best_is` can name; the ranking
// itself comes from the API (spec 0002), never from this file.
import type { ExitConfig, Schemas } from "@swing-scan/api-client";

export type TradeMetrics = Schemas["TradeMetrics"];
export type EdgeMetrics = Schemas["EdgeMetrics"];
export type RankedKey = keyof Schemas["BestIs"];

/** How a value is shown. `r` cells of a config without a stop carry the footnote mark. */
export type ValueKind = "int" | "rate" | "signed_pct" | "per_bar" | "r" | "number" | "bars" | "pts";

export interface MetricColumn {
  key: keyof TradeMetrics;
  label: string;
  kind: ValueKind;
  /** Only ranked metrics can carry the best IS highlight. */
  ranked: boolean;
  /** The one plain line beside the term, word for word from doc 01 section 6.8. */
  hint?: string;
}

export interface EdgeColumn {
  key: keyof EdgeMetrics;
  label: string;
  kind: ValueKind;
  hint?: string;
}

/** Shared between a metric column and its edge column, so the reader meets one wording. */
const EXPECTANCY_PCT = "What one average trade made or lost, in percent.";
const EXPECTANCY_R =
  "The same, counted in multiples of the risk you took (R = the distance to your stop).";
const EXPECTANCY_PER_BAR =
  "Expectancy divided by how long the trade was held, so quick trades and slow ones compare.";
const WIN_RATE = "The share of trades that ended in profit.";

export const METRIC_COLUMNS: MetricColumn[] = [
  { key: "n_trades", label: "Trades", kind: "int", ranked: false },
  {
    key: "distinct_weeks",
    label: "Distinct entry weeks",
    kind: "int",
    ranked: false,
    hint: "How many separate weeks the trades started in. A high count means the result is not one lucky week.",
  },
  { key: "win_rate_pct", label: "Win rate", kind: "rate", ranked: true, hint: WIN_RATE },
  { key: "avg_win_pct", label: "Average win", kind: "signed_pct", ranked: true },
  { key: "avg_loss_pct", label: "Average loss", kind: "signed_pct", ranked: true },
  {
    key: "expectancy_pct",
    label: "Expectancy (%)",
    kind: "signed_pct",
    ranked: true,
    hint: EXPECTANCY_PCT,
  },
  { key: "expectancy_r", label: "Expectancy (R)", kind: "r", ranked: true, hint: EXPECTANCY_R },
  {
    key: "expectancy_per_bar_pct",
    label: "Expectancy per bar",
    kind: "per_bar",
    ranked: true,
    hint: EXPECTANCY_PER_BAR,
  },
  {
    key: "profit_factor",
    label: "Profit factor",
    kind: "number",
    ranked: true,
    hint: "Everything the winners made divided by everything the losers lost. Above 1 is a profit.",
  },
  { key: "avg_bars_held", label: "Average bars held", kind: "bars", ranked: false },
  {
    key: "avg_mae_pct",
    label: "Average MAE",
    kind: "signed_pct",
    ranked: true,
    hint: "MAE is the deepest a trade went against you before it closed.",
  },
  {
    key: "avg_mfe_pct",
    label: "Average MFE",
    kind: "signed_pct",
    ranked: true,
    hint: "MFE is the furthest a trade went in your favour before it closed.",
  },
  {
    key: "horizon_exit_pct",
    label: "Exited by horizon",
    kind: "rate",
    ranked: true,
    hint: "The share of trades still open at the horizon, which were closed at that bar's close rather than by a real exit.",
  },
];

export const EDGE_COLUMNS: EdgeColumn[] = [
  { key: "expectancy_pct", label: "Expectancy (%)", kind: "signed_pct", hint: EXPECTANCY_PCT },
  { key: "expectancy_r", label: "Expectancy (R)", kind: "r", hint: EXPECTANCY_R },
  {
    key: "expectancy_per_bar_pct",
    label: "Expectancy per bar",
    kind: "per_bar",
    hint: EXPECTANCY_PER_BAR,
  },
  {
    key: "win_rate_pct",
    label: "Win rate (pts)",
    kind: "pts",
    hint: `${WIN_RATE} The edge in it is a difference in percentage points.`,
  },
];

const STOP_TYPES: ReadonlySet<string> = new Set(["stop_pct", "stop_atr", "trail_pct"]);

/** R needs a stop: a config with no `stop_pct`, `stop_atr` or `trail_pct` has no R (X-4). */
export function hasStop(config: ExitConfig | undefined): boolean {
  return config?.exits.some((exit) => STOP_TYPES.has(exit.type)) ?? false;
}

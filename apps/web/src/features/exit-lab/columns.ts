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
}

export interface EdgeColumn {
  key: keyof EdgeMetrics;
  label: string;
  kind: ValueKind;
}

export const METRIC_COLUMNS: MetricColumn[] = [
  { key: "n_trades", label: "Trades", kind: "int", ranked: false },
  { key: "distinct_weeks", label: "Distinct entry weeks", kind: "int", ranked: false },
  { key: "win_rate_pct", label: "Win rate", kind: "rate", ranked: true },
  { key: "avg_win_pct", label: "Average win", kind: "signed_pct", ranked: true },
  { key: "avg_loss_pct", label: "Average loss", kind: "signed_pct", ranked: true },
  { key: "expectancy_pct", label: "Expectancy (%)", kind: "signed_pct", ranked: true },
  { key: "expectancy_r", label: "Expectancy (R)", kind: "r", ranked: true },
  { key: "expectancy_per_bar_pct", label: "Expectancy per bar", kind: "per_bar", ranked: true },
  { key: "profit_factor", label: "Profit factor", kind: "number", ranked: true },
  { key: "avg_bars_held", label: "Average bars held", kind: "bars", ranked: false },
  { key: "avg_mae_pct", label: "Average MAE", kind: "signed_pct", ranked: true },
  { key: "avg_mfe_pct", label: "Average MFE", kind: "signed_pct", ranked: true },
  { key: "horizon_exit_pct", label: "Exited by horizon", kind: "rate", ranked: true },
];

export const EDGE_COLUMNS: EdgeColumn[] = [
  { key: "expectancy_pct", label: "Expectancy (%)", kind: "signed_pct" },
  { key: "expectancy_r", label: "Expectancy (R)", kind: "r" },
  { key: "expectancy_per_bar_pct", label: "Expectancy per bar", kind: "per_bar" },
  { key: "win_rate_pct", label: "Win rate (pts)", kind: "pts" },
];

const STOP_TYPES: ReadonlySet<string> = new Set(["stop_pct", "stop_atr", "trail_pct"]);

/** R needs a stop: a config with no `stop_pct`, `stop_atr` or `trail_pct` has no R (X-4). */
export function hasStop(config: ExitConfig | undefined): boolean {
  return config?.exits.some((exit) => STOP_TYPES.has(exit.type)) ?? false;
}

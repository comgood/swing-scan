// Every `Assumptions` field in plain words (spec 0007 AC-12, U-3). One entry per field: the
// `satisfies` below fails the typecheck when the contract adds a field this map lacks.
import type { ExitConfig, Schemas } from "@swing-scan/api-client";

import { formatDate, formatInt, formatNumber } from "@/lib/format";

type Assumptions = Schemas["Assumptions"];
type Exit = ExitConfig["exits"][number];

export const NOT_USED = "not used in portfolio mode";
export const NOT_USED_TRADE = "not used in trade mode";

interface AssumptionLabel<K extends keyof Assumptions> {
  label: string;
  text: (value: NonNullable<Assumptions[K]>) => string;
}

export function exitText(exit: Exit): string {
  switch (exit.type) {
    case "stop_pct":
      return `stop ${formatNumber(exit.pct)}% below entry`;
    case "stop_atr":
      return `stop ${formatNumber(exit.k)} × ATR(${formatInt(exit.n)}) below entry`;
    case "target":
      return `target ${formatNumber(exit.pct)}% above entry`;
    case "trail_pct":
      return `trailing stop ${formatNumber(exit.pct)}% below the high`;
    case "close_below_ma":
      return `exit at the next open after a close below ${exit.ma.toUpperCase()}(${formatInt(exit.n)})`;
    case "time":
      return `exit at the close of bar ${formatInt(exit.bars)}`;
  }
}

function configText(config: ExitConfig): string {
  const exits = config.exits.length ? config.exits.map(exitText).join(", ") : "no exits";
  return `${config.name}: ${exits}`;
}

export const ASSUMPTION_LABELS = {
  fill_model: {
    label: "Fill model",
    text: () => "signal at the close, entry at the next open",
  },
  slippage_bps: {
    label: "Slippage",
    text: (v) => `${formatNumber(v, { decimals: 0 })} bps per side`,
  },
  commission_bps: {
    label: "Commission",
    text: (v) => `${formatNumber(v, { decimals: 0 })} bps`,
  },
  sizing: {
    label: "Sizing",
    text: (v) =>
      v === "equal_weight"
        ? "equal weight: equity ÷ max positions at the signal close, capped by cash"
        : "one unit of notional per trade",
  },
  max_positions: { label: "Max positions", text: (v) => formatInt(v) },
  entry_rising_edge: {
    label: "Entry",
    text: () => "only when the rule turns true (rising edge)",
  },
  cooldown_bars: { label: "Cooldown", text: (v) => `${formatInt(v)} bars` },
  cooldown_basis: { label: "Cooldown counts from", text: () => "each accepted signal" },
  no_last_bar_entry: {
    label: "Last bar entry",
    text: () => "none: a signal on the last bar is never entered",
  },
  same_ticker_overlap: {
    label: "Overlapping trades in one ticker",
    text: (v) => (v ? "yes: same ticker trades may overlap" : "no"),
  },
  horizon_bars: {
    label: "Horizon",
    text: (v) =>
      `${formatInt(v)} bars: a trade still open on bar ${formatInt(v)} exits at its close`,
  },
  seed: { label: "Random seed", text: (v) => String(v) },
  configs: {
    label: "Exit rules",
    text: (v) => v.map(configText).join("; "),
  },
  baseline_config_index: {
    label: "Baseline config",
    text: (v) => `config ${formatInt(v + 1)}`,
  },
  delisting_rule: {
    label: "Delisting",
    text: () => "exit at the last close before delisting",
  },
  oos_start: { label: "Out of sample from", text: (v) => formatDate(v) },
  oos_fraction: {
    label: "Out of sample share",
    text: (v) => `last ${formatNumber(v * 100, { decimals: 0 })}% of sessions`,
  },
  data_mode: { label: "Data mode", text: (v) => v },
  data_version: { label: "Data version", text: (v) => v },
  data_seed: { label: "Data seed", text: (v) => String(v) },
} satisfies { [K in keyof Assumptions]: AssumptionLabel<K> };

export interface AssumptionLine {
  key: keyof Assumptions;
  label: string;
  text: string;
}

/** The header's lines in map order; a null field reads "not used in <mode> mode" (AC-12, AC-19). */
export function assumptionLines(
  assumptions: Assumptions,
  mode: "portfolio" | "trade" = "portfolio",
): AssumptionLine[] {
  const notUsed = mode === "trade" ? NOT_USED_TRADE : NOT_USED;
  return (Object.keys(ASSUMPTION_LABELS) as (keyof Assumptions)[]).map((key) => {
    const entry = ASSUMPTION_LABELS[key] as AssumptionLabel<typeof key>;
    const value = assumptions[key];
    const text = value === null || value === undefined ? notUsed : entry.text(value as never);
    return { key, label: entry.label, text };
  });
}

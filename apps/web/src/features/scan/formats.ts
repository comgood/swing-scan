// How each scan value is written, by indicator kind (spec 0005 number formats). The kind comes
// from the rule's operand, never from the column label; `mult` keeps its indicator's kind.
import { formatInt, formatNumber, formatPct, formatPrice } from "@/lib/format";

import type { IndOperand } from "./operands";

type Format = (value: number | null | undefined) => string;

const BY_KIND: Record<IndOperand["ind"], Format> = {
  open: formatPrice,
  high: formatPrice,
  low: formatPrice,
  close: formatPrice,
  sma: formatPrice,
  ema: formatPrice,
  highest: formatPrice,
  lowest: formatPrice,
  atr: formatPrice,
  volume: formatInt,
  avg_volume: formatInt,
  rs: formatInt,
  rsi: (v) => formatNumber(v),
  // `ret` is a fraction; the percent formatter takes percent numbers.
  ret: (v) => formatPct(typeof v === "number" ? v * 100 : v),
};

export function formatOperand(op: IndOperand | undefined, value: number | null | undefined) {
  return op ? BY_KIND[op.ind](value) : formatNumber(value);
}

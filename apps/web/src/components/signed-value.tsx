// A signed number in the gain or loss colour; the sign always carries the meaning too
// (spec 0003 AC-12).
import { formatNumber, formatPct, formatR } from "@/lib/format";
import { cn } from "@/lib/utils";

const FORMATS = {
  pct: (v: number | null | undefined) => formatPct(v),
  r: (v: number | null | undefined) => formatR(v),
  number: (v: number | null | undefined) => formatNumber(v),
};

interface SignedValueProps {
  value: number | null | undefined;
  format: keyof typeof FORMATS;
  className?: string;
}

export function SignedValue({ value, format, className }: SignedValueProps) {
  let text = FORMATS[format](value);
  // Every format rounds to 2 decimals, so a value that rounds to zero carries no sign.
  const nonZero = typeof value === "number" && Number.isFinite(value) && Math.abs(value) >= 0.005;
  if (nonZero && value > 0 && !text.startsWith("+")) text = `+${text}`;
  const tone = !nonZero ? "text-foreground" : value > 0 ? "text-positive" : "text-negative";
  return <span className={cn("tabular-nums", tone, className)}>{text}</span>;
}

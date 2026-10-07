// Number and date formatting for every value on screen (spec 0003 AC-12). Fixed en-US locale,
// so the static HTML and the browser render the same text. Missing values show `n/a`.

const LOCALE = "en-US";
export const NOT_AVAILABLE = "n/a";

type Maybe = number | null | undefined;

function isFiniteNumber(v: Maybe): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** Formats `v` to `decimals` places with separators; a value that rounds to zero has no sign. */
function fixed(v: number, decimals: number): string {
  const text = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    signDisplay: "negative",
  }).format(v);
  // signDisplay "negative" already drops the sign of -0.00; normalise the minus to ASCII.
  return text.replace("−", "-");
}

function roundsToZero(v: number, decimals: number): boolean {
  return Number(Math.abs(v).toFixed(decimals)) === 0;
}

/** `3.254` → `+3.25%`. Inputs are already percent numbers (`_pct` fields), never multiplied. */
export function formatPct(v: Maybe, { decimals = 2 }: { decimals?: number } = {}): string {
  if (!isFiniteNumber(v)) return NOT_AVAILABLE;
  if (roundsToZero(v, decimals)) return `${fixed(0, decimals)}%`;
  return `${v > 0 ? "+" : ""}${fixed(v, decimals)}%`;
}

export function formatNumber(v: Maybe, { decimals = 2 }: { decimals?: number } = {}): string {
  if (!isFiniteNumber(v)) return NOT_AVAILABLE;
  if (roundsToZero(v, decimals)) return fixed(0, decimals);
  return fixed(v, decimals);
}

/** Multiples of risk: `1.32R`, `-0.50R`. */
export function formatR(v: Maybe): string {
  if (!isFiniteNumber(v)) return NOT_AVAILABLE;
  return `${formatNumber(v, { decimals: 2 })}R`;
}

/** Prices: 2 decimals, separators, no currency symbol. */
export function formatPrice(v: Maybe): string {
  return formatNumber(v, { decimals: 2 });
}

export function formatInt(v: Maybe): string {
  if (!isFiniteNumber(v)) return NOT_AVAILABLE;
  return formatNumber(Math.round(v), { decimals: 0 });
}

/** The API sends `YYYY-MM-DD`; it is shown exactly as sent. */
export function formatDate(s: string | null | undefined): string {
  return s ? s : NOT_AVAILABLE;
}

// Compile time checks on the generated types (spec 0002 AC-1). `tsc` fails if they break.
import type { BacktestResponse, Schemas } from "./index";

type Assert<T extends true> = T;
type IsRequired<T, K extends keyof T> = object extends Pick<T, K> ? false : true;

// Discriminator tags stay required, so narrowing works.
export type KindIsRequired = Assert<IsRequired<Schemas["IndOperand"], "kind">>;
export type TypeIsRequired = Assert<IsRequired<Schemas["StopPct"], "type">>;
export type ModeIsRequired = Assert<IsRequired<Schemas["PortfolioResult"], "mode">>;

export function describe(result: BacktestResponse): string {
  switch (result.mode) {
    case "portfolio": {
      const equity: Schemas["Point"][] = result.equity;
      return `portfolio with ${equity.length} equity points`;
    }
    case "trade": {
      const rows: Schemas["ConfigRow"][] = result.rows;
      return `exit lab with ${rows.length} configs`;
    }
    default: {
      const unreachable: never = result;
      return unreachable;
    }
  }
}

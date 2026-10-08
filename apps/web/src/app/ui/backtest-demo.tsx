"use client";

// The backtest report parts for the /ui gallery (spec 0007 FE task 6), on invented data. The
// trial counter uses in memory storage, so the gallery never touches your real counts.
import { useState } from "react";

import { AssumptionsHeader, MetricsTable, TradeList } from "@/features/backtest";
import { memoryStores } from "@/features/honesty/memory-stores";

import { SAMPLE_BACKTEST, SAMPLE_TRADES } from "./sample";

export function BacktestDemo() {
  const [stores] = useState(memoryStores);
  return (
    <>
      <AssumptionsHeader result={SAMPLE_BACKTEST} stores={stores} />
      <MetricsTable result={SAMPLE_BACKTEST} />
      <div role="group" aria-labelledby="demo-trades" className="flex min-w-0 flex-col gap-2">
        <h3 id="demo-trades" className="text-sm font-medium">
          Trade list
        </h3>
        <TradeList
          trades={SAMPLE_TRADES}
          total={SAMPLE_TRADES.length}
          truncated={false}
          oosStart={SAMPLE_BACKTEST.oos_start}
        />
      </div>
      <div role="group" aria-labelledby="demo-truncated" className="flex min-w-0 flex-col gap-2">
        <h3 id="demo-truncated" className="text-sm font-medium">
          Truncated trade list
        </h3>
        <TradeList
          trades={SAMPLE_TRADES.slice(0, 12)}
          total={2600}
          truncated
          caption="Truncated trade list, sortable by any column"
          oosStart={SAMPLE_BACKTEST.oos_start}
        />
      </div>
    </>
  );
}

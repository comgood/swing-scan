import { createClient, type BacktestRequest } from "@swing-scan/api-client";
import { describe, expect, it } from "vitest";

import { backtestHandler, mocks } from "./handlers";
import { server } from "./node";

const api = () => createClient({ baseUrl: "http://api.test" });

const config = { name: "Baseline", exits: [{ type: "stop_pct" as const, pct: 8 }] };
const request = (configs: number): BacktestRequest => ({
  rule: mocks.templates[0].rule,
  configs: Array.from({ length: configs }, (_, i) => ({ ...config, name: `Config ${i + 1}` })),
  sim: {
    max_positions: 10,
    slippage_bps: 10,
    horizon_bars: 60,
    seed: 42,
    start: null,
    end: null,
  },
});

describe("POST /backtest mock", () => {
  it("answers 1 config with portfolio mode", async () => {
    const { data } = await api().POST("/api/v1/backtest", { body: request(1) });
    expect(data?.mode).toBe("portfolio");
  });

  it("answers 2 to 6 configs with the exit lab", async () => {
    const { data } = await api().POST("/api/v1/backtest", { body: request(3) });
    expect(data?.mode).toBe("trade");
  });

  it("answers 7 configs with a 422 at configs", async () => {
    const { error, response } = await api().POST("/api/v1/backtest", { body: request(7) });
    expect(response.status).toBe(422);
    const detail = error?.detail;
    if (!Array.isArray(detail)) throw new Error(`expected a 422 list, got ${String(detail)}`);
    expect(detail[0]?.loc).toEqual(["body", "configs"]);
  });

  it("can switch to the truncated and no entries results", async () => {
    server.use(backtestHandler("truncated"));
    const truncated = await api().POST("/api/v1/backtest", { body: request(1) });
    expect(truncated.data?.mode === "portfolio" && truncated.data.trades_truncated).toBe(true);

    server.use(backtestHandler("no_entries"));
    const empty = await api().POST("/api/v1/backtest", { body: request(1) });
    expect(empty.data?.warnings.map((w) => w.code)).toEqual(["no_entries"]);
  });
});

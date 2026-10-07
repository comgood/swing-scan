// The remaining MSW handlers: static GETs, explicit backtest errors, and the infinite delay
// that holds a loading state (spec 0002 AC-13, U-5, U-7).
import { createClient } from "@swing-scan/api-client";
import { describe, expect, it } from "vitest";

import { backtestHandler, mocks, scanHandler } from "./handlers";
import { server } from "./node";

const api = () => createClient({ baseUrl: "http://api.test" });

describe("static GET handlers", () => {
  it("serves the meta mock with the contract version", async () => {
    const { data } = await api().GET("/api/v1/meta");
    expect(data?.contract_version).toBe("1.0.0");
  });

  it("serves all 14 indicators", async () => {
    const { data } = await api().GET("/api/v1/indicators");
    expect(data).toHaveLength(14);
  });

  it("serves both templates", async () => {
    const { data } = await api().GET("/api/v1/templates");
    expect(data?.map((t) => t.id)).toEqual(["breakout_52w", "pullback_ema21"]);
  });
});

describe("error variants", () => {
  it("serves a backtest 422 whose loc points at the duplicate exit", async () => {
    server.use(backtestHandler("422.exits.duplicate_type"));

    const { error, response } = await api().POST("/api/v1/backtest", {
      body: { rule: mocks.templates[0].rule, configs: [] },
    });

    expect(response.status).toBe(422);
    const detail = error?.detail;
    if (!Array.isArray(detail)) throw new Error("expected a 422 list");
    expect(detail[0]?.type).toBe("duplicate_exit_type");
    expect(detail[0]?.loc.at(-1)).toBe("type");
  });

  it("serves the 501 body while the scan engine is not built", async () => {
    server.use(scanHandler("501.scan"));

    const { error, response } = await api().POST("/api/v1/scan", {
      body: { rule: mocks.templates[0].rule, as_of: null },
    });

    expect(response.status).toBe(501);
    expect(error?.detail).toMatch(/feature 8/);
  });

  it("can hold a request forever to show a loading state", async () => {
    server.use(scanHandler("ok", { delayMs: "infinite" }));
    const controller = new AbortController();

    const pending = api().POST("/api/v1/scan", {
      body: { rule: mocks.templates[0].rule, as_of: null },
      signal: controller.signal,
    });
    const settled = await Promise.race([
      pending.then(() => "settled"),
      new Promise((resolve) => setTimeout(() => resolve("still pending"), 100)),
    ]);
    controller.abort();
    await pending.catch(() => undefined);

    expect(settled).toBe("still pending");
  });
});

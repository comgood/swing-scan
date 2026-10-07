import { createClient, type ScanRequest, type ScanResponse } from "@swing-scan/api-client";
import { describe, expect, expectTypeOf, it } from "vitest";

import { mocks, scanHandler } from "./handlers";
import { server } from "./node";

const request: ScanRequest = { rule: mocks.templates[0].rule, as_of: null };

// Created per test: openapi-fetch keeps the fetch it sees at creation, and MSW patches it
// in beforeAll.
const api = () => createClient({ baseUrl: "http://api.test" });

describe("POST /scan through MSW and the generated client", () => {
  it("returns the typed scan mock", async () => {
    const { data, error, response } = await api().POST("/api/v1/scan", { body: request });

    expect(response.status).toBe(200);
    expect(error).toBeUndefined();
    expectTypeOf(data).toEqualTypeOf<ScanResponse | undefined>();
    expect(data?.columns).toEqual(["close", "highest(252)[1]", "volume", "1.5×avg_volume(50)"]);
    expect(data?.rows.length).toBeGreaterThan(0);
    expect(data?.rows.every((row) => row.operands.length === data.columns.length)).toBe(true);
  });

  it("can switch to a 422 mock whose loc points at the bad field", async () => {
    server.use(scanHandler("422.rule.n_out_of_range"));

    const { data, error, response } = await api().POST("/api/v1/scan", { body: request });

    expect(response.status).toBe(422);
    expect(data).toBeUndefined();
    const detail = error?.detail;
    // The error body is a 422 list here; a 501 would carry a string.
    if (!Array.isArray(detail)) throw new Error(`expected a 422 list, got ${String(detail)}`);
    const issue = detail[0];
    expect(issue?.type).toBe("out_of_range");
    expect(issue?.loc.at(-1)).toBe("n");
    expect(issue?.ctx).toEqual({ min: 2, max: 50 });
  });

  it("can switch to the empty result", async () => {
    server.use(scanHandler("empty"));

    const { data } = await api().POST("/api/v1/scan", { body: request });

    expect(data?.rows).toEqual([]);
  });

  it("can delay a response to hold a loading state", async () => {
    server.use(scanHandler("ok", { delayMs: 60 }));

    const started = performance.now();
    await api().POST("/api/v1/scan", { body: request });

    expect(performance.now() - started).toBeGreaterThanOrEqual(50);
  });
});

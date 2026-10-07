import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api-error";
import { server } from "@/mocks/node";

import { ApiStatus } from "./api-status";
import { HEALTH_TIMEOUT_MS, isLive, useHealth } from "./use-health";

function wrapper() {
  const client = new QueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function countHealthRequests(respond: () => Response) {
  const counter = { calls: 0 };
  server.use(
    http.get("*/api/v1/health", () => {
      counter.calls += 1;
      return respond();
    }),
  );
  return counter;
}

afterEach(() => vi.restoreAllMocks());

// covers: AC-4 (one health query, 10 s timeout, retry 1, staleTime Infinity, exactly "live")
describe("isLive (AC-4)", () => {
  it.each([
    [{ data_mode: "live" }, true],
    [{ data_mode: "synthetic" }, false],
    [{ data_mode: "LIVE" }, false],
    [{ data_mode: " live" }, false],
    [{}, false],
    [undefined, false],
  ])("treats %j as live: %s", (health, expected) => {
    expect(isLive(health)).toBe(expected);
  });
});

describe("useHealth (AC-4)", () => {
  it("returns the health body from GET /api/v1/health", async () => {
    const { result } = renderHook(() => useHealth(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ status: "ok", data_mode: "synthetic", version: "0.1.0" });
  });

  it("retries a failed ping exactly once, then reports a network error", async () => {
    const counter = countHealthRequests(() => HttpResponse.error());
    const { result } = renderHook(() => useHealth(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 5000 });
    expect(counter.calls).toBe(2);
    expect(result.current.error).toBeInstanceOf(ApiRequestError);
    expect((result.current.error as ApiRequestError).apiError).toEqual({ kind: "network" });
  });

  it("gives up after the 10 s timeout and reports it as a timeout", async () => {
    const timeout = vi
      .spyOn(AbortSignal, "timeout")
      .mockImplementation(() => AbortSignal.abort(new DOMException("timed out", "TimeoutError")));
    const { result } = renderHook(() => useHealth(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 5000 });
    expect(timeout).toHaveBeenCalledWith(HEALTH_TIMEOUT_MS);
    expect(HEALTH_TIMEOUT_MS).toBe(10_000);
    expect((result.current.error as ApiRequestError).apiError).toEqual({ kind: "timeout" });
  });

  it("reports an HTTP error status without retrying forever", async () => {
    const counter = countHealthRequests(() =>
      HttpResponse.json({ detail: "down" }, { status: 503 }),
    );
    const { result } = renderHook(() => useHealth(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 5000 });
    expect(counter.calls).toBe(2);
    expect((result.current.error as ApiRequestError).apiError).toEqual({
      kind: "http",
      status: 503,
      detail: "down",
    });
  });

  it("shares one request between every part of the shell that reads it", async () => {
    const counter = countHealthRequests(() =>
      HttpResponse.json({ status: "ok", data_mode: "synthetic", version: "1" }),
    );
    const Wrapper = wrapper();
    render(
      <Wrapper>
        <ApiStatus />
        <ApiStatus />
      </Wrapper>,
    );
    expect(await screen.findAllByText("API ready (data: synthetic, version 1)")).toHaveLength(2);
    expect(counter.calls).toBe(1);
  });
});

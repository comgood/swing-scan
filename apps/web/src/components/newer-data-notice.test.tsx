import { focusManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { META_POLL_MS, META_STALE_MS, useMeta } from "@/components/shell/use-meta";
import { mocks } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";

import {
  isNewerThan,
  NEWER_DATA_TEXT,
  NewerDataNotice,
  ResultNewerDataNotice,
} from "./newer-data-notice";

const DATA_END = "2025-12-31";
const NEWER_END = "2026-01-02";

function wrapper() {
  const client = new QueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

/** Serves `/meta` and counts the polls, so "no poll at all" is checkable (AC-6, AC-11). */
function countMeta(respond: () => Response) {
  const counter = { calls: 0 };
  server.use(
    http.get("*/api/v1/meta", () => {
      counter.calls += 1;
      return respond();
    }),
  );
  return counter;
}

function metaEnding(end: string | null): () => Response {
  const data = end === null ? null : { ...mocks.meta.data, end };
  return () => HttpResponse.json({ ...mocks.meta, data });
}

afterEach(() => {
  focusManager.setFocused(undefined);
  vi.restoreAllMocks();
});

// covers: AC-2 (the comparison is against the result's own dataset), AC-8 (a null dataset is
// not a change)
describe("isNewerThan (AC-2, AC-8)", () => {
  it.each([
    [NEWER_END, true],
    [DATA_END, false],
    ["2025-12-30", false],
    [null, false],
    [undefined, false],
  ])("treats a polled end of %j as newer: %s", (latest, expected) => {
    expect(isNewerThan(DATA_END, latest)).toBe(expected);
  });
});

describe("NewerDataNotice (AC-4, AC-13)", () => {
  it("tells you to reload, in a polite live region, once newer data exists", async () => {
    const { container } = render(<NewerDataNotice newer />);
    const notice = screen.getByRole("status");
    expect(notice).toHaveTextContent(NEWER_DATA_TEXT);
    expect(NEWER_DATA_TEXT).toContain("Reload");
    await expectNoAxeViolations(container);
  });

  it("renders nothing at all while the data is current", () => {
    const { container } = render(<NewerDataNotice newer={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("useMeta (AC-1, AC-6, AC-7, AC-11)", () => {
  it("polls every 30 s, and goes stale sooner so a refocus checks once", () => {
    expect(META_POLL_MS).toBe(30_000);
    expect(META_STALE_MS).toBeGreaterThan(0);
    expect(META_STALE_MS).toBeLessThan(META_POLL_MS);
  });

  it("waits for the health query, so a cold start sees one waking request (AC-11)", async () => {
    server.use(http.get("*/api/v1/health", () => HttpResponse.error()));
    const counter = countMeta(metaEnding(DATA_END));
    const { result } = renderHook(() => useMeta(), { wrapper: wrapper() });
    // Health retries once and then fails; the meta query must never have fired.
    await waitFor(() => expect(result.current.fetchStatus).toBe("idle"), { timeout: 5000 });
    expect(counter.calls).toBe(0);
  });

  it("issues no poll while the tab is in the background, then checks once on refocus (AC-6)", async () => {
    const counter = countMeta(metaEnding(DATA_END));
    vi.useFakeTimers();
    try {
      renderHook(() => useMeta(), { wrapper: wrapper() });
      await vi.advanceTimersByTimeAsync(20); // health, then the first meta read
      const atMount = counter.calls;
      expect(atMount).toBe(1);

      // The interval follows the tab: `refetchIntervalInBackground` stays off, so a hidden tab
      // issues nothing at all, however long it sits there.
      focusManager.setFocused(false);
      await vi.advanceTimersByTimeAsync(META_POLL_MS * 3);
      expect(counter.calls).toBe(atMount);

      // Coming back checks once, which needs the finite `staleTime` above: an infinite one
      // would make the query fresh forever and never refetch on focus.
      focusManager.setFocused(true);
      await vi.advanceTimersByTimeAsync(20);
      expect(counter.calls).toBe(atMount + 1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps the last good dataset when a poll fails, and shows no error (AC-7)", async () => {
    const { result } = renderHook(() => useMeta(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const good = result.current.data;

    server.use(
      http.get("*/api/v1/meta", () => HttpResponse.json({ detail: "down" }, { status: 500 })),
    );
    await result.current.refetch();
    // The query knows it failed, but `data` still names the dataset the page last saw, so
    // nothing on screen changes and the next poll recovers on its own.
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toEqual(good);
  });
});

describe("ResultNewerDataNotice (AC-2, AC-4, AC-7, AC-8)", () => {
  it("appears once the poll names a later session than the result's own dataset", async () => {
    countMeta(metaEnding(NEWER_END));
    const Wrapper = wrapper();
    render(
      <Wrapper>
        <ResultNewerDataNotice dataEnd={DATA_END} />
      </Wrapper>,
    );
    expect(await screen.findByRole("status")).toHaveTextContent(NEWER_DATA_TEXT);
  });

  it("stays away when the poll names the very dataset the result was computed on", async () => {
    countMeta(metaEnding(DATA_END));
    const Wrapper = wrapper();
    const { container } = render(
      <Wrapper>
        <ResultNewerDataNotice dataEnd={DATA_END} />
      </Wrapper>,
    );
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it.each([
    ["no dataset at all (AC-8)", metaEnding(null)],
    ["a failed poll (AC-7)", () => HttpResponse.json({ detail: "down" }, { status: 500 })],
  ])("shows nothing for %s", async (_label, respond) => {
    countMeta(respond);
    const Wrapper = wrapper();
    const { container } = render(
      <Wrapper>
        <ResultNewerDataNotice dataEnd={DATA_END} />
      </Wrapper>,
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });
});

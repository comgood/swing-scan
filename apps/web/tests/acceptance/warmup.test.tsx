// QA acceptance: U-5, from doc 01 section 6.6 and spec 0003 AC-4, AC-9.
// "Given the API is cold, when a request is pending > 1.5 s, then a 'warming up the engine…'
// state shows." The shell's health ping is the first request every page makes, so a slow
// ping (an MSW delay) stands in for the cold Lambda.
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Home from "@/app/page";
import { WarmupNotice } from "@/components/warmup-notice";
import { healthHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";

import { renderPage, WARMUP_TEXT } from "./pages";

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe("U-5 on the shell's first request", () => {
  it("U-5: a request pending past 1.5 s shows the notice, and it goes when the answer arrives", async () => {
    server.use(healthHandler("synthetic", { delayMs: 2500 }));
    renderPage(Home);

    expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument();
    await wait(1200);
    expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument();

    expect(await screen.findByText(WARMUP_TEXT, {}, { timeout: 1500 })).toBeVisible();
    await screen.findByText(/API ready/, {}, { timeout: 3000 });
    await waitFor(() => expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument());
  });

  it("U-5: a fast answer never shows the notice", async () => {
    renderPage(Home);
    await screen.findByText(/API ready/);
    await wait(1700);
    expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument();
  });

  it("U-5: the notice sits in a polite live region so screen readers announce it", async () => {
    server.use(healthHandler("synthetic", { delayMs: "infinite" }));
    renderPage(Home);
    const text = await screen.findByText(WARMUP_TEXT, {}, { timeout: 2500 });
    const region = text.closest('[role="status"]');
    expect(region).not.toBeNull();
    expect(region).toHaveAttribute("aria-live", "polite");
  });
});

describe("U-5 threshold, any request (WarmupNotice with a pending flag)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("U-5: empty at 1,499 ms, shown at 1,500 ms, gone when the request ends, and the timer restarts", () => {
    vi.useFakeTimers();
    const { rerender } = render(<WarmupNotice pending />);

    act(() => vi.advanceTimersByTime(1499));
    expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByText(WARMUP_TEXT)).toBeInTheDocument();

    rerender(<WarmupNotice pending={false} />);
    expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument();

    rerender(<WarmupNotice pending />);
    act(() => vi.advanceTimersByTime(1499));
    expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByText(WARMUP_TEXT)).toBeInTheDocument();
  });
});

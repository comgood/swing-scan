// QA acceptance: U-1 (banner part) and U-2, from doc 01 section 6.6 and spec 0003 AC-3, AC-4.
// Written against the MSW mocks; the health ping decides the banner text.
// Not covered here: U-1's "builder opens with Breakout and its results" (feature 8 and 10 UI).
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { healthHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";

import { LIVE_BANNER, PAGES, renderPage, SYNTHETIC_BANNER } from "./pages";

describe.each(PAGES)("page $path", ({ Page }) => {
  it("U-1: shows the synthetic banner at the top of main before the health ping answers", async () => {
    server.use(healthHandler("synthetic", { delayMs: "infinite" }));
    renderPage(Page);
    const main = screen.getByRole("main");
    expect(main.firstElementChild).toHaveTextContent(SYNTHETIC_BANNER);
    expect(screen.queryByText(LIVE_BANNER)).not.toBeInTheDocument();
  });

  it("U-1: keeps the synthetic banner after a synthetic health ping", async () => {
    renderPage(Page);
    await screen.findByText(/API ready/);
    const main = screen.getByRole("main");
    expect(within(main).getByText(SYNTHETIC_BANNER)).toBeVisible();
    expect(main.firstElementChild).toHaveTextContent(SYNTHETIC_BANNER);
  });

  it("U-1: keeps the synthetic banner when the API cannot be reached", async () => {
    server.use(healthHandler("network_error"));
    renderPage(Page);
    await screen.findByText("API not reachable", {}, { timeout: 5000 });
    expect(screen.getByText(SYNTHETIC_BANNER)).toBeVisible();
    expect(screen.queryByText(LIVE_BANNER)).not.toBeInTheDocument();
  });

  it("U-1: the banner cannot be dismissed", async () => {
    renderPage(Page);
    await screen.findByText(/API ready/);
    const banner = screen.getByRole("main").firstElementChild as HTMLElement;
    expect(within(banner).queryByRole("button")).not.toBeInTheDocument();
  });

  it("U-2: live mode shows the survivors-only, current S&P warning instead", async () => {
    server.use(healthHandler("live"));
    renderPage(Page);
    const live = await screen.findByText(LIVE_BANNER);
    expect(live).toBeVisible();
    expect(screen.getByRole("main").firstElementChild).toHaveTextContent(LIVE_BANNER);
    expect(screen.queryByText(SYNTHETIC_BANNER)).not.toBeInTheDocument();
  });
});

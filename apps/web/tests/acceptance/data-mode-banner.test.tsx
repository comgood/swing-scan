// QA acceptance: U-1 (banner part) and U-2, from doc 01 section 6.6 and spec 0003 AC-3, AC-4.
// Written against the MSW mocks; the health ping decides the banner text.
// The rest of U-1 (the builder opening on Breakout with its results) is in template-scan.test.tsx
// and rule-builder.test.tsx.
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { healthHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";

import { LIVE_BANNER, PAGES, renderPage, SYNTHETIC_BANNER } from "./pages";

// The data mode banner is main's first child (spec 0003 AC-3). Assertions target that element,
// not the whole page: the /ui gallery shows both banner texts as static samples.
function shellBanner(): HTMLElement {
  return screen.getByRole("main").firstElementChild as HTMLElement;
}

describe.each(PAGES)("page $path", ({ Page }) => {
  it("U-1: shows the synthetic banner at the top of main before the health ping answers", async () => {
    server.use(healthHandler("synthetic", { delayMs: "infinite" }));
    renderPage(Page);
    expect(shellBanner()).toHaveTextContent(SYNTHETIC_BANNER);
    expect(shellBanner()).not.toHaveTextContent(LIVE_BANNER);
  });

  it("U-1: keeps the synthetic banner after a synthetic health ping", async () => {
    renderPage(Page);
    await screen.findByText(/API ready/);
    expect(within(shellBanner()).getByText(SYNTHETIC_BANNER)).toBeVisible();
    expect(shellBanner()).not.toHaveTextContent(LIVE_BANNER);
  });

  it("U-1: keeps the synthetic banner when the API cannot be reached", async () => {
    server.use(healthHandler("network_error"));
    renderPage(Page);
    await screen.findByText("API not reachable", {}, { timeout: 5000 });
    expect(within(shellBanner()).getByText(SYNTHETIC_BANNER)).toBeVisible();
    expect(shellBanner()).not.toHaveTextContent(LIVE_BANNER);
  });

  it("U-1: the banner cannot be dismissed", async () => {
    renderPage(Page);
    await screen.findByText(/API ready/);
    expect(within(shellBanner()).queryByRole("button")).not.toBeInTheDocument();
  });

  it("U-2: live mode shows the survivors-only, current S&P warning instead", async () => {
    server.use(healthHandler("live"));
    renderPage(Page);
    // Wait for the health ping to say live, so a static sample of the text can't satisfy it.
    await screen.findByText(/API ready \(data: live/);
    expect(within(shellBanner()).getByText(LIVE_BANNER)).toBeVisible();
    expect(shellBanner()).not.toHaveTextContent(SYNTHETIC_BANNER);
  });
});

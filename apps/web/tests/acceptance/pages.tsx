// QA acceptance support: every page the app ships today, rendered the way the root layout
// renders it (inside the shell, with one QueryClient). Add a page here when a feature adds one,
// so the "every page" criteria (U-1 banner, U-2) cover it automatically.
import type { ReactElement } from "react";

import BacktestPage from "@/app/backtest/page";
import Home from "@/app/page";
import UiGalleryPage from "@/app/ui/page";
import { AppShell } from "@/components/shell/app-shell";
import { renderWithQuery } from "@/test/render";

export const PAGES: { path: string; Page: () => ReactElement }[] = [
  { path: "/", Page: Home },
  { path: "/backtest", Page: BacktestPage },
  { path: "/ui", Page: UiGalleryPage },
];

export function renderPage(Page: () => ReactElement) {
  return renderWithQuery(
    <AppShell>
      <Page />
    </AppShell>,
  );
}

/** Doc 01 U-1, word for word. */
export const SYNTHETIC_BANNER = "Synthetic market: not real prices";

/** Spec 0003 AC-4 fixes the words; doc 01 U-2 fixes the meaning (survivors only, current S&P). */
export const LIVE_BANNER =
  "Live data: current S&P 500 members only (survivors). Results are biased upward.";

/** Doc 01 U-5, with the U+2026 ellipsis spec 0003 AC-9 fixes. */
export const WARMUP_TEXT = "Warming up the engine…";

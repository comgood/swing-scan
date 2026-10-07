"use client";

// The one global data mode signal (spec 0003 AC-4, U-1, U-2). The static HTML always holds the
// synthetic text; it switches only after the health ping says exactly "live".
import { Banner } from "@/components/banner";

import { isLive, useHealth } from "./use-health";

export const SYNTHETIC_TEXT = "Synthetic market: not real prices";
export const LIVE_TEXT =
  "Live data: current S&P 500 members only (survivors). Results are biased upward.";

export function DataModeBanner() {
  const health = useHealth();
  return <Banner variant="warning">{isLive(health.data) ? LIVE_TEXT : SYNTHETIC_TEXT}</Banner>;
}

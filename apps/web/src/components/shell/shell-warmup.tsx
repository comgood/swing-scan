"use client";

// The warm up notice bound to the shell's health query, so a cold start shows it (AC-4).
import { WarmupNotice } from "@/components/warmup-notice";

import { useHealth } from "./use-health";

export function ShellWarmup() {
  const health = useHealth();
  return <WarmupNotice pending={health.isPending} className="mt-2" />;
}

"use client";

// Tells you a slow request is the engine waking up (spec 0003 AC-9, U-5). Pass TanStack
// Query's `isPending`, never `isFetching`, so a background refetch never shows it.
// The live region is always in the DOM so screen readers announce the text when it appears.
import { useEffect, useState } from "react";

import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

export const WARMUP_DELAY_MS = 1500;

interface WarmupNoticeProps {
  pending: boolean;
  className?: string;
}

export function WarmupNotice({ pending, className }: WarmupNoticeProps) {
  const [warming, setWarming] = useState(false);

  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(() => setWarming(true), WARMUP_DELAY_MS);
    return () => {
      clearTimeout(timer);
      setWarming(false);
    };
  }, [pending]);

  const show = pending && warming;
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(show && "flex items-center gap-2 text-sm text-muted-foreground", className)}
    >
      {show && (
        <>
          <Spinner />
          <span>Warming up the engine…</span>
        </>
      )}
    </div>
  );
}

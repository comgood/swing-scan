"use client";

import { useEffect, useState, type ReactNode } from "react";

/** True when the browser build should answer API calls from the mocks (spec 0002). */
export const API_MOCK = process.env.NEXT_PUBLIC_API_MOCK === "1";

// Holds rendering until the mock service worker is ready, so the first API call is mocked.
// With mocks off it renders children straight away and the worker code is never loaded.
export function MockProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(!API_MOCK);

  useEffect(() => {
    if (!API_MOCK) return;
    let cancelled = false;
    import("./browser")
      .then(({ worker }) => worker.start({ onUnhandledRequest: "bypass" }))
      .then(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return ready ? children : null;
}

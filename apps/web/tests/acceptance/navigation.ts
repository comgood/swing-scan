// QA acceptance support: `next/navigation` emulated over jsdom's `window.location` and
// `window.history`, shared by the page tests.
//
// The App Router keeps `useSearchParams` in step with `window.history.pushState` and
// `replaceState`. The emulation does the same: the URL lives in jsdom's `window.location`, the
// history methods are wrapped to re render subscribers, and `router.replace` / `push` go through
// them. Tests assert on the URL and on `history.length`, never on which API the page called
// (docs/qa/ac-questions.md#AC-10-url).
//
// Use it from a test file with:
//
//   vi.mock("next/navigation", async (importOriginal) =>
//     (await import("./navigation")).emulatedNavigation(await importOriginal()),
//   );
import { useSyncExternalStore } from "react";

const listeners = new Set<() => void>();
let cached = { search: "\u0000", params: new URLSearchParams() };

function params(): URLSearchParams {
  const search = window.location.search;
  if (cached.search !== search) cached = { search, params: new URLSearchParams(search) };
  return cached.params;
}

function notify() {
  listeners.forEach((l) => l());
}

const original = {
  push: window.history.pushState.bind(window.history),
  replace: window.history.replaceState.bind(window.history),
};

window.history.pushState = (...args: Parameters<History["pushState"]>) => {
  original.push(...args);
  notify();
};
window.history.replaceState = (...args: Parameters<History["replaceState"]>) => {
  original.replace(...args);
  notify();
};

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const nav = {
  /** Open `path` with `search` as a fresh visit (the setup itself adds no history entry). */
  set(search: string, path = "/") {
    const q = search.replace(/^\?/, "");
    original.replace(null, "", q ? `${path}?${q}` : path);
    notify();
  },
};

export function emulatedNavigation<T extends object>(actual: T) {
  const router = {
    replace: (href: string) => window.history.replaceState(null, "", href),
    push: (href: string) => window.history.pushState(null, "", href),
    prefetch: () => {},
    back: () => {},
    forward: () => {},
    refresh: () => {},
  };
  return {
    ...actual,
    useRouter: () => router,
    usePathname: () => window.location.pathname,
    useSearchParams: () => useSyncExternalStore(subscribe, params, params),
  };
}

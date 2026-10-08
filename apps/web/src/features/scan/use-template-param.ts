"use client";

// The selected template in the URL as `?template=<id>` (spec 0005 AC-10). Read with
// `useSearchParams`, so the reader must sit inside `Suspense` for the static export. Written
// with `history.replaceState`, which the App Router syncs into `useSearchParams` and which adds
// no history entry (the same effect as `router.replace`, without needing a mounted router).
import { useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

export const TEMPLATE_PARAM = "template";

/** The URL after setting `?template` to `id`, or removing it when `id` is null. */
export function templateUrl(
  pathname: string,
  search: string,
  hash: string,
  id: string | null,
): string {
  const params = new URLSearchParams(search);
  if (id === null) params.delete(TEMPLATE_PARAM);
  else params.set(TEMPLATE_PARAM, id);
  const query = params.toString();
  return `${pathname}${query ? `?${query}` : ""}${hash}`;
}

export function useTemplateParam(): [string | null, (id: string | null) => void] {
  // Null only outside the App Router (a component test with no router). The choice is then
  // kept in local state, so the workspace still works; the URL stays the only source in the app.
  const searchParams = useSearchParams() as URLSearchParams | null;
  const [local, setLocal] = useState<string | null>(null);
  const hasRouter = searchParams !== null;
  const value = hasRouter ? searchParams.get(TEMPLATE_PARAM) : local;
  const setValue = useCallback(
    (id: string | null) => {
      const { pathname, search, hash } = window.location;
      window.history.replaceState(null, "", templateUrl(pathname, search, hash, id));
      if (!hasRouter) setLocal(id);
    },
    [hasRouter],
  );
  return [value, setValue];
}

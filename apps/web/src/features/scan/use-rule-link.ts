"use client";

// The workspace's rule in the URL (spec 0005 AC-10, spec 0008 decision 3): `?template=<id>` for
// an unedited template (Breakout has no parameter), `?r=<encoded rule>` once you edit, never both.
// Read with `useSearchParams`, so the reader must sit inside `Suspense` for the static export.
// Written with `history.replaceState`, which the App Router syncs into `useSearchParams` and which
// adds no history entry (the same effect as `router.replace`, without needing a mounted router).
import { useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

export const TEMPLATE_PARAM = "template";
export const RULE_PARAM = "r";

export interface RuleLink {
  template: string | null;
  r: string | null;
}

/** The URL with `?template` and `?r` set to `link` (null removes one), other keys kept. */
export function linkUrl(pathname: string, search: string, hash: string, link: RuleLink): string {
  const params = new URLSearchParams(search);
  for (const [key, value] of [
    [TEMPLATE_PARAM, link.template],
    [RULE_PARAM, link.r],
  ] as const) {
    if (value === null) params.delete(key);
    else params.set(key, value);
  }
  const query = params.toString();
  return `${pathname}${query ? `?${query}` : ""}${hash}`;
}

/** The URL after setting `?template` to `id` (or removing it), dropping any `?r`. */
export function templateUrl(
  pathname: string,
  search: string,
  hash: string,
  id: string | null,
): string {
  return linkUrl(pathname, search, hash, { template: id, r: null });
}

export function useRuleLink(): [RuleLink, (link: RuleLink) => void] {
  // Null only outside the App Router (a component test with no router). The link is then kept
  // in local state, so the workspace still works; the URL stays the only source in the app.
  const searchParams = useSearchParams() as URLSearchParams | null;
  const [local, setLocal] = useState<RuleLink>({ template: null, r: null });
  const hasRouter = searchParams !== null;
  const value = hasRouter
    ? { template: searchParams.get(TEMPLATE_PARAM), r: searchParams.get(RULE_PARAM) }
    : local;
  const setValue = useCallback(
    (link: RuleLink) => {
      const { pathname, search, hash } = window.location;
      const next = linkUrl(pathname, search, hash, link);
      if (next !== `${pathname}${search}${hash}`) window.history.replaceState(null, "", next);
      if (!hasRouter) setLocal(link);
    },
    [hasRouter],
  );
  return [value, setValue];
}

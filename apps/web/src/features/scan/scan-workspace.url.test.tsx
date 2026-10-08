// covers: spec 0005 AC-10 (`?template` in the URL). `next/navigation` is replaced by a store that
// follows `history.replaceState`, as the App Router does.
import type { ScanRequest } from "@swing-scan/api-client";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mocks, templatesHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { renderWithQuery } from "@/test/render";

import { ScanWorkspace } from "./scan-workspace";
import { templateUrl } from "./use-template-param";

const nav = vi.hoisted(() => ({ search: "", listeners: new Set<() => void>() }));

vi.mock("next/navigation", async () => {
  const React = await import("react");
  return {
    useSearchParams: () => {
      const search = React.useSyncExternalStore(
        (listener) => {
          nav.listeners.add(listener);
          return () => nav.listeners.delete(listener);
        },
        () => nav.search,
      );
      return React.useMemo(() => new URLSearchParams(search), [search]);
    },
  };
});

const realReplace = window.history.replaceState.bind(window.history);

function open(url: string) {
  realReplace(null, "", url);
  nav.search = window.location.search;
}

function recordScans() {
  const bodies: ScanRequest[] = [];
  server.use(
    http.post("*/api/v1/scan", async ({ request }) => {
      bodies.push((await request.json()) as ScanRequest);
      return HttpResponse.json(mocks.scan);
    }),
  );
  return bodies;
}

const ruleOf = (id: string) => mocks.templates.find((t) => t.id === id)!.rule;

beforeEach(() => {
  vi.spyOn(window.history, "replaceState").mockImplementation((state, unused, url) => {
    realReplace(state, unused, url);
    nav.search = window.location.search;
    nav.listeners.forEach((listener) => listener());
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  open("/");
});

describe("templateUrl", () => {
  it("sets, replaces and removes the parameter, keeping others", () => {
    expect(templateUrl("/", "", "", "pullback_ema21")).toBe("/?template=pullback_ema21");
    expect(templateUrl("/", "?template=a&x=1", "#t", "b")).toBe("/?template=b&x=1#t");
    expect(templateUrl("/", "?template=a", "", null)).toBe("/");
    expect(templateUrl("/", "?x=1&template=a", "", null)).toBe("/?x=1");
  });
});

describe("ScanWorkspace and ?template", () => {
  it("opens the template named in the link", async () => {
    open("/?template=pullback_ema21");
    const bodies = recordScans();
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByLabelText("Template")).toHaveValue("pullback_ema21");
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({ rule: ruleOf("pullback_ema21") });
  });

  it("opens Breakout for an unknown id and drops the parameter", async () => {
    open("/?template=nope");
    const bodies = recordScans();
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByLabelText("Template")).toHaveValue("breakout_52w");
    await waitFor(() => expect(window.location.search).toBe(""));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({ rule: ruleOf("breakout_52w") });
  });

  it("shows a skeleton and runs no scan until the templates load", async () => {
    server.use(templatesHandler({ delayMs: "infinite" }));
    const bodies = recordScans();
    renderWithQuery(<ScanWorkspace />);
    expect(screen.getByText("Loading templates…")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByLabelText("Template")).not.toBeInTheDocument();
    expect(bodies).toHaveLength(0);
  });

  it("switching replaces the URL without a new history entry; Breakout carries no parameter", async () => {
    const bodies = recordScans();
    const user = userEvent.setup();
    const before = window.history.length;
    renderWithQuery(<ScanWorkspace />);
    const select = await screen.findByLabelText("Template");

    await user.selectOptions(select, "pullback_ema21");
    expect(window.location.search).toBe("?template=pullback_ema21");
    expect(select).toHaveValue("pullback_ema21");
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual({ rule: ruleOf("pullback_ema21") });

    await user.selectOptions(select, "breakout_52w");
    expect(window.location.search).toBe("");
    expect(window.history.length).toBe(before);
  });
});

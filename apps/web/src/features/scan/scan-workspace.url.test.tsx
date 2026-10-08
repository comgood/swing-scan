// covers: spec 0005 AC-10 (`?template` in the URL). `next/navigation` is replaced by a store that
// follows `history.replaceState`, as the App Router does.
import type { Rule, ScanRequest, ScanResponse } from "@swing-scan/api-client";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BAD_LINK_NOTICE, decodeRule, encodeRule } from "@/features/rule-builder";
import { mocks, templatesHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { renderWithQuery } from "@/test/render";

import { LINK_DEBOUNCE_MS, ScanWorkspace } from "./scan-workspace";
import { linkUrl, templateUrl } from "./use-rule-link";

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
    expect(templateUrl("/", "?r=abc", "", "b")).toBe("/?template=b");
  });

  it("linkUrl never leaves both parameters when one is replaced", () => {
    expect(linkUrl("/", "?template=a&x=1", "", { template: null, r: "abc" })).toBe("/?x=1&r=abc");
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

// covers: spec 0005 AC-10 edges (Breakout named outright, empty id, other keys, page 1 on switch)
describe("ScanWorkspace and ?template edges", () => {
  it.each(["breakout_52w", ""])(
    "opens Breakout for ?template=%s and drops the parameter",
    async (id) => {
      open(`/?template=${id}`);
      const bodies = recordScans();
      const before = window.history.length;
      renderWithQuery(<ScanWorkspace />);
      expect(await screen.findByLabelText("Template")).toHaveValue("breakout_52w");
      await waitFor(() => expect(window.location.search).toBe(""));
      await waitFor(() => expect(bodies).toHaveLength(1));
      expect(bodies[0]).toEqual({ rule: ruleOf("breakout_52w") });
      expect(window.history.length).toBe(before);
    },
  );

  it("keeps other query keys and the hash when it drops an unknown template", async () => {
    open("/?x=1&template=nope#top");
    recordScans();
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByLabelText("Template")).toHaveValue("breakout_52w");
    await waitFor(() => expect(window.location.search).toBe("?x=1"));
    expect(window.location.hash).toBe("#top");
  });

  it("returns the table to page 1 when you switch templates", async () => {
    const many: ScanResponse = {
      ...mocks.scan,
      rows: Array.from({ length: 120 }, (_, i) => ({
        ...mocks.scan.rows[0],
        ticker: `T${String(i).padStart(3, "0")}`,
      })),
    };
    server.use(http.post("*/api/v1/scan", () => HttpResponse.json(many)));
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    const pages = await screen.findByRole("navigation", { name: /pages$/ });
    await user.click(within(pages).getByRole("button", { name: "Next" }));
    expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Template"), "pullback_ema21");
    await waitFor(() => expect(screen.getByText("Page 1 of 3")).toBeInTheDocument());
  });
});

// covers: spec 0008 AC-1 (a `?r` link reproduces the rule), AC-2 (`?template` to `?r` on the
// first edit, debounced; old links still work), AC-3 (bad link fallback), AC-8 (a link scans)
describe("ScanWorkspace and ?r", () => {
  const NAMES = mocks.indicators.map((s) => s.name);
  const custom: Rule = {
    name: "Mine ✓",
    conditions: [
      {
        left: { kind: "ind", ind: "ema", n: 9, offset: 2, mult: 1.5 },
        op: "crosses_above",
        right: { kind: "ind", ind: "sma", n: 50, offset: 0, mult: 1 },
      },
    ],
  };
  const rows = () => screen.getAllByRole("group", { name: /^Condition \d$/ });
  const params = () => new URLSearchParams(window.location.search);

  it("opens the rule a ?r link carries and scans it", async () => {
    open(`/?r=${encodeRule(custom)}`);
    const bodies = recordScans();
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByLabelText("Name")).toHaveValue("Mine ✓");
    expect(rows()).toHaveLength(1);
    expect(screen.getByText("1.5×ema(9)[2] crosses above sma(50)")).toBeInTheDocument();
    expect(screen.getByLabelText("Template")).toHaveValue("");
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({ rule: custom });
    expect(screen.queryByText(BAD_LINK_NOTICE)).not.toBeInTheDocument();
  });

  it("prefers ?r over ?template and drops the template", async () => {
    open(`/?template=pullback_ema21&r=${encodeRule(custom)}`);
    const bodies = recordScans();
    renderWithQuery(<ScanWorkspace />);
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({ rule: custom });
    await waitFor(() => expect(params().has("template")).toBe(false));
    expect(decodeRule(params().get("r")!, NAMES)).toEqual(custom);
  });

  it("falls back to Breakout with a notice for a link that does not decode", async () => {
    open("/?r=not-a-rule");
    const bodies = recordScans();
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByText(BAD_LINK_NOTICE)).toBeInTheDocument();
    expect(screen.getByLabelText("Template")).toHaveValue("breakout_52w");
    await waitFor(() => expect(window.location.search).toBe(""));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({ rule: ruleOf("breakout_52w") });

    await userEvent.setup().selectOptions(screen.getByLabelText("Template"), "pullback_ema21");
    expect(screen.queryByText(BAD_LINK_NOTICE)).not.toBeInTheDocument();
  });

  it("switches to ?r a moment after the first edit, and back on picking a template", async () => {
    open("/?template=pullback_ema21");
    recordScans();
    const user = userEvent.setup();
    const before = window.history.length;
    renderWithQuery(<ScanWorkspace />);
    const name = await screen.findByLabelText("Name");

    await user.type(name, "!");
    expect(window.location.search).toBe("?template=pullback_ema21");
    await waitFor(() => expect(params().has("r")).toBe(true));
    expect(params().has("template")).toBe(false);
    expect(decodeRule(params().get("r")!, NAMES)).toEqual({
      ...ruleOf("pullback_ema21"),
      name: `${ruleOf("pullback_ema21").name}!`,
    });

    await user.selectOptions(screen.getByLabelText("Template"), "pullback_ema21");
    expect(window.location.search).toBe("?template=pullback_ema21");
    await new Promise((resolve) => setTimeout(resolve, LINK_DEBOUNCE_MS + 50));
    expect(window.location.search).toBe("?template=pullback_ema21");
    expect(window.history.length).toBe(before);
  });
});

// QA acceptance: U-3 (the assumptions header) on the portfolio backtest report `/backtest`
// (scope feature 9), from doc 01 section 6.6 and spec 0007 AC-10 and AC-12. Written against the
// rendered page (roles and labels), the `PortfolioResult` contract and its mocks; the report's
// own code is not read.
//
// The report is on `main`, so these are plain `it` and always block. U-3 stays pending in
// tests/acceptance/status.yaml until the exit lab report (feature 12) shows its header too
// (`horizon_bars`, the seed and one exit rule line per config).
import type { Schemas } from "@swing-scan/api-client";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import BacktestPage from "@/app/backtest/page";
import { mocks } from "@/mocks/handlers";
import { server } from "@/mocks/node";

import { nav } from "./navigation";
import { renderPage } from "./pages";

vi.mock("next/navigation", async (importOriginal) =>
  (await import("./navigation")).emulatedNavigation(await importOriginal<object>()),
);

type Assumptions = Schemas["Assumptions"];

/** Spec 0007 AC-12: a null field reads this. */
const NOT_USED = "not used in portfolio mode";

/** Run the report on Breakout with the form's defaults and return the assumptions header. */
async function runReport(body: Schemas["PortfolioResult"] = mocks.backtestPortfolio) {
  server.use(http.post("*/api/v1/backtest", () => HttpResponse.json(body)));
  nav.set("template=breakout_52w", "/backtest");
  renderPage(BacktestPage);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Run backtest" }));
  const header = await screen.findByRole("region", { name: "Assumptions" });
  return header;
}

/** The header as term → value pairs, in screen order. */
function entries(header: HTMLElement): [string, string][] {
  const terms = within(header).getAllByRole("term");
  return terms.map((dt) => {
    const dd = dt.nextElementSibling;
    expect(dd?.tagName, `no value after "${dt.textContent}"`).toBe("DD");
    return [norm(dt.textContent), norm(dd?.textContent)];
  });
}

function norm(text: string | null | undefined): string {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

/** The value of the one term matching `label`. */
function valueOf(pairs: [string, string][], label: RegExp): string {
  const hits = pairs.filter(([term]) => label.test(term));
  expect(
    hits.map(([t]) => t),
    `exactly one term matching ${label}`,
  ).toHaveLength(1);
  return hits[0][1];
}

/** A result whose every echoed setting differs from the form's defaults and the stock mock. */
function distinctResult(): Schemas["PortfolioResult"] {
  const base = mocks.backtestPortfolio;
  const assumptions: Assumptions = {
    ...base.assumptions,
    slippage_bps: 25,
    max_positions: 7,
    configs: [
      {
        name: "Tight",
        exits: [
          { type: "stop_pct", pct: 5 },
          { type: "time", bars: 12 },
        ],
      },
    ],
    oos_start: "2023-03-15",
    data_version: "synthetic:v1:seed7",
    data_seed: 7,
  };
  return { ...base, assumptions, oos_start: assumptions.oos_start };
}

describe("U-3 assumptions header on the portfolio report", () => {
  it("U-3: the report opens with an Assumptions header before the results", async () => {
    const header = await runReport();
    const results = screen.getByRole("heading", { name: "Results" });
    // DOCUMENT_POSITION_FOLLOWING: the results come after the header.
    expect(header.compareDocumentPosition(results) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("U-3: one line per Assumptions field (spec 0007 AC-12)", async () => {
    const pairs = entries(await runReport());
    expect(pairs).toHaveLength(Object.keys(mocks.backtestPortfolio.assumptions).length);
    for (const [term, value] of pairs) {
      expect(term, "an empty label").not.toBe("");
      expect(value, `"${term}" has no value`).not.toBe("");
    }
  });

  it("U-3: every doc 01 item is listed with the response's value", async () => {
    const a = mocks.backtestPortfolio.assumptions;
    const pairs = entries(await runReport());
    expect(valueOf(pairs, /fill model/i)).toMatch(/close/i);
    expect(valueOf(pairs, /fill model/i)).toMatch(/next open/i);
    expect(valueOf(pairs, /slippage/i)).toMatch(new RegExp(`\\b${a.slippage_bps}\\b`));
    expect(valueOf(pairs, /sizing/i)).toMatch(/equal weight/i);
    expect(valueOf(pairs, /max(imum)? positions/i)).toBe(String(a.max_positions));
    // Entry rule: rising edge, cooldown 10, no last bar entry.
    expect(valueOf(pairs, /^entry$/i)).toMatch(/rising edge/i);
    expect(valueOf(pairs, /^cooldown$/i)).toMatch(new RegExp(`\\b${a.cooldown_bars}\\b`));
    expect(valueOf(pairs, /last bar/i)).toMatch(/never|no|none/i);
    // Exit rules per config: the config's name and every exit's number.
    const exits = valueOf(pairs, /exit rules/i);
    expect(exits).toContain(a.configs[0].name);
    expect(exits).toMatch(/\b8(\.0+)?%/);
    expect(exits).toMatch(/\b20\b/);
    // horizon_bars and the seed are trade mode settings: null here.
    expect(valueOf(pairs, /horizon/i)).toBe(NOT_USED);
    expect(valueOf(pairs, /random seed/i)).toBe(NOT_USED);
    expect(valueOf(pairs, /delist/i)).toMatch(/last close/i);
    expect(valueOf(pairs, /out of sample from/i)).toBe(a.oos_start);
    expect(valueOf(pairs, /data mode/i)).toBe(a.data_mode);
    expect(valueOf(pairs, /data version/i)).toBe(a.data_version);
    expect(valueOf(pairs, /data seed/i)).toBe(String(a.data_seed));
  });

  it("U-3: the header echoes the response, not the form's defaults", async () => {
    const result = distinctResult();
    const a = result.assumptions;
    const pairs = entries(await runReport(result));
    expect(valueOf(pairs, /slippage/i)).toMatch(/\b25\b/);
    expect(valueOf(pairs, /max(imum)? positions/i)).toBe(String(a.max_positions));
    const exits = valueOf(pairs, /exit rules/i);
    expect(exits).toContain("Tight");
    expect(exits).toMatch(/\b5(\.0+)?%/);
    expect(exits).toMatch(/\b12\b/);
    expect(valueOf(pairs, /out of sample from/i)).toBe(a.oos_start);
    expect(valueOf(pairs, /data version/i)).toBe(a.data_version);
    expect(valueOf(pairs, /data seed/i)).toBe("7");
  });

  it("U-3: live mode shows its data mode and no data seed", async () => {
    const result = distinctResult();
    const live: Schemas["PortfolioResult"] = {
      ...result,
      assumptions: {
        ...result.assumptions,
        data_mode: "live",
        data_version: "live:2026-10-01",
        data_seed: null,
      },
    };
    const pairs = entries(await runReport(live));
    expect(valueOf(pairs, /data mode/i)).toBe("live");
    expect(valueOf(pairs, /data version/i)).toBe("live:2026-10-01");
    // A null seed never shows a number (spec 0007 AC-12 gives nulls one fixed wording).
    expect(valueOf(pairs, /data seed/i)).not.toMatch(/\d/);
  });
});

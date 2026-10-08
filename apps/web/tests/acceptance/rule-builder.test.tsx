// QA acceptance: the rule builder on `/` (scope feature 10) and the 422 path onto its rows and
// onto the exit form on `/backtest`, from doc 01 U-1, R-1, R-8 and U-7 and spec 0008 (AC-1, AC-2,
// AC-4, AC-7). Written against the mocks, the rendered DOM (labels, legends, roles) and the
// real API's 422 `loc` shapes; the builder's own code is not read.
//
// Every test goes through `acIt`: while its IDs are `pending` in tests/acceptance/status.yaml a
// failure is reported as skipped, and once they are `required` it fails the web suite.
import type { BacktestRequest, Rule } from "@swing-scan/api-client";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, vi } from "vitest";

import BacktestPage from "@/app/backtest/page";
import Home from "@/app/page";
import { mocks } from "@/mocks/handlers";
import { server } from "@/mocks/node";

import { acIt } from "./gate";
import { nav } from "./navigation";
import { renderPage } from "./pages";

vi.mock("next/navigation", async (importOriginal) =>
  (await import("./navigation")).emulatedNavigation(await importOriginal<object>()),
);

// ------------------------------------------------------------------ fixtures

const BREAKOUT = mocks.templates[0];

type Operand = Rule["conditions"][number]["left"] | Rule["conditions"][number]["right"];
type Condition = Rule["conditions"][number];

/** A rule that uses every operand shape, every optional field and a non ASCII name. */
const EVERY_SHAPE: Rule = {
  name: "Ünïcode rule ✓ & more",
  conditions: [
    {
      left: { kind: "ind", ind: "close", n: null, offset: 3, mult: 0.5 },
      op: "crosses_below",
      right: { kind: "ind", ind: "rs", n: 126, offset: 0, mult: 1 },
    },
    {
      left: { kind: "ind", ind: "ret", n: 20, offset: 0, mult: 1 },
      op: ">=",
      right: { kind: "value", value: -1.25 },
    },
    {
      left: { kind: "ind", ind: "ema", n: 21, offset: 0, mult: 1 },
      op: "<=",
      right: { kind: "ind", ind: "sma", n: 50, offset: 2, mult: 1.01 },
    },
    {
      left: { kind: "ind", ind: "volume", n: null, offset: 0, mult: 1 },
      op: "crosses_above",
      right: { kind: "ind", ind: "avg_volume", n: 50, offset: 1, mult: 2 },
    },
  ],
} as Rule;

/** Spec 0008 decision 3: `?r=` is base64url, no padding, of the rule's compact UTF-8 JSON. */
function encodeR(rule: Rule): string {
  const bytes = new TextEncoder().encode(JSON.stringify(rule));
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function decodeR(r: string): unknown {
  const b64 = r.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
}

// ------------------------------------------------------------------ requests

let scanBodies: { rule: Rule }[] = [];
let backtestBodies: BacktestRequest[] = [];

function recordScans() {
  server.use(
    http.post("*/api/v1/scan", async ({ request }) => {
      scanBodies.push((await request.json()) as { rule: Rule });
      return HttpResponse.json(mocks.scan);
    }),
  );
}

/** A 422 shaped exactly like the real API's (FastAPI `detail`, `loc` from the body root). */
function detail422(loc: (string | number)[], msg: string, input: unknown, ctx?: object) {
  return HttpResponse.json(
    { detail: [{ type: "out_of_range", loc: ["body", ...loc], msg, input, ctx }] },
    { status: 422 },
  );
}

beforeEach(() => {
  scanBodies = [];
  backtestBodies = [];
});

// ------------------------------------------------------------------ reading the rows

function conditionRows(): HTMLElement[] {
  return screen.getAllByRole("group", { name: /^Condition \d+$/ });
}

function row(i: number): HTMLElement {
  return screen.getByRole("group", { name: `Condition ${i}` });
}

function side(i: number, which: "Left" | "Right"): HTMLElement {
  return within(row(i)).getByRole("group", { name: `${which} side` });
}

function numberIn(scope: HTMLElement, label: string | RegExp): number {
  return Number((within(scope).getByLabelText(label) as HTMLInputElement).value);
}

function readOperand(group: HTMLElement): Operand {
  const indicator = within(group).queryByLabelText("Indicator") as HTMLSelectElement | null;
  if (!indicator) return { kind: "value", value: numberIn(group, "Number") };
  const window = within(group).queryByLabelText("Window (n)") as HTMLInputElement | null;
  return {
    kind: "ind",
    ind: indicator.value,
    n: window ? Number(window.value) : null,
    offset: numberIn(group, "Bars ago"),
    mult: numberIn(group, "Multiplier (×)"),
  } as Operand;
}

/** The rule as the rows on screen show it: the UI half of the R-8 parity check. */
function readRule(): Rule {
  const conditions = conditionRows().map((r, k) => {
    const i = k + 1;
    return {
      left: readOperand(side(i, "Left")),
      op: (within(r).getByLabelText("Operator") as HTMLSelectElement).value,
      right: readOperand(side(i, "Right")),
    } as Condition;
  });
  return { name: (screen.getByLabelText("Name") as HTMLInputElement).value, conditions } as Rule;
}

// ------------------------------------------------------------------ driving the page

function openAt(search = "") {
  nav.set(search);
  return renderPage(Home);
}

async function opened(): Promise<void> {
  await screen.findByRole("group", { name: "Condition 1" }, { timeout: 3000 });
  await waitFor(() => expect(scanBodies.length).toBeGreaterThan(0), { timeout: 3000 });
}

async function setNumber(scope: HTMLElement, label: string | RegExp, value: string) {
  const user = userEvent.setup();
  const input = within(scope).getByLabelText(label);
  await user.clear(input);
  await user.type(input, value);
}

async function choose(scope: HTMLElement, label: string, value: string) {
  await userEvent.setup().selectOptions(within(scope).getByLabelText(label), value);
}

async function runScan(): Promise<{ rule: Rule }> {
  const before = scanBodies.length;
  await userEvent.setup().click(screen.getByRole("button", { name: "Run scan" }));
  await waitFor(() => expect(scanBodies.length).toBeGreaterThan(before), { timeout: 3000 });
  return scanBodies[scanBodies.length - 1];
}

function rParam(): string | null {
  return new URLSearchParams(window.location.search).get("r");
}

// ------------------------------------------------------------------ U-1 the builder on first visit

describe("U-1 the builder opens with Breakout loaded", () => {
  acIt(["U-1"], "U-1: the builder opens with Breakout's rows and scans them", async () => {
    recordScans();
    openAt();
    await opened();
    expect(readRule()).toEqual(BREAKOUT.rule);
    expect(scanBodies[0].rule).toEqual(BREAKOUT.rule);
    expect(await screen.findAllByRole("table", {}, { timeout: 2000 })).not.toHaveLength(0);
  });
});

// ------------------------------------------------------------------ R-8 UI to JSON parity

describe("R-8 the scan request matches the builder rows", () => {
  acIt(
    ["R-8"],
    "R-8: edits, an added row and a removed row reach the request exactly as the rows show",
    async () => {
      recordScans();
      openAt();
      await opened();
      expect(scanBodies[0].rule).toEqual(readRule()); // the template, before any edit

      const user = userEvent.setup();
      // Row 1: operator and the left side's bars ago.
      await choose(row(1), "Operator", ">=");
      await setNumber(side(1, "Left"), "Bars ago", "2");
      // Row 2: the right side's window and multiplier.
      await setNumber(side(2, "Right"), "Window (n)", "20");
      await setNumber(side(2, "Right"), "Multiplier (×)", "2");
      // A new row (spec 0008 decision 8: close > sma(50)), then edited to rsi(14) > 70.
      await user.click(screen.getByRole("button", { name: "Add condition" }));
      expect(conditionRows()).toHaveLength(4);
      await choose(side(4, "Left"), "Indicator", "rsi");
      await choose(row(4), "Compare with", "value");
      await setNumber(side(4, "Right"), "Number", "70");
      // Remove row 3 (close > 5); row 4 becomes row 3.
      await user.click(screen.getByRole("button", { name: "Remove condition 3" }));
      expect(conditionRows()).toHaveLength(3);
      const name = screen.getByLabelText("Name");
      await user.clear(name);
      await user.type(name, "My edit");

      const body = await runScan();
      expect(body.rule).toEqual(readRule());
      expect(body.rule).toEqual({
        name: "My edit",
        conditions: [
          {
            ...BREAKOUT.rule.conditions[0],
            op: ">=",
            left: { ...BREAKOUT.rule.conditions[0].left, offset: 2 },
          },
          {
            ...BREAKOUT.rule.conditions[1],
            right: { kind: "ind", ind: "avg_volume", n: 20, offset: 0, mult: 2 },
          },
          {
            left: { kind: "ind", ind: "rsi", n: 14, offset: 0, mult: 1 },
            op: ">",
            right: { kind: "value", value: 70 },
          },
        ],
      });
    },
  );

  acIt(
    ["R-8"],
    "R-8: a rule loaded from the JSON panel becomes rows that serialise back to the same JSON",
    async () => {
      recordScans();
      openAt();
      await opened();
      const user = userEvent.setup();
      await user.click(screen.getByLabelText("Paste a rule"));
      await user.paste(JSON.stringify(EVERY_SHAPE, null, 2));
      await user.click(screen.getByRole("button", { name: "Load rule" }));

      await waitFor(() => expect(conditionRows()).toHaveLength(EVERY_SHAPE.conditions.length));
      expect(readRule()).toEqual(EVERY_SHAPE);
      const runButton = screen.getByRole("button", { name: "Run scan" }) as HTMLButtonElement;
      if (!runButton.disabled) await user.click(runButton);
      await waitFor(() => expect(scanBodies.at(-1)?.rule).toEqual(EVERY_SHAPE), { timeout: 3000 });
    },
  );
});

// ------------------------------------------------------------------ R-1 the link round trip

describe("R-1 the link reproduces the rule after a reload", () => {
  acIt(
    ["R-1"],
    "R-1: the first edit switches the link to ?r=, and reopening it gives the same rule",
    async () => {
      recordScans();
      const first = openAt();
      await opened();
      expect(window.location.search).toBe(""); // an unedited Breakout carries no parameter

      await setNumber(side(1, "Left"), "Bars ago", "1");
      await setNumber(side(2, "Right"), "Multiplier (×)", "2.5");
      await choose(row(3), "Operator", "crosses_above");
      const name = screen.getByLabelText("Name");
      await userEvent.setup().clear(name);
      await userEvent.setup().type(name, "Linked rule");
      const edited = readRule();

      // URL writes are debounced (spec 0008, 300 ms); the link then holds the whole rule.
      await waitFor(() => expect(rParam()).not.toBeNull(), { timeout: 3000 });
      await waitFor(() => expect(decodeR(rParam()!)).toEqual(edited), { timeout: 3000 });
      expect(new URLSearchParams(window.location.search).get("template")).toBeNull();

      // Reload: a fresh page on the same address.
      const search = window.location.search;
      first.unmount();
      scanBodies = [];
      openAt(search);
      await opened();
      expect(readRule()).toEqual(edited);
      expect(scanBodies.every((b) => JSON.stringify(b.rule) === JSON.stringify(edited))).toBe(true);
      expect(scanBodies[0].rule).toEqual(edited);
    },
  );

  acIt(
    ["R-1"],
    "R-1: a ?r= link in spec 0008's encoding opens that exact rule and scans it",
    async () => {
      recordScans();
      openAt(`?r=${encodeR(EVERY_SHAPE)}`);
      await opened();
      await waitFor(() => expect(conditionRows()).toHaveLength(EVERY_SHAPE.conditions.length));
      expect(readRule()).toEqual(EVERY_SHAPE);
      expect(scanBodies[0].rule).toEqual(EVERY_SHAPE);
      expect(decodeR(rParam()!)).toEqual(EVERY_SHAPE);
    },
  );
});

// ------------------------------------------------------------------ U-7 inline 422s

describe("U-7 a 422 shows on the offending builder row", () => {
  acIt(
    ["U-7"],
    "U-7: a 422 on row 2's right n shows on that field with its range, as typed",
    async () => {
      recordScans();
      openAt();
      await opened();
      await setNumber(side(2, "Right"), "Window (n)", "300");
      // The real API names the union member in the path: right.ind.n (test_ui.py checks it).
      server.use(
        http.post("*/api/v1/scan", async ({ request }) => {
          scanBodies.push((await request.json()) as { rule: Rule });
          return detail422(
            ["rule", "conditions", 1, "right", "ind", "n"],
            "must be between 2 and 252",
            300,
            {
              min: 2,
              max: 252,
            },
          );
        }),
      );
      await runScan();

      const field = within(side(2, "Right")).getByLabelText("Window (n)");
      await waitFor(() => expect(field).toHaveAttribute("aria-invalid", "true"));
      expect(field).toHaveAccessibleDescription(/between 2 and 252/i);
      expect(field).toHaveValue(field.getAttribute("type") === "number" ? 300 : "300");
      // No other row's window is marked.
      const other = within(side(1, "Right")).getByLabelText("Window (n)");
      expect(other).not.toHaveAttribute("aria-invalid", "true");
    },
  );

  acIt(["U-7"], "U-7: a 422 on row 2's left bars ago shows on that field only", async () => {
    recordScans();
    openAt();
    await opened();
    await setNumber(side(2, "Left"), "Bars ago", "30");
    server.use(
      http.post("*/api/v1/scan", async ({ request }) => {
        scanBodies.push((await request.json()) as { rule: Rule });
        return detail422(
          ["rule", "conditions", 1, "left", "offset"],
          "must be between 0 and 20",
          30,
          {
            min: 0,
            max: 20,
          },
        );
      }),
    );
    await runScan();

    const field = within(side(2, "Left")).getByLabelText("Bars ago");
    await waitFor(() => expect(field).toHaveAttribute("aria-invalid", "true"));
    expect(field).toHaveAccessibleDescription(/between 0 and 20/i);
    for (const i of [1, 3]) {
      expect(within(side(i, "Left")).getByLabelText("Bars ago")).not.toHaveAttribute(
        "aria-invalid",
        "true",
      );
    }
  });
});

describe("U-7 a 422 shows on the offending exit field", () => {
  acIt(
    ["U-7"],
    "U-7: a 422 on the stop's pct shows on Stop loss (%) on /backtest, not on the time exit",
    async () => {
      // The real API names the exit's type in the path: exits.<i>.stop_pct.pct. The index is
      // read from the request, so the test does not assume the form's exit order.
      server.use(
        http.post("*/api/v1/backtest", async ({ request }) => {
          const body = (await request.json()) as BacktestRequest;
          backtestBodies.push(body);
          const exits = body.configs[0].exits;
          const at = exits.findIndex((e) => e.type === "stop_pct");
          const stop = exits[at] as { pct: number };
          if (stop.pct <= 30) return HttpResponse.json(mocks.backtestPortfolio);
          return detail422(
            ["configs", 0, "exits", at, "stop_pct", "pct"],
            "must be between 1 and 30",
            stop.pct,
            {
              min: 1,
              max: 30,
            },
          );
        }),
      );
      nav.set("", "/backtest");
      renderPage(BacktestPage);
      const stopField = await screen.findByLabelText("Stop loss (%)", {}, { timeout: 3000 });
      await setNumber(document.body, "Stop loss (%)", "40");
      const before = backtestBodies.length;
      await userEvent.setup().click(screen.getByRole("button", { name: "Run backtest" }));
      await waitFor(() => expect(backtestBodies.length).toBeGreaterThan(before), { timeout: 3000 });

      await waitFor(() => expect(stopField).toHaveAttribute("aria-invalid", "true"));
      expect(stopField).toHaveAccessibleDescription(/between 1 and 30/i);
      expect(screen.getByLabelText("Time exit (bars)")).not.toHaveAttribute("aria-invalid", "true");
    },
  );
});

// QA acceptance: the exit lab on `/backtest` (scope feature 12), from doc 01 section 6.5 and 6.6
// (X-3, X-4, X-9, U-3, U-4, U-7, U-8) and spec 0009 AC-13 to AC-20. Written against the rendered
// page (roles, labels and the words on screen), the `TradeLabResult` contract and its mock; the
// lab's own code is not read.
//
// The page is on `main` (PR #74), so these are plain `it` and always block. The table itself is
// read through its header cells: every IS or OOS header carries `aria-label` "<metric> IS" or
// "<metric> OOS", which fixes each data cell's column without reading the component.
import type { Schemas } from "@swing-scan/api-client";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BacktestPage from "@/app/backtest/page";
import { mocks } from "@/mocks/handlers";
import { server } from "@/mocks/node";

import { nav } from "./navigation";
import { renderPage } from "./pages";

vi.mock("next/navigation", async (importOriginal) =>
  (await import("./navigation")).emulatedNavigation(await importOriginal<object>()),
);

const LAB = mocks.backtestTradeLab;
const CONFIGS = LAB.assumptions.configs;

/** Doc 01 U-8, word for word. */
const PROCEDURE_NOTE =
  "Trade mode isolates the exit effect: every config trades identical entries, so the exit " +
  "is the only difference. Pick the exit on in sample (IS), read out of sample (OOS) once, " +
  "then confirm with a single portfolio backtest.";

/** Spec 0009 AC-19: a null trade mode field reads this. */
const NOT_USED = "not used in trade mode";

/** Spec 0004, assumption 3. */
const LOCAL_PREFIX = "swing-scan:trials:v1:";
const SESSION_KEY = "swing-scan:session-trials:v1";

/**
 * The column header words for every ranked metric in `BestIs` (spec 0002). The contract fixes
 * the keys; the header words are the lab's, so the test fails loudly if a key has no column.
 */
const METRIC_COLUMNS: Record<string, string> = {
  win_rate_pct: "Win rate",
  avg_win_pct: "Average win",
  avg_loss_pct: "Average loss",
  expectancy_pct: "Expectancy (%)",
  expectancy_r: "Expectancy (R)",
  expectancy_per_bar_pct: "Expectancy per bar",
  profit_factor: "Profit factor",
  avg_mae_pct: "Average MAE",
  avg_mfe_pct: "Average MFE",
  horizon_exit_pct: "Exited by horizon",
};

/** An exit config with no stop, ATR stop or trailing stop has no R (spec 0009, FE "no stop"). */
function hasStop(config: Schemas["ExitConfig"]): boolean {
  return config.exits.some((e) => ["stop_pct", "stop_atr", "trail_pct"].includes(e.type));
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

// ------------------------------------------------------------------ driving the page

/** Switch `/backtest` to the exit lab and run it; returns once the table is on screen. */
async function runLab(): Promise<void> {
  nav.set("", "/backtest");
  renderPage(BacktestPage);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("radio", { name: /exit lab/i }, { timeout: 3000 }));
  await user.click(screen.getByRole("button", { name: /^Run exit lab$/i }));
  await screen.findByRole("region", { name: /in sample beside out of sample/i }, { timeout: 5000 });
}

function table(): HTMLTableElement {
  // The table sits in its own labelled scroll box (U-6); the box names it.
  const box = screen.getByRole("region", { name: /in sample beside out of sample/i });
  return within(box).getByRole("table") as HTMLTableElement;
}

/** Column index per IS or OOS header, e.g. "Win rate IS" or "Edge Expectancy (R) OOS". */
function columns(): Map<string, number> {
  const headers = Array.from(table().tHead?.rows ?? [])
    .flatMap((r) => Array.from(r.cells))
    .filter((c) => c.getAttribute("aria-label"));
  const out = new Map<string, number>();
  headers.forEach((cell, i) => out.set(cell.getAttribute("aria-label")!, i));
  expect(out.size, "every IS and OOS header carries an aria-label").toBe(headers.length);
  return out;
}

function bodyRows(): HTMLTableRowElement[] {
  return Array.from(table().tBodies[0]?.rows ?? []);
}

/** The name a body row shows first: the config's name, or "Random entries". */
function rowName(row: HTMLTableRowElement): string {
  const first = row.cells[0].querySelector("span, a, strong");
  return text(first ?? row.cells[0]);
}

/** The body row named `name` (a config's name, or "Random entries"). */
function rowNamed(name: string): HTMLTableRowElement {
  const hits = bodyRows().filter((r) => rowName(r) === name);
  expect(
    hits.map(rowName),
    `exactly one row named "${name}" (rows: ${bodyRows().map(rowName).join(", ")})`,
  ).toHaveLength(1);
  return hits[0];
}

/** The cell under `column` ("Win rate IS") in `row`, as the text on screen reads. */
function cell(row: HTMLTableRowElement, column: string): HTMLTableCellElement {
  const at = columns().get(column);
  expect(at, `a column labelled "${column}"`).not.toBeUndefined();
  const data = Array.from(row.cells).filter((c) => c.tagName === "TD");
  expect(data.length, "one data cell per IS or OOS header").toBe(columns().size);
  return data[at!];
}

function text(el: Element): string {
  return (el.textContent ?? "").replace(/\s+/g, " ").trim();
}

/** Every cell showing the "best IS" marker, as "<row name> | <column label>" pairs. */
function markedCells(): string[] {
  const cols = Array.from(columns().entries()).sort((a, b) => a[1] - b[1]);
  const out: string[] = [];
  for (const row of bodyRows()) {
    const name = rowName(row);
    const data = Array.from(row.cells).filter((c) => c.tagName === "TD");
    data.forEach((c, i) => {
      if (/best is/i.test(text(c))) out.push(`${name} | ${cols[i]?.[0] ?? `#${i}`}`);
    });
  }
  return out;
}

// ------------------------------------------------------------------ X-3 IS and OOS, best IS only

describe("X-3 IS and OOS columns, best IS highlighted in IS only", () => {
  it("X-3: every per trade metric shows an IS and an OOS column", async () => {
    await runLab();
    const cols = columns();
    const bases = new Set(Array.from(cols.keys()).map((label) => label.replace(/ (IS|OOS)$/, "")));
    expect(bases.size).toBeGreaterThanOrEqual(Object.keys(METRIC_COLUMNS).length);
    for (const base of bases) {
      expect(cols.has(`${base} IS`), `${base} has an IS column`).toBe(true);
      expect(cols.has(`${base} OOS`), `${base} has an OOS column`).toBe(true);
    }
    // Every ranked metric in the contract has a column of its own.
    for (const [key, label] of Object.entries(METRIC_COLUMNS)) {
      expect(cols.has(`${label} IS`), `${key} shows as "${label}"`).toBe(true);
    }
    expect(Object.keys(LAB.best_is).sort()).toEqual(Object.keys(METRIC_COLUMNS).sort());
  });

  it("X-3: each row shows its config's IS and OOS values from the response", async () => {
    await runLab();
    expect(bodyRows().length).toBe(CONFIGS.length + 1); // one per config, plus Random entries
    LAB.rows.forEach((row, i) => {
      const onScreen = rowNamed(CONFIGS[i].name);
      expect(text(cell(onScreen, "Trades IS"))).toBe(String(row.strategy.is.n_trades));
      expect(text(cell(onScreen, "Trades OOS"))).toBe(String(row.strategy.oos.n_trades));
      const winIs = row.strategy.is.win_rate_pct;
      if (winIs !== null) {
        expect(text(cell(onScreen, "Win rate IS"))).toContain(winIs.toFixed(2));
      }
    });
  });

  it("X-3: the best IS value of every metric is marked, in the IS cell only", async () => {
    await runLab();
    const expected: string[] = [];
    for (const [key, label] of Object.entries(METRIC_COLUMNS)) {
      const at = LAB.best_is[key as keyof Schemas["BestIs"]];
      expect(at, `best_is.${key} names a config`).not.toBeNull();
      const row = rowNamed(CONFIGS[at!].name);
      expect(text(cell(row, `${label} IS`)), `${label}: best IS marked`).toMatch(/best is/i);
      expect(text(cell(row, `${label} OOS`)), `${label}: OOS never marked`).not.toMatch(/best is/i);
      expected.push(`${CONFIGS[at!].name} | ${label} IS`);
    }
    // Nothing else is marked: no second row per metric, no OOS, random or edge cell.
    expect(markedCells().sort()).toEqual(expected.sort());
  });

  it("X-3: no OOS, random or edge cell is ever marked (AC-13)", async () => {
    await runLab();
    const marked = markedCells();
    expect(marked.filter((m) => / OOS$/.test(m))).toEqual([]);
    expect(marked.filter((m) => /\| Edge /.test(m))).toEqual([]);
    expect(marked.filter((m) => m.startsWith("Random entries"))).toEqual([]);
    // The marker is a word on screen, not colour alone (AC-13).
    expect(screen.getAllByText(/best is/i).length).toBeGreaterThan(0);
  });
});

// ------------------------------------------------------------------ X-4 no stop means no R

describe("X-4 a config without a stop shows % and n/a for R", () => {
  it("X-4: a stopless config shows expectancy in % and n/a in every R cell", async () => {
    await runLab();
    const stopless = CONFIGS.filter((c) => !hasStop(c));
    expect(stopless.length, "the mock has a stopless config").toBeGreaterThan(0);
    for (const config of stopless) {
      const row = rowNamed(config.name);
      const i = CONFIGS.indexOf(config);
      const pct = LAB.rows[i].strategy.is.expectancy_pct;
      expect(pct, "a stopless config still has a % expectancy").not.toBeNull();
      expect(text(cell(row, "Expectancy (%) IS"))).toContain(pct!.toFixed(2));
      for (const column of [
        "Expectancy (R) IS",
        "Expectancy (R) OOS",
        "Edge Expectancy (R) IS",
        "Edge Expectancy (R) OOS",
      ]) {
        expect(text(cell(row, column)), `${config.name}: ${column}`).toMatch(/^n\/a/i);
      }
    }
  });

  it("X-4: a config with a stop shows its R value, not n/a", async () => {
    await runLab();
    const withStop = CONFIGS.filter(hasStop);
    expect(withStop.length).toBeGreaterThan(0);
    for (const config of withStop) {
      const r = LAB.rows[CONFIGS.indexOf(config)].strategy.is.expectancy_r;
      expect(r).not.toBeNull();
      const shown = text(cell(rowNamed(config.name), "Expectancy (R) IS"));
      expect(shown, `${config.name}: an R value`).not.toMatch(/n\/a/i);
      expect(shown).toContain(r!.toFixed(2));
    }
  });

  it("X-4: a footnote explains that R needs a stop and names the stopless configs", async () => {
    await runLab();
    const note = screen.getByText(/R needs a stop/i);
    expect(note).toBeVisible();
    for (const config of CONFIGS.filter((c) => !hasStop(c))) {
      expect(text(note)).toContain(config.name);
    }
    // The n/a cells point at the footnote rather than leaving it to be found.
    const row = rowNamed(CONFIGS.filter((c) => !hasStop(c))[0].name);
    expect(cell(row, "Expectancy (R) IS").querySelector("sup, a")).not.toBeNull();
  });
});

// ------------------------------------------------------------------ X-9 the horizon warning

describe("X-9 the horizon warning badge", () => {
  const warnings = LAB.warnings.filter((w) => w.code === "horizon_exits_over_10pct");

  it("X-9: the warned config's row carries the badge and the warning message", async () => {
    await runLab();
    expect(warnings.length, "the mock warns about a config").toBeGreaterThan(0);
    for (const warning of warnings) {
      const name = CONFIGS[warning.config_index!].name;
      const row = rowNamed(name);
      expect(text(row.cells[0]), `${name}: the warning message`).toContain(warning.message);
      // A badge, in words, beside the config name (AC-15).
      expect(text(row.cells[0])).toMatch(/horizon/i);
    }
  });

  it("X-9: no other config row shows the warning", async () => {
    await runLab();
    const warned = new Set(warnings.map((w) => CONFIGS[w.config_index!].name));
    for (const config of CONFIGS.filter((c) => !warned.has(c.name))) {
      const row = rowNamed(config.name);
      for (const warning of warnings) {
        expect(text(row.cells[0]), `${config.name} is not warned`).not.toContain(warning.message);
      }
    }
  });

  it("X-9: a run with no warning shows no badge", async () => {
    const clean: Schemas["TradeLabResult"] = { ...LAB, warnings: [] };
    server.use(http.post("*/api/v1/backtest", () => HttpResponse.json(clean)));
    await runLab();
    for (const warning of warnings) {
      expect(screen.queryByText(warning.message)).not.toBeInTheDocument();
    }
  });
});

// ------------------------------------------------------------------ U-3 the lab's assumptions

describe("U-3 the exit lab report's assumptions header", () => {
  function header(): HTMLElement {
    return screen.getByRole("region", { name: "Assumptions" });
  }

  function pairs(): [string, string][] {
    return within(header())
      .getAllByRole("term")
      .map((dt) => {
        const dd = dt.nextElementSibling;
        expect(dd?.tagName, `no value after "${text(dt)}"`).toBe("DD");
        return [text(dt), text(dd!)] as [string, string];
      });
  }

  function valueOf(label: RegExp): string {
    const hits = pairs().filter(([term]) => label.test(term));
    expect(
      hits.map(([t]) => t),
      `exactly one term matching ${label}`,
    ).toHaveLength(1);
    return hits[0][1];
  }

  it("U-3: the lab report opens with an Assumptions header before the table", async () => {
    await runLab();
    const after = header().compareDocumentPosition(table());
    expect(after & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("U-3: one line per Assumptions field of the trade mode response (AC-12)", async () => {
    await runLab();
    const listed = pairs();
    expect(listed).toHaveLength(Object.keys(LAB.assumptions).length);
    for (const [term, value] of listed) {
      expect(term, "an empty label").not.toBe("");
      expect(value, `"${term}" has no value`).not.toBe("");
    }
  });

  it("U-3: every doc 01 item is listed with the trade mode value (AC-19)", async () => {
    await runLab();
    const a = LAB.assumptions;
    expect(valueOf(/fill model/i)).toMatch(/close/i);
    expect(valueOf(/fill model/i)).toMatch(/next open/i);
    expect(valueOf(/slippage/i)).toMatch(new RegExp(`\\b${a.slippage_bps}\\b`));
    // Trade mode sizes one unit of notional per trade and caps nothing.
    expect(valueOf(/sizing/i)).toMatch(/unit|notional/i);
    expect(valueOf(/max(imum)? positions/i)).toBe(NOT_USED);
    expect(valueOf(/^entry$/i)).toMatch(/rising edge/i);
    expect(valueOf(/^cooldown$/i)).toMatch(new RegExp(`\\b${a.cooldown_bars}\\b`));
    expect(valueOf(/last bar/i)).toMatch(/never|no|none/i);
    // The horizon, the seed and the overlap rule are stated (AC-19).
    expect(valueOf(/horizon/i)).toMatch(new RegExp(`\\b${a.horizon_bars}\\b`));
    expect(valueOf(/random seed|^seed$/i)).toMatch(new RegExp(`\\b${a.seed}\\b`));
    expect(valueOf(/overlap/i)).toMatch(/same ticker/i);
    // One exit rule line per config, each named.
    const exits = valueOf(/exit rules/i);
    for (const config of CONFIGS) expect(exits).toContain(config.name);
    expect(exits).toMatch(/\b8(\.0+)?%/); // Baseline's stop
    expect(exits).toMatch(/\b20\b/); // Baseline's time exit
    expect(valueOf(/baseline config/i)).toMatch(/\b1\b/);
    expect(valueOf(/delist/i)).toMatch(/last close/i);
    expect(valueOf(/out of sample from/i)).toBe(a.oos_start);
    expect(valueOf(/data mode/i)).toBe(a.data_mode);
    expect(valueOf(/data version/i)).toBe(a.data_version);
    expect(valueOf(/data seed/i)).toBe(String(a.data_seed));
  });

  it("U-3: the header echoes the response, not the form", async () => {
    const distinct: Schemas["TradeLabResult"] = {
      ...LAB,
      assumptions: {
        ...LAB.assumptions,
        slippage_bps: 25,
        horizon_bars: 90,
        seed: 7,
        oos_start: "2023-03-15",
        data_version: "synthetic:v1:seed7",
        data_seed: 7,
      },
      oos_start: "2023-03-15",
    };
    server.use(http.post("*/api/v1/backtest", () => HttpResponse.json(distinct)));
    await runLab();
    expect(valueOf(/slippage/i)).toMatch(/\b25\b/);
    expect(valueOf(/horizon/i)).toMatch(/\b90\b/);
    expect(valueOf(/random seed|^seed$/i)).toMatch(/\b7\b/);
    expect(valueOf(/out of sample from/i)).toBe("2023-03-15");
    expect(valueOf(/data version/i)).toBe("synthetic:v1:seed7");
  });
});

// ------------------------------------------------------------------ U-4 the counter in a report

describe("U-4 the trial counter in the reports", () => {
  function counterLine(n: number, m: number): string {
    return `Trial #${n} for this rule structure · ${m} this session`;
  }

  it("U-4: the exit lab report shows the counter beside the assumptions header (AC-18)", async () => {
    await runLab();
    const k = LAB.trial.pair_keys.length;
    const line = await screen.findByText(counterLine(k, k));
    expect(line).toBeVisible();
    // Beside the header, not buried in the table (spec 0009 AC-18).
    expect(screen.getByRole("region", { name: "Assumptions" }).contains(line)).toBe(true);
    expect(table().contains(line)).toBe(false);
  });

  it("U-4: the lab run records one pair per config under the spec 0004 keys", async () => {
    await runLab();
    const k = LAB.trial.pair_keys.length;
    await screen.findByText(counterLine(k, k));
    const stored = JSON.parse(
      localStorage.getItem(LOCAL_PREFIX + LAB.trial.structure_key) ?? "null",
    ) as string[];
    expect(new Set(stored)).toEqual(new Set(LAB.trial.pair_keys));
    expect(new Set(JSON.parse(sessionStorage.getItem(SESSION_KEY) ?? "null") as string[])).toEqual(
      new Set(LAB.trial.pair_keys),
    );
  });

  it("U-4: a failed run adds no count and shows no counter", async () => {
    server.use(
      http.post("*/api/v1/backtest", () =>
        HttpResponse.json({ detail: "engine exploded" }, { status: 500 }),
      ),
    );
    nav.set("", "/backtest");
    renderPage(BacktestPage);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("radio", { name: /exit lab/i }, { timeout: 3000 }));
    await user.click(screen.getByRole("button", { name: /^Run exit lab$/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument(), { timeout: 5000 });
    expect(screen.queryByText(/Trial #/)).not.toBeInTheDocument();
    expect(screen.queryByText(/this session/)).not.toBeInTheDocument();
    expect(localStorage.getItem(LOCAL_PREFIX + LAB.trial.structure_key)).toBeNull();
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("U-4: a 422 on the form adds no count", async () => {
    server.use(
      http.post("*/api/v1/backtest", () =>
        HttpResponse.json(
          {
            detail: [
              {
                type: "out_of_range",
                loc: ["body", "configs", 0, "exits", 0, "stop_pct", "pct"],
                msg: "must be between 1 and 30",
                input: 40,
                ctx: { min: 1, max: 30 },
              },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    nav.set("", "/backtest");
    renderPage(BacktestPage);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("radio", { name: /exit lab/i }, { timeout: 3000 }));
    await user.click(screen.getByRole("button", { name: /^Run exit lab$/i }));
    await waitFor(() =>
      expect(
        within(screen.getByRole("group", { name: /^Config 1/ })).getByLabelText("Stop loss (%)"),
      ).toHaveAttribute("aria-invalid", "true"),
    );
    expect(screen.queryByText(/Trial #/)).not.toBeInTheDocument();
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });
});

// ------------------------------------------------------------------ U-7 422 on a lab exit field

describe("U-7 a 422 lands on the exit lab config and field it names", () => {
  it("U-7: a 422 on config 3's stop lands on that config's Stop loss (%) only", async () => {
    // The real API names the config, the exit index and the exit's type in the path:
    // configs.2.exits.<i>.stop_pct.pct (spec 0009 AC-20, doc 01 U-7).
    server.use(
      http.post("*/api/v1/backtest", async ({ request }) => {
        const body = (await request.json()) as Schemas["BacktestRequest"];
        const exits = body.configs[2]?.exits ?? [];
        const at = exits.findIndex((e) => e.type === "stop_pct");
        if (at < 0) return HttpResponse.json(LAB);
        return HttpResponse.json(
          {
            detail: [
              {
                type: "out_of_range",
                loc: ["body", "configs", 2, "exits", at, "stop_pct", "pct"],
                msg: "must be between 1 and 30",
                input: (exits[at] as { pct: number }).pct,
                ctx: { min: 1, max: 30 },
              },
            ],
          },
          { status: 422 },
        );
      }),
    );
    nav.set("", "/backtest");
    renderPage(BacktestPage);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("radio", { name: /exit lab/i }, { timeout: 3000 }));

    const third = screen.getByRole("group", { name: /^Config 3/ });
    const field = within(third).getByLabelText("Stop loss (%)");
    await user.clear(field);
    await user.type(field, "40");
    await user.click(screen.getByRole("button", { name: /^Run exit lab$/i }));

    await waitFor(() => expect(field).toHaveAttribute("aria-invalid", "true"), { timeout: 5000 });
    expect(field).toHaveAccessibleDescription(/between 1 and 30/i);
    // No other config, and no other field of config 3, is marked.
    for (const legend of ["Config 1", "Config 2", "Config 4", "Config 5"]) {
      const group = screen.getByRole("group", { name: new RegExp(`^${legend}`) });
      expect(
        within(group).getByLabelText("Stop loss (%)"),
        `${legend} is not marked`,
      ).not.toHaveAttribute("aria-invalid", "true");
    }
    expect(within(third).getByLabelText("Target (%)")).not.toHaveAttribute("aria-invalid", "true");
    expect(within(third).getByLabelText("Time exit (bars)")).not.toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });
});

// ------------------------------------------------------------------ U-8 the note under the table

describe("U-8 the procedure note under the exit lab table", () => {
  it("U-8: the note sits directly under the exit lab table, word for word", async () => {
    await runLab();
    const note = screen.getByText(PROCEDURE_NOTE);
    expect(note).toBeVisible();
    const box = screen.getByRole("region", { name: /in sample beside out of sample/i });
    expect(box.contains(note), "the note is outside the table's scroll box").toBe(false);
    expect(box.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Directly under: the first thing after the table, with nothing between (spec 0009 AC-18).
    expect(box.nextElementSibling?.contains(note)).toBe(true);
  });

  it("U-8: the note is one line of body text, not fine print", async () => {
    await runLab();
    const note = screen.getByText(PROCEDURE_NOTE);
    expect(note.className).not.toMatch(/\btext-(xs|\[1[01]px\])\b/);
    expect(note.textContent).not.toMatch(/\n/);
  });
});

// QA acceptance: the template scan workspace on `/` (scope feature 8), from doc 01 U-1, U-5,
// R-10, S-1 and spec 0005 AC-9 to AC-13. Written against the mocks and Next's public
// `next/navigation` hooks; the workspace's own code is not read.
//
// Feature 8's UI is not on `main` yet, so every test here goes through `acIt`: while its IDs are
// `pending` in tests/acceptance/status.yaml a failure is reported as skipped, not failed.
import type { Rule, ScanResponse } from "@swing-scan/api-client";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, vi } from "vitest";

import Home from "@/app/page";
import { formatDate } from "@/lib/format";
import { mocks, scanHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";

import { acIt } from "./gate";
import { nav } from "./navigation";
import { renderPage, SYNTHETIC_BANNER, WARMUP_TEXT } from "./pages";

// ------------------------------------------------------------------ next/navigation, emulated

// Shared with the other page tests (`navigation.ts`); see ac-questions.md#AC-10-url.
vi.mock("next/navigation", async (importOriginal) =>
  (await import("./navigation")).emulatedNavigation(await importOriginal<object>()),
);

// ------------------------------------------------------------------ fixtures and helpers

const [BREAKOUT, PULLBACK] = mocks.templates;
const HITS_TITLE = `Hits on ${formatDate(mocks.scan.as_of)}`;

/** Spec 0005 value sourcing: each operand as its column label, numbers plain. */
const CONDITIONS: Record<string, string[]> = {
  breakout_52w: ["close > highest(252)[1]", "volume > 1.5×avg_volume(50)", "close > 5"],
  pullback_ema21: [
    "ema(21) > ema(21)[5]",
    "close > sma(50)",
    "low <= 1.01×ema(21)",
    "close > ema(21)",
    "close > 5",
  ],
};

let scanBodies: { rule: Rule; as_of?: string }[] = [];

function recordScans(body: ScanResponse = mocks.scan, init: { delayMs?: number } = {}) {
  server.use(
    http.post("*/api/v1/scan", async ({ request }) => {
      scanBodies.push((await request.json()) as { rule: Rule });
      if (init.delayMs) await new Promise((r) => setTimeout(r, init.delayMs));
      return HttpResponse.json(body);
    }),
  );
}

/** History entries when the page opened; AC-10 updates the URL without adding any. */
let openedHistoryLength = 0;

function openAt(search = "") {
  nav.set(search);
  openedHistoryLength = window.history.length;
  return renderPage(Home);
}

function norm(text: string | null | undefined): string {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

/** The smallest element whose whole text is `text` (the conditions may be split into spans). */
function findExactText(text: string): HTMLElement | undefined {
  const all = Array.from(document.body.querySelectorAll<HTMLElement>("*"));
  return all.find(
    (el) =>
      norm(el.textContent) === text &&
      !Array.from(el.children).some((c) => norm(c.textContent) === text),
  );
}

async function templateBox(): Promise<HTMLElement> {
  return screen.findByRole("combobox", { name: /template/i }, { timeout: 2000 });
}

function selectedText(box: HTMLElement): string {
  return box instanceof HTMLSelectElement
    ? norm(box.selectedOptions[0]?.textContent)
    : norm(box.textContent);
}

async function chooseTemplate(name: string) {
  const user = userEvent.setup();
  const box = await templateBox();
  if (box instanceof HTMLSelectElement) {
    const option = within(box).getByRole("option", { name });
    await user.selectOptions(box, option);
    return;
  }
  await user.click(box);
  await user.click(await screen.findByRole("option", { name }));
}

/** `?template` in the address bar right now. */
function urlTemplate(): string | null {
  return new URLSearchParams(window.location.search).get("template");
}

async function resultsTable(): Promise<HTMLElement> {
  const tables = await screen.findAllByRole("table", {}, { timeout: 2000 });
  return tables[0];
}

function bodyRows(table: HTMLElement): HTMLElement[] {
  return within(table)
    .getAllByRole("row")
    .filter((row) => within(row).queryAllByRole("columnheader").length === 0);
}

beforeEach(() => {
  scanBodies = [];
});

// ------------------------------------------------------------------ U-1 first visit

describe("U-1 first visit opens Breakout with its results", () => {
  acIt(["U-1"], "U-1: / opens on Breakout, its scan results and the synthetic banner", async () => {
    recordScans();
    openAt();
    const box = await templateBox();
    expect(selectedText(box)).toContain(BREAKOUT.name);
    expect(await screen.findByText(HITS_TITLE, {}, { timeout: 2000 })).toBeVisible();
    const table = await resultsTable();
    await waitFor(() => expect(bodyRows(table)).toHaveLength(mocks.scan.rows.length));
    expect(scanBodies).toHaveLength(1);
    expect(scanBodies[0].rule).toEqual(BREAKOUT.rule);
    expect(scanBodies[0].as_of).toBeUndefined(); // AC-6: the web app never sends as_of
    const main = screen.getByRole("main");
    expect(main.firstElementChild).toHaveTextContent(SYNTHETIC_BANNER);
    expect(screen.queryByText(/sign up|log in|sign in/i)).not.toBeInTheDocument();
  });

  acIt(["U-1"], "U-1: a link to ?template=pullback_ema21 opens Pullback and scans it", async () => {
    recordScans();
    openAt("?template=pullback_ema21");
    await waitFor(async () => expect(selectedText(await templateBox())).toContain(PULLBACK.name));
    await waitFor(() => expect(scanBodies.length).toBeGreaterThan(0));
    expect(scanBodies.every((b) => JSON.stringify(b.rule) === JSON.stringify(PULLBACK.rule))).toBe(
      true,
    );
  });

  acIt(
    ["U-1"],
    "U-1: an unknown ?template falls back to Breakout and drops the parameter",
    async () => {
      recordScans();
      openAt("?template=nope");
      await waitFor(async () => expect(selectedText(await templateBox())).toContain(BREAKOUT.name));
      await waitFor(() => expect(window.location.search).toBe(""));
      expect(urlTemplate()).toBeNull();
      expect(window.history.length).toBe(openedHistoryLength); // replaced, not pushed
      await waitFor(() => expect(scanBodies.length).toBeGreaterThan(0));
      expect(scanBodies.at(-1)?.rule).toEqual(BREAKOUT.rule);
    },
  );

  acIt(["U-1"], "U-1: no scan runs until the templates have loaded", async () => {
    recordScans();
    let release: () => void = () => {};
    const held = new Promise<void>((r) => (release = r));
    server.use(
      http.get("*/api/v1/templates", async () => {
        await held;
        return HttpResponse.json(mocks.templates);
      }),
    );
    openAt("?template=pullback_ema21");
    await new Promise((r) => setTimeout(r, 300));
    expect(scanBodies).toHaveLength(0);
    release();
    // Once they load, the shared link scans Pullback only: no wasted Breakout scan first.
    await waitFor(() => expect(scanBodies.length).toBeGreaterThan(0), { timeout: 2000 });
    expect(scanBodies.map((b) => JSON.stringify(b.rule))).toEqual(
      scanBodies.map(() => JSON.stringify(PULLBACK.rule)),
    );
  });

  acIt(["U-1"], "U-1: switching templates rewrites ?template in place and scans it", async () => {
    // Each template answers with its own tickers, so the rows on screen show which scan they
    // are. Switching back to a template already scanned may be served from the query cache
    // (the market is fixed, so the answer is the same): the test checks the rows the user
    // sees, not that a second request went out (ac-questions.md#AC-10-url).
    const rowsFor = (prefix: string) =>
      mocks.scan.rows.map((row, i) => ({ ...row, ticker: `${prefix}${i}` }));
    const answers: Record<string, ScanResponse> = {
      [JSON.stringify(BREAKOUT.rule)]: { ...mocks.scan, rows: rowsFor("BRK") },
      [JSON.stringify(PULLBACK.rule)]: { ...mocks.scan, rows: rowsFor("PUL") },
    };
    server.use(
      http.post("*/api/v1/scan", async ({ request }) => {
        const body = (await request.json()) as { rule: Rule };
        scanBodies.push(body);
        const answer = answers[JSON.stringify(body.rule)];
        return answer ? HttpResponse.json(answer) : HttpResponse.json({}, { status: 500 });
      }),
    );
    const firstTicker = async () => {
      const rows = bodyRows(await resultsTable());
      return norm(rows[0]?.textContent);
    };
    openAt();
    await screen.findByText(HITS_TITLE, {}, { timeout: 2000 });
    await waitFor(async () => expect(await firstTicker()).toContain("BRK0"));

    await chooseTemplate(PULLBACK.name);
    await waitFor(() => expect(urlTemplate()).toBe("pullback_ema21"));
    expect(window.history.length).toBe(openedHistoryLength); // no new history entry
    await waitFor(() => expect(scanBodies.at(-1)?.rule).toEqual(PULLBACK.rule));
    await waitFor(async () => expect(await firstTicker()).toContain("PUL0"));

    await chooseTemplate(BREAKOUT.name);
    await waitFor(() => expect(urlTemplate()).toBeNull()); // Breakout has no parameter
    expect(window.history.length).toBe(openedHistoryLength);
    await waitFor(async () => expect(await firstTicker()).toContain("BRK0"));
    expect(scanBodies.every((b) => JSON.stringify(b.rule) in answers)).toBe(true);
  });

  acIt(["U-1"], "U-1: a failed templates request shows Try again, which refetches", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/templates", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ detail: "boom" }, { status: 500 })
          : HttpResponse.json(mocks.templates);
      }),
    );
    recordScans();
    openAt();
    const retry = await screen.findByRole("button", { name: /try again/i }, { timeout: 8000 });
    await userEvent.setup().click(retry);
    await waitFor(() => expect(calls).toBe(2));
    expect(await templateBox()).toBeInTheDocument();
  });
});

// ------------------------------------------------------------------ R-10 visible price filter

describe("R-10 the conditions text shows every condition", () => {
  acIt(["R-10"], "R-10: Breakout's conditions read as text, including close > 5", async () => {
    recordScans();
    openAt();
    await templateBox();
    for (const line of CONDITIONS.breakout_52w) {
      await waitFor(() => expect(findExactText(line), line).toBeDefined());
    }
  });

  acIt(["R-10"], "R-10: Pullback's conditions read as text, including close > 5", async () => {
    recordScans();
    openAt("?template=pullback_ema21");
    await templateBox();
    for (const line of CONDITIONS.pullback_ema21) {
      await waitFor(() => expect(findExactText(line), line).toBeDefined());
    }
  });
});

// ------------------------------------------------------------------ S-1 results table

describe("S-1 the results table", () => {
  acIt(["S-1"], "S-1: one column per operand, close not repeated, and a New column", async () => {
    recordScans();
    openAt();
    const table = await resultsTable();
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => norm(h.textContent));
    for (const label of ["highest(252)[1]", "volume", "1.5×avg_volume(50)"]) {
      expect(
        headers.some((h) => h.includes(label)),
        label,
      ).toBe(true);
    }
    expect(headers.filter((h) => /^close\b/i.test(h))).toHaveLength(1);
    expect(headers.some((h) => /ticker/i.test(h))).toBe(true);
    expect(headers.some((h) => /change/i.test(h))).toBe(true);
    expect(headers.some((h) => /vol(ume)? ratio/i.test(h))).toBe(true);
    expect(headers.some((h) => /^new\b/i.test(h))).toBe(true);
  });

  acIt(
    ["S-1"],
    "S-1: rows keep the server's order and the new_today rows carry a New badge",
    async () => {
      recordScans();
      openAt();
      const table = await resultsTable();
      await waitFor(() => expect(bodyRows(table)).toHaveLength(mocks.scan.rows.length));
      const rows = bodyRows(table);
      mocks.scan.rows.forEach((row, i) => {
        expect(rows[i]).toHaveTextContent(row.ticker);
        const badge = within(rows[i]).queryByText(/^new$/i);
        if (row.new_today) expect(badge, row.ticker).toBeInTheDocument();
        else expect(badge, row.ticker).not.toBeInTheDocument();
      });
    },
  );

  acIt(["S-1"], "S-1: the table pages at 50 rows", async () => {
    const rows = Array.from({ length: 120 }, (_, i) => ({
      ...mocks.scan.rows[i % mocks.scan.rows.length],
      ticker: `T${String(i).padStart(3, "0")}`,
    }));
    recordScans({ ...mocks.scan, rows });
    openAt();
    const table = await resultsTable();
    await waitFor(() => expect(bodyRows(table)).toHaveLength(50));
  });

  acIt(["S-1"], "S-1: zero hits shows the empty state with a hint", async () => {
    recordScans(mocks.scanEmpty);
    openAt();
    expect(
      await screen.findByText(
        `No hits on ${formatDate(mocks.scanEmpty.as_of)}`,
        {},
        { timeout: 2000 },
      ),
    ).toBeVisible();
    expect(screen.getByText(/Try the other template\./)).toBeVisible();
  });

  acIt(["S-1"], "S-1: a failed scan shows Try again, which runs the scan again", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/v1/scan", () => {
        calls += 1;
        return calls === 1 ? HttpResponse.error() : HttpResponse.json(mocks.scan);
      }),
    );
    openAt();
    const retry = await screen.findByRole("button", { name: /try again/i }, { timeout: 8000 });
    await userEvent.setup().click(retry);
    await waitFor(() => expect(calls).toBe(2));
    expect(await screen.findByText(HITS_TITLE, {}, { timeout: 2000 })).toBeVisible();
  });

  acIt(["S-1"], "S-1: a 501 shows Not built yet with no retry", async () => {
    server.use(scanHandler("501.scan"));
    openAt();
    const alert = await screen.findByText(/not built yet/i, {}, { timeout: 2000 });
    const box = alert.closest('[role="alert"]') ?? alert.parentElement!;
    expect(within(box as HTMLElement).queryByRole("button", { name: /try again/i })).toBeNull();
  });
});

// ------------------------------------------------------------------ U-5 warming up

describe("U-5 a slow scan shows the warm up notice", () => {
  acIt(
    ["U-5"],
    "U-5: a scan pending over 1.5 s shows Warming up the engine…",
    async () => {
      recordScans(mocks.scan, { delayMs: 2500 });
      openAt();
      await templateBox();
      expect(await screen.findByText(WARMUP_TEXT, {}, { timeout: 2400 })).toBeVisible();
      expect(await screen.findByText(HITS_TITLE, {}, { timeout: 2000 })).toBeVisible();
      await waitFor(() => expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument());
    },
    10_000,
  );
});

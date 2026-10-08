// QA acceptance: U-4 (trial counter) and U-8 (procedure note), from doc 01 section 6.6 and
// spec 0004 AC-1 to AC-7, AC-9. Written against the components' documented use
// (`<RunTrialCounter trial={result.trial} />`, `<ProcedureNote />`, apps/web/AGENTS.md), the
// storage layout spec 0004 fixes, the `trial` block of the backtest mocks, and the /ui gallery.
// U-2 (spec 0004 AC-8) is the shell banner, covered in data-mode-banner.test.tsx.
//
// Not covered yet (the pages do not exist, so these stay `it.todo` and the IDs stay pending):
// the counter inside the portfolio report (feature 9) and the exit lab report (feature 12), and
// the procedure note directly under the exit lab table (feature 12).
import type { Schemas } from "@swing-scan/api-client";
import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import UiGalleryPage from "@/app/ui/page";
import { ProcedureNote, RunTrialCounter } from "@/features/honesty";
import { mocks } from "@/mocks/handlers";

import { renderPage } from "./pages";

/** Doc 01 U-4, word for word. */
const OVERFIT_WARNING =
  "You've tested many variants of this rule structure; the best IS result is likely overfit. " +
  "Read OOS once and treat the result as a hypothesis.";

/** Doc 01 U-8, word for word. */
const PROCEDURE_NOTE =
  "Trade mode isolates the exit effect. Pick the exit on IS, read OOS once, then confirm with " +
  "a single portfolio backtest.";

/** Spec 0004, assumption 3. */
const LOCAL_PREFIX = "swing-scan:trials:v1:";
const SESSION_KEY = "swing-scan:session-trials:v1";

const STRUCTURE_A = mocks.backtestPortfolio.trial.structure_key;
const STRUCTURE_B = "b".repeat(64);

function pair(n: number): string {
  return n.toString(16).padStart(64, "0");
}

function trial(structureKey: string, ...pairKeys: string[]): Schemas["Trial"] {
  return { structure_key: structureKey, pair_keys: pairKeys };
}

function counterLine(n: number, m: number): string {
  return `Trial #${n} for this rule structure · ${m} this session`;
}

/** Each completed run mounts a fresh counter for that result, as a report would. */
function completeRun(keys: Schemas["Trial"]) {
  return render(<RunTrialCounter trial={keys} />);
}

function readJson(storage: Storage, key: string): unknown {
  const raw = storage.getItem(key);
  return raw === null ? null : (JSON.parse(raw) as unknown);
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("U-4 trial counter", () => {
  it("U-4: a first run reads Trial #1 · 1 this session, in a polite live region (AC-4)", async () => {
    completeRun(mocks.backtestPortfolio.trial);
    const line = await screen.findByText(counterLine(1, 1));
    const region = line.closest('[aria-live="polite"], [role="status"]');
    expect(region).not.toBeNull();
    if (region?.getAttribute("aria-live") !== null) {
      expect(region?.getAttribute("aria-live")).toBe("polite");
    }
    expect(screen.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
  });

  it("U-4: a numbers only tweak (same structure key, new pair) adds to the same N (AC-1)", async () => {
    completeRun(trial(STRUCTURE_A, pair(1))).unmount();
    completeRun(trial(STRUCTURE_A, pair(2)));
    expect(await screen.findByText(counterLine(2, 2))).toBeInTheDocument();
  });

  it("U-4: re running an identical pair adds nothing to N or M (AC-2)", async () => {
    completeRun(trial(STRUCTURE_A, pair(1))).unmount();
    completeRun(trial(STRUCTURE_A, pair(2))).unmount();
    completeRun(trial(STRUCTURE_A, pair(1)));
    expect(await screen.findByText(counterLine(2, 2))).toBeInTheDocument();
  });

  it("U-4: a re render of the same result never double counts", async () => {
    const keys = trial(STRUCTURE_A, pair(1));
    const view = completeRun(keys);
    await screen.findByText(counterLine(1, 1));
    view.rerender(<RunTrialCounter trial={{ ...keys }} />);
    view.rerender(<RunTrialCounter trial={{ ...keys }} />);
    expect(await screen.findByText(counterLine(1, 1))).toBeInTheDocument();
  });

  it("U-4: M counts distinct pairs across every structure key; N is per structure (AC-3)", async () => {
    completeRun(trial(STRUCTURE_A, pair(1))).unmount();
    completeRun(trial(STRUCTURE_A, pair(2))).unmount();
    completeRun(trial(STRUCTURE_B, pair(3)));
    expect(await screen.findByText(counterLine(1, 3))).toBeInTheDocument();
  });

  it("U-4: an exit lab run with k configs records k pairs", async () => {
    const lab = mocks.backtestTradeLab.trial;
    expect(lab.pair_keys.length).toBeGreaterThan(1);
    completeRun(lab);
    const k = lab.pair_keys.length;
    expect(await screen.findByText(counterLine(k, k))).toBeInTheDocument();
  });

  it("U-4: N lives in localStorage and M in sessionStorage, under the spec 0004 keys", async () => {
    completeRun(trial(STRUCTURE_A, pair(1))).unmount();
    completeRun(trial(STRUCTURE_B, pair(2)));
    await screen.findByText(counterLine(1, 2));
    expect(readJson(localStorage, LOCAL_PREFIX + STRUCTURE_A)).toEqual([pair(1)]);
    expect(readJson(localStorage, LOCAL_PREFIX + STRUCTURE_B)).toEqual([pair(2)]);
    expect(new Set(readJson(sessionStorage, SESSION_KEY) as string[])).toEqual(
      new Set([pair(1), pair(2)]),
    );
  });

  it("U-4: N survives a new session; an old pair counts toward M once, not toward N", async () => {
    // An earlier session saw pairs 1 and 2 for this structure; this session is new.
    localStorage.setItem(LOCAL_PREFIX + STRUCTURE_A, JSON.stringify([pair(1), pair(2)]));
    completeRun(trial(STRUCTURE_A, pair(1)));
    expect(await screen.findByText(counterLine(2, 1))).toBeInTheDocument();
  });

  it("U-4: the warning is absent at N = 9 (AC-5)", async () => {
    const seen = Array.from({ length: 8 }, (_, i) => pair(i + 1));
    localStorage.setItem(LOCAL_PREFIX + STRUCTURE_A, JSON.stringify(seen));
    completeRun(trial(STRUCTURE_A, pair(9)));
    await screen.findByText(counterLine(9, 1));
    expect(screen.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
  });

  it("U-4: at N = 10 the overfit warning shows word for word (AC-5)", async () => {
    const seen = Array.from({ length: 9 }, (_, i) => pair(i + 1));
    localStorage.setItem(LOCAL_PREFIX + STRUCTURE_A, JSON.stringify(seen));
    completeRun(trial(STRUCTURE_A, pair(10)));
    expect(await screen.findByText(counterLine(10, 1))).toBeInTheDocument();
    expect(screen.getByText(OVERFIT_WARNING)).toBeVisible();
  });

  it("U-4: the warning stays above 10, and builds up from runs alone", async () => {
    for (let i = 1; i <= 11; i += 1) {
      completeRun(trial(STRUCTURE_A, pair(i))).unmount();
    }
    completeRun(trial(STRUCTURE_A, pair(12)));
    expect(await screen.findByText(counterLine(12, 12))).toBeInTheDocument();
    expect(screen.getByText(OVERFIT_WARNING)).toBeVisible();
  });

  it("U-4: a stored value that does not parse is treated as empty, not as unavailable", async () => {
    localStorage.setItem(LOCAL_PREFIX + STRUCTURE_A, "{not json");
    sessionStorage.setItem(SESSION_KEY, "[[[");
    completeRun(trial(STRUCTURE_A, pair(1)));
    expect(await screen.findByText(counterLine(1, 1))).toBeInTheDocument();
    expect(screen.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
  });

  it.each([
    ["localStorage", () => localStorage],
    ["sessionStorage", () => sessionStorage],
  ])(
    "U-4: with %s throwing, the counter is hidden and the static warning shows (AC-6)",
    async (_name, store) => {
      const target = store();
      const boom = () => {
        throw new DOMException("blocked", "SecurityError");
      };
      vi.spyOn(Storage.prototype, "getItem").mockImplementation(function (this: Storage, key) {
        if (this === target) boom();
        return Object.getOwnPropertyDescriptor(Storage.prototype, "getItem")!.value.call(
          this,
          key,
        ) as string | null;
      });
      vi.spyOn(Storage.prototype, "setItem").mockImplementation(boom);
      completeRun(trial(STRUCTURE_A, pair(1)));
      expect(await screen.findByText(OVERFIT_WARNING)).toBeVisible();
      expect(screen.queryByText(/Trial #/)).not.toBeInTheDocument();
      expect(screen.queryByText(/this session/)).not.toBeInTheDocument();
    },
  );

  it.todo(
    "U-4: the portfolio report shows the counter once a 200 backtest is on screen (feature 9)",
  );
  it.todo("U-4: the exit lab report shows the counter near the assumptions header (feature 12)");
  it.todo("U-4: a failed or 422 backtest never adds to the counter (features 9, 12)");
});

describe("U-8 procedure note", () => {
  it("U-8: the note renders word for word as one line of body text (AC-7)", () => {
    render(<ProcedureNote />);
    const note = screen.getByText(PROCEDURE_NOTE);
    expect(note).toBeVisible();
    // One line of body text, never fine print (spec 0004, assumption 5).
    expect(note.className).not.toMatch(/\btext-(xs|\[1[01]px\])\b/);
    expect(note.textContent).not.toMatch(/\n/);
  });

  it.todo("U-8: the note sits directly under the exit lab table (feature 12)");
});

describe("U-4 and U-8 in the /ui gallery (spec 0004 AC-9)", () => {
  function section(name: RegExp): HTMLElement {
    const heading = screen.getByRole("heading", { name });
    return heading.closest("section") ?? (heading.parentElement as HTMLElement);
  }

  it("U-4: the gallery shows the first, counting, warning and unavailable states", async () => {
    renderPage(UiGalleryPage);
    await screen.findByText(/API ready/);
    const guards = section(/Research honesty guards/);
    expect(
      within(guards).getAllByText(/^Trial #\d+ for this rule structure · \d+ this session$/).length,
    ).toBeGreaterThanOrEqual(3);
    expect(within(guards).getAllByText(OVERFIT_WARNING).length).toBeGreaterThanOrEqual(2);
  });

  it("U-8: the gallery shows the procedure note word for word", async () => {
    renderPage(UiGalleryPage);
    await screen.findByText(/API ready/);
    expect(screen.getByText(PROCEDURE_NOTE)).toBeVisible();
  });
});

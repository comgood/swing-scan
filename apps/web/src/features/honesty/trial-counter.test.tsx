import { render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";
import { expectNoAxeViolations } from "@/test/axe";

import { blockedStores, memoryStores } from "./memory-stores";
import {
  OVERFIT_WARNING,
  RunTrialCounter,
  TrialCounter,
  trialCounterText,
  trialDataText,
} from "./trial-counter";
import { TRIAL_DATA_KEY_PREFIX, TRIAL_KEY_PREFIX, type Trial } from "./trial-store";
import type { TrialCountState } from "./use-trial-count";

const STRUCTURE = "c".repeat(64);
const trial = (...pairs: string[]): Trial => ({ structure_key: STRUCTURE, pair_keys: pairs });
const DATA_END = "2025-01-31";
const NEWER_DATA_END = "2025-02-03";

describe("TrialCounter (U-4)", () => {
  it("uses the U-4 wording word for word (AC-4, AC-5)", () => {
    expect(trialCounterText(3, 7)).toBe("Trial #3 for this rule structure · 7 this session");
    expect(OVERFIT_WARNING).toBe(
      "You've tested many variants of this rule structure; the best IS result is likely overfit. Read OOS once and treat the result as a hypothesis.",
    );
  });

  it("shows the counter line without a warning below 10", () => {
    render(
      <TrialCounter
        state={{ status: "counted", count: { trialNumber: 9, sessionTotal: 12 }, dataEnds: [] }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Trial #9 for this rule structure · 12 this session",
    );
    expect(screen.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
  });

  it("shows the overfit warning at 10 (AC-5)", () => {
    render(
      <TrialCounter
        state={{ status: "counted", count: { trialNumber: 10, sessionTotal: 10 }, dataEnds: [] }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Trial #10 for this rule structure");
    expect(screen.getByText(OVERFIT_WARNING)).toBeInTheDocument();
  });

  it("hides the counters and shows the static warning when storage is unavailable (AC-6)", () => {
    render(<TrialCounter state={{ status: "unavailable" }} />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    expect(screen.queryByText(/Trial #/)).not.toBeInTheDocument();
    expect(screen.getByText(OVERFIT_WARNING)).toBeInTheDocument();
  });

  it("shows nothing but an empty live region while pending", () => {
    render(<TrialCounter state={{ status: "pending" }} />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    expect(screen.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
  });

  it.each([
    { status: "counted", count: { trialNumber: 2, sessionTotal: 2 }, dataEnds: [] },
    { status: "counted", count: { trialNumber: 12, sessionTotal: 30 }, dataEnds: [DATA_END] },
    { status: "unavailable" },
  ] as TrialCountState[])("passes axe for %o", async (state) => {
    const { container } = render(<TrialCounter state={state} />);
    await expectNoAxeViolations(container);
  });
});

describe("RunTrialCounter (U-4, spec 0004)", () => {
  it("records a run and shows trial 1 of 1", async () => {
    render(<RunTrialCounter dataEnd={DATA_END} trial={trial("p1")} stores={memoryStores()} />);
    expect(
      await screen.findByText("Trial #1 for this rule structure · 1 this session"),
    ).toBeVisible();
  });

  it("counts once under strict mode's double effect", async () => {
    render(
      <StrictMode>
        <RunTrialCounter dataEnd={DATA_END} trial={trial("p1", "p2")} stores={memoryStores()} />
      </StrictMode>,
    );
    expect(
      await screen.findByText("Trial #2 for this rule structure · 2 this session"),
    ).toBeVisible();
  });

  it("adds a numbers only tweak to the same rule's count, and not a re run (AC-1, AC-2)", async () => {
    const stores = memoryStores();
    const { rerender } = render(
      <RunTrialCounter dataEnd={DATA_END} trial={trial("n252")} stores={stores} />,
    );
    await screen.findByText(/Trial #1 /);
    rerender(<RunTrialCounter dataEnd={DATA_END} trial={trial("n100")} stores={stores} />);
    expect(
      await screen.findByText("Trial #2 for this rule structure · 2 this session"),
    ).toBeVisible();
    rerender(<RunTrialCounter dataEnd={DATA_END} trial={trial("n252")} stores={stores} />);
    expect(
      await screen.findByText("Trial #2 for this rule structure · 2 this session"),
    ).toBeVisible();
  });

  it("shows the warning once the tenth distinct pair is recorded (AC-5)", async () => {
    const stores = memoryStores();
    const { rerender } = render(
      <RunTrialCounter
        dataEnd={DATA_END}
        trial={trial(...Array.from({ length: 9 }, (_, i) => `p${i}`))}
        stores={stores}
      />,
    );
    await screen.findByText(/Trial #9 /);
    expect(screen.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
    rerender(<RunTrialCounter dataEnd={DATA_END} trial={trial("p9")} stores={stores} />);
    await screen.findByText(/Trial #10 /);
    expect(screen.getByText(OVERFIT_WARNING)).toBeInTheDocument();
  });

  it("counts the exit lab mock's pairs from the response, never hashing in the browser", async () => {
    render(
      <RunTrialCounter
        dataEnd={DATA_END}
        trial={mocks.backtestTradeLab.trial}
        stores={memoryStores()}
      />,
    );
    expect(
      await screen.findByText("Trial #5 for this rule structure · 5 this session"),
    ).toBeVisible();
  });

  it("falls back to the static warning when storage is blocked (AC-6)", async () => {
    render(<RunTrialCounter dataEnd={DATA_END} trial={trial("p1")} stores={blockedStores()} />);
    expect(await screen.findByText(OVERFIT_WARNING)).toBeInTheDocument();
    expect(screen.queryByText(/Trial #/)).not.toBeInTheDocument();
  });

  it("uses the browser's storage by default", async () => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    render(<RunTrialCounter dataEnd={DATA_END} trial={trial("browser")} />);
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Trial #1 for this rule structure · 1 this session",
      ),
    );
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders pending on the server, never touching storage", () => {
    const html = renderToString(
      <RunTrialCounter dataEnd={DATA_END} trial={trial("p1")} stores={blockedStores()} />,
    );
    expect(html).not.toContain("Trial #");
    expect(html).not.toContain("overfit");
  });

  it("sums pairs under two structure keys into one session total (AC-3)", async () => {
    const stores = memoryStores();
    const { rerender } = render(
      <RunTrialCounter dataEnd={DATA_END} trial={trial("p1", "p2")} stores={stores} />,
    );
    await screen.findByText(/Trial #2 /);
    rerender(
      <RunTrialCounter
        dataEnd={DATA_END}
        trial={{ structure_key: "d".repeat(64), pair_keys: ["q1"] }}
        stores={stores}
      />,
    );
    expect(
      await screen.findByText("Trial #1 for this rule structure · 3 this session"),
    ).toBeVisible();
  });

  it("shows the same totals after a remount of the same run, without counting it again (AC-2)", async () => {
    const stores = memoryStores();
    const first = render(
      <RunTrialCounter dataEnd={DATA_END} trial={trial("p1")} stores={stores} />,
    );
    await screen.findByText("Trial #1 for this rule structure · 1 this session");
    first.unmount();
    render(<RunTrialCounter dataEnd={DATA_END} trial={trial("p1")} stores={stores} />);
    expect(
      await screen.findByText("Trial #1 for this rule structure · 1 this session"),
    ).toBeVisible();
  });

  it("keeps one live region from pending to counted, so the new count is announced", async () => {
    const { container } = render(
      <RunTrialCounter dataEnd={DATA_END} trial={trial("p1")} stores={memoryStores()} />,
    );
    const region = container.querySelector('[role="status"]');
    expect(region).toHaveAttribute("aria-live", "polite");
    await screen.findByText(/Trial #1 /);
    expect(container.querySelector('[role="status"]')).toBe(region);
  });
});

describe("trialCounterText formatting (AC-4)", () => {
  it("writes large counts with separators through the shared formatter", () => {
    expect(trialCounterText(1234, 56789)).toBe(
      "Trial #1,234 for this rule structure · 56,789 this session",
    );
  });

  it("shows the warning for any count past 10, not only exactly 10 (AC-5)", () => {
    render(
      <TrialCounter
        state={{ status: "counted", count: { trialNumber: 37, sessionTotal: 40 }, dataEnds: [] }}
      />,
    );
    expect(screen.getByText(OVERFIT_WARNING)).toBeInTheDocument();
  });
});

// The dataset label on the warning (spec 0013 AC-10).
describe("the warning's dataset sentence (spec 0013 AC-10)", () => {
  it("names one dataset, and every dataset seen oldest first when a count spans two", () => {
    expect(trialDataText([])).toBe("");
    expect(trialDataText([DATA_END])).toBe("Those trials ran on data as of 2025-01-31.");
    expect(trialDataText([DATA_END, NEWER_DATA_END])).toBe(
      "Those trials ran on more than one dataset: data as of 2025-01-31 and 2025-02-03.",
    );
  });

  it("keeps counting across a dataset change and names both datasets, wiping no count", async () => {
    const stores = memoryStores();
    const nine = trial(...Array.from({ length: 9 }, (_, i) => `p${i}`));
    const { rerender } = render(
      <RunTrialCounter dataEnd={DATA_END} trial={nine} stores={stores} />,
    );
    await screen.findByText(/Trial #9 /);

    // A trading day lands: the same structure, a new pair, the newer dataset.
    rerender(<RunTrialCounter dataEnd={NEWER_DATA_END} trial={trial("p9")} stores={stores} />);
    // The count carried over rather than restarting at 1 (AC-10).
    await screen.findByText(/Trial #10 /);
    expect(
      screen.getByText(trialDataText([DATA_END, NEWER_DATA_END]), { exact: false }),
    ).toBeInTheDocument();
  });

  it("leaves the existing count array untouched, keeping its own key beside it", async () => {
    const stores = memoryStores();
    render(<RunTrialCounter dataEnd={DATA_END} trial={trial("p1", "p2")} stores={stores} />);
    await screen.findByText(/Trial #2 /);
    expect(JSON.parse(stores.local().getItem(TRIAL_KEY_PREFIX + STRUCTURE) ?? "")).toEqual([
      "p1",
      "p2",
    ]);
    expect(JSON.parse(stores.local().getItem(TRIAL_DATA_KEY_PREFIX + STRUCTURE) ?? "")).toEqual([
      DATA_END,
    ]);
  });
});

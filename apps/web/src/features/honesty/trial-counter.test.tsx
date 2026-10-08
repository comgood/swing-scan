import { render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";
import { expectNoAxeViolations } from "@/test/axe";

import { blockedStores, memoryStores } from "./memory-stores";
import { OVERFIT_WARNING, RunTrialCounter, TrialCounter, trialCounterText } from "./trial-counter";
import type { Trial } from "./trial-store";

const STRUCTURE = "c".repeat(64);
const trial = (...pairs: string[]): Trial => ({ structure_key: STRUCTURE, pair_keys: pairs });

describe("TrialCounter (U-4)", () => {
  it("uses the U-4 wording word for word (AC-4, AC-5)", () => {
    expect(trialCounterText(3, 7)).toBe("Trial #3 for this rule structure · 7 this session");
    expect(OVERFIT_WARNING).toBe(
      "You've tested many variants of this rule structure; the best IS result is likely overfit. Read OOS once and treat the result as a hypothesis.",
    );
  });

  it("shows the counter line without a warning below 10", () => {
    render(
      <TrialCounter state={{ status: "counted", count: { trialNumber: 9, sessionTotal: 12 } }} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Trial #9 for this rule structure · 12 this session",
    );
    expect(screen.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
  });

  it("shows the overfit warning at 10 (AC-5)", () => {
    render(
      <TrialCounter state={{ status: "counted", count: { trialNumber: 10, sessionTotal: 10 } }} />,
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
    { status: "counted", count: { trialNumber: 2, sessionTotal: 2 } },
    { status: "counted", count: { trialNumber: 12, sessionTotal: 30 } },
    { status: "unavailable" },
  ] as const)("passes axe for %o", async (state) => {
    const { container } = render(<TrialCounter state={state} />);
    await expectNoAxeViolations(container);
  });
});

describe("RunTrialCounter (U-4, spec 0004)", () => {
  it("records a run and shows trial 1 of 1", async () => {
    render(<RunTrialCounter trial={trial("p1")} stores={memoryStores()} />);
    expect(
      await screen.findByText("Trial #1 for this rule structure · 1 this session"),
    ).toBeVisible();
  });

  it("counts once under strict mode's double effect", async () => {
    render(
      <StrictMode>
        <RunTrialCounter trial={trial("p1", "p2")} stores={memoryStores()} />
      </StrictMode>,
    );
    expect(
      await screen.findByText("Trial #2 for this rule structure · 2 this session"),
    ).toBeVisible();
  });

  it("adds a numbers only tweak to the same rule's count, and not a re run (AC-1, AC-2)", async () => {
    const stores = memoryStores();
    const { rerender } = render(<RunTrialCounter trial={trial("n252")} stores={stores} />);
    await screen.findByText(/Trial #1 /);
    rerender(<RunTrialCounter trial={trial("n100")} stores={stores} />);
    expect(
      await screen.findByText("Trial #2 for this rule structure · 2 this session"),
    ).toBeVisible();
    rerender(<RunTrialCounter trial={trial("n252")} stores={stores} />);
    expect(
      await screen.findByText("Trial #2 for this rule structure · 2 this session"),
    ).toBeVisible();
  });

  it("shows the warning once the tenth distinct pair is recorded (AC-5)", async () => {
    const stores = memoryStores();
    const { rerender } = render(
      <RunTrialCounter
        trial={trial(...Array.from({ length: 9 }, (_, i) => `p${i}`))}
        stores={stores}
      />,
    );
    await screen.findByText(/Trial #9 /);
    expect(screen.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
    rerender(<RunTrialCounter trial={trial("p9")} stores={stores} />);
    await screen.findByText(/Trial #10 /);
    expect(screen.getByText(OVERFIT_WARNING)).toBeInTheDocument();
  });

  it("counts the exit lab mock's pairs from the response, never hashing in the browser", async () => {
    render(<RunTrialCounter trial={mocks.backtestTradeLab.trial} stores={memoryStores()} />);
    expect(
      await screen.findByText("Trial #5 for this rule structure · 5 this session"),
    ).toBeVisible();
  });

  it("falls back to the static warning when storage is blocked (AC-6)", async () => {
    render(<RunTrialCounter trial={trial("p1")} stores={blockedStores()} />);
    expect(await screen.findByText(OVERFIT_WARNING)).toBeInTheDocument();
    expect(screen.queryByText(/Trial #/)).not.toBeInTheDocument();
  });

  it("uses the browser's storage by default", async () => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    render(<RunTrialCounter trial={trial("browser")} />);
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Trial #1 for this rule structure · 1 this session",
      ),
    );
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders pending on the server, never touching storage", () => {
    const html = renderToString(<RunTrialCounter trial={trial("p1")} stores={blockedStores()} />);
    expect(html).not.toContain("Trial #");
    expect(html).not.toContain("overfit");
  });

  it("sums pairs under two structure keys into one session total (AC-3)", async () => {
    const stores = memoryStores();
    const { rerender } = render(<RunTrialCounter trial={trial("p1", "p2")} stores={stores} />);
    await screen.findByText(/Trial #2 /);
    rerender(
      <RunTrialCounter
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
    const first = render(<RunTrialCounter trial={trial("p1")} stores={stores} />);
    await screen.findByText("Trial #1 for this rule structure · 1 this session");
    first.unmount();
    render(<RunTrialCounter trial={trial("p1")} stores={stores} />);
    expect(
      await screen.findByText("Trial #1 for this rule structure · 1 this session"),
    ).toBeVisible();
  });

  it("keeps one live region from pending to counted, so the new count is announced", async () => {
    const { container } = render(<RunTrialCounter trial={trial("p1")} stores={memoryStores()} />);
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
      <TrialCounter state={{ status: "counted", count: { trialNumber: 37, sessionTotal: 40 } }} />,
    );
    expect(screen.getByText(OVERFIT_WARNING)).toBeInTheDocument();
  });
});

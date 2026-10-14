// covers: AC-12, AC-17 (all six exit types on the form, and a 422 on the field you typed it in)
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fieldErrorsFrom422 } from "@/lib/field-errors";
import { mocks } from "@/mocks/handlers";
import { expectNoAxeViolations } from "@/test/axe";

import { BacktestForm } from "./backtest-form";
import { DEFAULT_INPUTS, exitsOf, placeErrors, type BacktestInputs } from "./inputs";

/** Every exit filled in, so the form shows all six and the exit indexes are 0 to 5. */
const EVERY_EXIT: BacktestInputs = {
  ...DEFAULT_INPUTS,
  stopPct: 8,
  atrK: 2,
  atrN: 14,
  targetPct: 20,
  trailPct: 12,
  maN: 50,
  maKind: "sma",
  timeBars: 20,
  start: "2022-01-03",
  end: "2024-12-31",
};

/** One issue per field the form owns, on the paths the API would use. */
const ISSUES: { loc: (string | number)[]; msg: string; label: string }[] = [
  { loc: ["configs", 0, "exits", 0, "pct"], msg: "bad stop", label: "Stop loss (%)" },
  { loc: ["configs", 0, "exits", 1, "k"], msg: "bad atr multiple", label: "ATR stop (× ATR)" },
  { loc: ["configs", 0, "exits", 1, "n"], msg: "bad atr length", label: "ATR length (bars)" },
  { loc: ["configs", 0, "exits", 2, "pct"], msg: "bad target", label: "Target (%)" },
  { loc: ["configs", 0, "exits", 3, "pct"], msg: "bad trail", label: "Trailing stop (%)" },
  { loc: ["configs", 0, "exits", 4, "n"], msg: "bad ma length", label: "Close below MA (bars)" },
  { loc: ["configs", 0, "exits", 5, "bars"], msg: "bad time", label: "Time exit (bars)" },
  { loc: ["sim", "max_positions"], msg: "bad slots", label: "Max positions" },
  { loc: ["sim", "slippage_bps"], msg: "bad slippage", label: "Slippage (bps)" },
  { loc: ["sim", "start"], msg: "bad start", label: "Start" },
  { loc: ["sim", "end"], msg: "bad end", label: "End" },
];

function renderForm(inputs: BacktestInputs, errors: Partial<Record<string, string>> = {}) {
  const onChange = vi.fn();
  const onSubmit = vi.fn();
  const view = render(
    <BacktestForm
      templates={mocks.templates}
      inputs={inputs}
      onChange={onChange}
      onSubmit={onSubmit}
      running={false}
      errors={errors}
    />,
  );
  return { user: userEvent.setup(), onChange, onSubmit, ...view };
}

describe("BacktestForm", () => {
  it("offers a field for each of the six exit types and the MA kind", () => {
    renderForm(EVERY_EXIT);
    expect(screen.getByLabelText("Stop loss (%)")).toHaveValue("8");
    expect(screen.getByLabelText("ATR stop (× ATR)")).toHaveValue("2");
    expect(screen.getByLabelText("ATR length (bars)")).toHaveValue("14");
    expect(screen.getByLabelText("Target (%)")).toHaveValue("20");
    expect(screen.getByLabelText("Trailing stop (%)")).toHaveValue("12");
    expect(screen.getByLabelText("Close below MA (bars)")).toHaveValue("50");
    expect(screen.getByLabelText("Time exit (bars)")).toHaveValue("20");
    expect(screen.getByLabelText("MA type")).toHaveValue("sma");
    expect(exitsOf(EVERY_EXIT).map((e) => e.type)).toEqual([
      "stop_pct",
      "stop_atr",
      "target",
      "trail_pct",
      "close_below_ma",
      "time",
    ]);
  });

  it("puts each 422 on the field it belongs to", async () => {
    const placed = placeErrors(
      fieldErrorsFrom422({
        detail: ISSUES.map(({ loc, msg }) => ({ loc: ["body", ...loc], msg })),
      }),
      EVERY_EXIT,
    );
    expect(placed.form).toEqual([]); // every one of them belongs to a field
    const { container } = renderForm(EVERY_EXIT, placed.fields);

    for (const { msg, label } of ISSUES) {
      const field = screen.getByLabelText(label);
      const capitalised = msg[0]!.toUpperCase() + msg.slice(1);
      expect(field, label).toHaveAttribute("aria-invalid", "true");
      expect(screen.getByText(capitalised)).toBeInTheDocument();
    }
    await expectNoAxeViolations(container);
  });

  it("clears an exit when you blank its field, and runs on submit", async () => {
    const { user, onChange, onSubmit } = renderForm(EVERY_EXIT);
    await user.clear(screen.getByLabelText("Target (%)"));
    await user.tab();
    expect(onChange).toHaveBeenCalledWith({ ...EVERY_EXIT, targetPct: null });

    await user.click(screen.getByRole("button", { name: "Run backtest" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("disables the button while a run is in flight", () => {
    render(
      <BacktestForm
        templates={mocks.templates}
        inputs={DEFAULT_INPUTS}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        running
        errors={{}}
      />,
    );
    const button = screen.getByRole("button", { name: "Running…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });
});

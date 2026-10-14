// covers the UAT fixes (batch 1): the name is checked before the request and lands in the error
// summary, the backtest hand off waits for a rule the server has not rejected, and "Create my
// own rule" is the entry point to your own rule.
import type { Rule } from "@swing-scan/api-client";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useReducer } from "react";
import { describe, expect, it, vi } from "vitest";

import { fieldErrorsFrom422, type FieldErrors } from "@/lib/field-errors";
import { mocks } from "@/mocks/handlers";
import { renderWithQuery } from "@/test/render";

import { builderReducer, DEFAULT_NAME, initBuilder } from "./reducer";
import { NAME_EMPTY, NAME_TOO_LONG, RuleBuilder } from "./rule-builder";

const breakout = mocks.templates.find((t) => t.id === "breakout_52w")!;
const catalog = mocks.indicators;

function Harness({
  rule = breakout.rule,
  errors,
  onRun,
  backtestHref,
}: {
  rule?: Rule;
  errors?: FieldErrors;
  onRun?: () => void;
  backtestHref?: string;
}) {
  const [state, dispatch] = useReducer(builderReducer, rule, (r) =>
    initBuilder(r, { template: "breakout_52w" }),
  );
  return (
    <RuleBuilder
      state={state}
      dispatch={dispatch}
      catalog={catalog}
      errors={errors}
      onRun={onRun}
      backtestHref={backtestHref}
    />
  );
}

const nameField = () => screen.getByLabelText("Name");
const runScan = () => screen.getByRole("button", { name: "Run scan" });

describe("RuleBuilder name check before the request (UAT)", () => {
  it("blocks an empty name, says so on the field and in the summary, and focuses the summary", async () => {
    const onRun = vi.fn();
    const user = userEvent.setup();
    renderWithQuery(<Harness onRun={onRun} />);

    await user.clear(nameField());
    await user.click(runScan());

    expect(onRun).not.toHaveBeenCalled();
    expect(nameField()).toHaveAttribute("aria-invalid", "true");
    expect(nameField()).toHaveAccessibleDescription(expect.stringContaining(NAME_EMPTY));
    const summary = screen.getByRole("alert");
    expect(summary).toHaveTextContent(NAME_EMPTY);
    expect(document.activeElement).toContainElement(summary);
  });

  it("blocks a name over 40 characters and clears the error once it fits", async () => {
    const onRun = vi.fn();
    const user = userEvent.setup();
    renderWithQuery(<Harness onRun={onRun} />);

    await user.clear(nameField());
    await user.type(nameField(), "x".repeat(41));
    await user.click(runScan());
    expect(onRun).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(NAME_TOO_LONG);

    await user.clear(nameField());
    await user.type(nameField(), "Short enough");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(nameField()).not.toHaveAttribute("aria-invalid", "true");

    await user.click(runScan());
    expect(onRun).toHaveBeenCalledTimes(1);
  });

  it("puts the server's name 422 in the summary too", () => {
    const errors = fieldErrorsFrom422({
      detail: [{ loc: ["body", "rule", "name"], msg: "String should have at most 40 characters" }],
    });
    renderWithQuery(<Harness errors={errors} />);
    expect(screen.getByRole("alert")).toHaveTextContent("String should have at most 40 characters");
  });
});

describe("RuleBuilder backtest hand off while rejected (UAT)", () => {
  it("links to the backtest when nothing was rejected", () => {
    renderWithQuery(<Harness backtestHref="/backtest?r=abc" />);
    expect(screen.getByRole("link", { name: "Backtest this rule" })).toHaveAttribute(
      "href",
      "/backtest?r=abc",
    );
  });

  it("disables the button and drops the link while the server rejected the rule", () => {
    const errors = fieldErrorsFrom422({
      detail: [{ loc: ["body", "rule", "conditions", 0, "left", "n"], msg: "Out of range" }],
    });
    renderWithQuery(<Harness errors={errors} backtestHref="/backtest?r=abc" />);
    expect(screen.queryByRole("link", { name: "Backtest this rule" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Backtest this rule" })).toBeDisabled();
  });

  it("disables the button while the name the client checked is bad", async () => {
    const user = userEvent.setup();
    renderWithQuery(<Harness onRun={vi.fn()} backtestHref="/backtest?r=abc" />);
    await user.clear(nameField());
    await user.click(runScan());
    expect(screen.getByRole("button", { name: "Backtest this rule" })).toBeDisabled();
  });
});

describe('RuleBuilder "Create my own rule" (UAT)', () => {
  const button = () => screen.queryByRole("button", { name: "Create my own rule" });

  it("keeps the conditions, names the rule My rule, and then steps aside", async () => {
    const user = userEvent.setup();
    renderWithQuery(<Harness />);
    expect(nameField()).toHaveValue(breakout.rule.name);

    await user.click(button()!);

    expect(nameField()).toHaveValue(DEFAULT_NAME);
    expect(screen.getAllByRole("group", { name: /^Condition \d$/ })).toHaveLength(
      breakout.rule.conditions.length,
    );
    expect(button()).not.toBeInTheDocument();
  });
});

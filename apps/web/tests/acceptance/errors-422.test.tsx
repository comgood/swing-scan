// QA acceptance: U-7, through the shared helpers, from doc 01 section 6.6, spec 0002
// (validation errors) and spec 0003 AC-6, AC-7. "Given a 422 from the API, the offending
// builder row or exit field shows the inline error."
//
// The real builder rows (feature 10) and exit config editor (feature 12) do not exist yet, so
// these tests drive the path every page will use: the API's 422 body from the mocks, through
// `fieldErrorsFrom422`, onto the field the error names. The page level half stays pending.
import type { BacktestRequest, Rule } from "@swing-scan/api-client";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { FormErrorSummary } from "@/components/form-error-summary";
import { NumberInput } from "@/components/number-input";
import { api } from "@/lib/api";
import { errorAt, errorsUnder, fieldErrorsFrom422 } from "@/lib/field-errors";
import { backtestHandler, mocks, scanHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";

const RULE: Rule = mocks.templates[0].rule;
const noop = () => {};

async function scan422() {
  const { error, response } = await api.POST("/api/v1/scan", { body: { rule: RULE } });
  expect(response.status).toBe(422);
  return fieldErrorsFrom422(error);
}

async function backtest422(body: BacktestRequest) {
  const { error, response } = await api.POST("/api/v1/backtest", { body });
  expect(response.status).toBe(422);
  return fieldErrorsFrom422(error);
}

describe("U-7 builder rows", () => {
  it("U-7: an out of range n lands on row 1's field, not on row 2", async () => {
    server.use(scanHandler("422.rule.n_out_of_range"));
    const errors = await scan422();

    render(
      <>
        <NumberInput
          label="Row 1 left n"
          value={60}
          onValueChange={noop}
          error={errorAt(errors, "rule.conditions.0.left.n")}
        />
        <NumberInput
          label="Row 2 left n"
          value={20}
          onValueChange={noop}
          error={errorAt(errors, "rule.conditions.1.left.n")}
        />
      </>,
    );

    const row1 = screen.getByLabelText("Row 1 left n");
    expect(row1).toHaveAttribute("aria-invalid", "true");
    expect(row1).toHaveAccessibleDescription(/Must be between 2 and 50/);
    expect(screen.getByText("Must be between 2 and 50")).toBeVisible();

    const row2 = screen.getByLabelText("Row 2 left n");
    expect(row2).not.toHaveAttribute("aria-invalid", "true");
    expect(errors.form).toEqual([]);
  });

  it("U-7: an unknown indicator belongs to row 1, so the row can show its child errors", async () => {
    server.use(scanHandler("422.rule.unknown_indicator"));
    const errors = await scan422();
    expect(Object.keys(errorsUnder(errors, "rule.conditions.0"))).toEqual([
      "rule.conditions.0.left.ind",
    ]);
    expect(errorsUnder(errors, "rule.conditions.1")).toEqual({});
  });
});

describe("U-7 exit and simulation fields", () => {
  it("U-7: a duplicate exit type points at config 1, exit 2, and nowhere else", async () => {
    server.use(backtestHandler("422.exits.duplicate_type"));
    const errors = await backtest422({
      rule: RULE,
      configs: [
        {
          name: "Config 1",
          exits: [
            { type: "stop_pct", pct: 8 },
            { type: "stop_pct", pct: 5 },
          ],
        },
      ],
    });
    expect(errorAt(errors, "configs.0.exits.1.type")).toBe(
      "Exit type stop_pct is already used in this config",
    );
    expect(Object.keys(errorsUnder(errors, "configs.0.exits.1"))).toEqual([
      "configs.0.exits.1.type",
    ]);
    expect(errorsUnder(errors, "configs.0.exits.0")).toEqual({});
  });

  it("U-7: an out of range simulation field shows the error inline on that field", async () => {
    server.use(backtestHandler("422.sim.out_of_range"));
    const errors = await backtest422({
      rule: RULE,
      configs: [{ name: "Config 1", exits: [{ type: "stop_pct", pct: 8 }] }],
    });
    render(
      <NumberInput
        label="Max positions"
        value={25}
        min={1}
        max={20}
        integer
        onValueChange={noop}
        error={errorAt(errors, "sim.max_positions")}
      />,
    );
    const field = screen.getByLabelText("Max positions");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(/Must be between 1 and 20/);
  });

  it("U-7: an error on the whole body shows in the form summary as an alert", async () => {
    server.use(
      http.post("*/api/v1/scan", () =>
        HttpResponse.json(
          { detail: [{ type: "missing", loc: ["body"], msg: "field required", input: null }] },
          { status: 422 },
        ),
      ),
    );
    const errors = await scan422();
    expect(errors.form).toEqual(["Field required"]);
    render(<FormErrorSummary errors={errors.form} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Field required");
  });
});

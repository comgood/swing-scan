// covers: spec 0008 AC-4 (UI to JSON parity), AC-5 (limits), AC-6 (every field), AC-7 (422 on
// its field, rule kept), AC-9 (no hidden filter), AC-10 (labels and axe)
import type { Rule, ScanRequest } from "@swing-scan/api-client";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useReducer, useState } from "react";
import { describe, expect, it } from "vitest";

import { api } from "@/lib/api";
import { fieldErrorsFrom422, type FieldErrors } from "@/lib/field-errors";
import { mocks, scanHandler, type ScanVariant } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";
import { renderWithQuery } from "@/test/render";

import { builderReducer, initBuilder } from "./reducer";
import { MAX_ROWS_REASON, RuleBuilder, STALE_TEXT } from "./rule-builder";

const breakout = mocks.templates.find((t) => t.id === "breakout_52w")!;
const catalog = mocks.indicators;

/** The caller the workspace will be: owns the reducer, posts `state.rule` on Run scan. */
function Harness({ rule = breakout.rule }: { rule?: Rule }) {
  const [state, dispatch] = useReducer(builderReducer, rule, (r) =>
    initBuilder(r, { template: "breakout_52w" }),
  );
  const [errors, setErrors] = useState<FieldErrors>();
  const [ranOnce, setRanOnce] = useState(false);
  const onRun = async () => {
    const result = await api.POST("/api/v1/scan", { body: { rule: state.rule } });
    setErrors(result.response.status === 422 ? fieldErrorsFrom422(result.error) : undefined);
    if (result.response.ok) {
      setRanOnce(true);
      dispatch({ type: "ran" });
    }
  };
  return (
    <RuleBuilder
      state={state}
      dispatch={dispatch}
      catalog={catalog}
      errors={errors}
      onRun={() => void onRun()}
      stale={ranOnce && state.dirty}
    />
  );
}

function recordScans(variant: ScanVariant = "ok") {
  const bodies: ScanRequest[] = [];
  server.use(
    http.post("*/api/v1/scan", async ({ request }) => {
      bodies.push((await request.json()) as ScanRequest);
      return variant === "ok" ? HttpResponse.json(mocks.scan) : undefined;
    }),
  );
  if (variant !== "ok") server.use(scanHandler(variant));
  return bodies;
}

const row = (n: number) => screen.getByRole("group", { name: `Condition ${n}` });
const side = (n: number, name: "Left side" | "Right side") =>
  within(row(n)).getByRole("group", { name });

function setup(rule?: Rule) {
  const user = userEvent.setup();
  const view = renderWithQuery(<Harness rule={rule} />);
  return { user, ...view };
}

describe("RuleBuilder", () => {
  it("shows every template condition, close > 5 included, and nothing else (AC-9)", () => {
    setup();
    expect(screen.getAllByRole("group", { name: /^Condition \d$/ })).toHaveLength(3);
    const third = row(3);
    expect(within(side(3, "Left side")).getByLabelText("Indicator")).toHaveValue("close");
    expect(within(third).getByLabelText("Operator")).toHaveValue(">");
    expect(within(side(3, "Right side")).getByLabelText("Number")).toHaveValue("5");
  });

  it("posts exactly the rows after add, edit and remove (AC-4)", async () => {
    const bodies = recordScans();
    const { user } = setup();

    await user.click(screen.getByRole("button", { name: "Add condition" }));
    const left4 = side(4, "Left side");
    await user.selectOptions(within(left4).getByLabelText("Indicator"), "rsi");
    const n = within(left4).getByLabelText("Window (n)");
    await user.clear(n);
    await user.type(n, "21");
    const offset = within(left4).getByLabelText("Bars ago");
    await user.clear(offset);
    await user.type(offset, "2");
    await user.selectOptions(within(row(4)).getByLabelText("Operator"), "crosses_below");
    await user.selectOptions(within(row(4)).getByLabelText("Compare with"), "value");
    const value = within(side(4, "Right side")).getByLabelText("Number");
    await user.clear(value);
    await user.type(value, "30.5");
    await user.click(screen.getByRole("button", { name: "Remove condition 2" }));
    await user.click(screen.getByRole("button", { name: "Run scan" }));

    await waitFor(() => expect(bodies).toHaveLength(1));
    const [c1, , c3] = breakout.rule.conditions;
    expect(bodies[0]).toEqual({
      rule: {
        name: breakout.rule.name,
        conditions: [
          c1,
          c3,
          {
            left: { kind: "ind", ind: "rsi", n: 21, offset: 2, mult: 1 },
            op: "crosses_below",
            right: { kind: "value", value: 30.5 },
          },
        ],
      },
    });
  });

  it("loads pasted JSON into rows that post back the same JSON (AC-4)", async () => {
    const bodies = recordScans();
    const { user } = setup();
    const pullback = mocks.templates.find((t) => t.id === "pullback_ema21")!;
    await user.click(screen.getByText("Rule as JSON"));
    await user.click(screen.getByLabelText("Paste a rule"));
    await user.paste(JSON.stringify(pullback.rule));
    await user.click(screen.getByRole("button", { name: "Load rule" }));
    expect(screen.getAllByRole("group", { name: /^Condition \d$/ })).toHaveLength(5);
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0].rule).toEqual(pullback.rule);
    expect(screen.getByLabelText("Rule JSON")).toHaveTextContent(`"name": "${pullback.rule.name}"`);
  });

  it("says Not a rule for bad JSON and changes nothing", async () => {
    const { user } = setup();
    await user.click(screen.getByText("Rule as JSON"));
    await user.click(screen.getByLabelText("Paste a rule"));
    await user.paste('{"name": "x"}');
    await user.click(screen.getByRole("button", { name: "Load rule" }));
    expect(screen.getByText("Not a rule")).toBeInTheDocument();
    expect(screen.getAllByRole("group", { name: /^Condition \d$/ })).toHaveLength(3);
  });

  it("disables add at 8 rows and remove on the last row, each with a reason (AC-5)", async () => {
    const { user } = setup();
    const add = screen.getByRole("button", { name: "Add condition" });
    for (let i = 0; i < 5; i++) await user.click(add);
    expect(add).toBeDisabled();
    expect(add).toHaveAccessibleDescription(MAX_ROWS_REASON);

    for (let i = 8; i > 1; i--) {
      await user.click(screen.getByRole("button", { name: `Remove condition ${i}` }));
    }
    const remove = screen.getByRole("button", { name: "Remove condition 1" });
    expect(remove).toBeDisabled();
    expect(remove).toHaveAccessibleDescription("A rule needs at least 1 condition.");
  });

  it("shows n only for windowed indicators, with the catalog range (AC-6)", async () => {
    const { user } = setup();
    const left = side(1, "Left side");
    expect(within(left).queryByLabelText("Window (n)")).not.toBeInTheDocument();
    await user.selectOptions(within(left).getByLabelText("Indicator"), "rsi");
    const n = within(left).getByLabelText("Window (n)");
    expect(n).toHaveValue("14");
    expect(n).toHaveAccessibleDescription(expect.stringContaining("Allowed: 2 to 50"));
    await user.selectOptions(within(left).getByLabelText("Indicator"), "rs");
    expect(within(left).getByLabelText("Window (n)")).toHaveValue("126");
  });

  it("keeps the last valid number when a field is emptied", async () => {
    const bodies = recordScans();
    const { user } = setup();
    const value = within(side(3, "Right side")).getByLabelText("Number");
    await user.clear(value);
    await user.tab();
    expect(value).toHaveAccessibleDescription(expect.stringContaining("Enter a number"));
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0].rule.conditions[2].right).toEqual({ kind: "value", value: 5 });
  });

  it("puts a 422 on the exact field and keeps the rule as typed (AC-7)", async () => {
    recordScans("422.rule.n_out_of_range");
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    const left = side(1, "Left side");
    await waitFor(() =>
      expect(within(left).getByText("Must be between 2 and 50")).toBeInTheDocument(),
    );
    expect(within(left).getByLabelText("Indicator")).toHaveValue("close");
    expect(within(side(1, "Right side")).queryByText(/Must be/)).not.toBeInTheDocument();
  });

  it("shows a 422 about the row count above the rows (AC-7)", async () => {
    recordScans("422.rule.too_many_conditions");
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    expect(await screen.findByText("Must be between 1 and 8")).toBeInTheDocument();
  });

  it("puts an unknown indicator error on that row's indicator (AC-7)", async () => {
    recordScans("422.rule.unknown_indicator");
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    expect(
      await within(side(1, "Left side")).findByText(/Input should be 'open'/),
    ).toBeInTheDocument();
  });

  // The real API names the right side's `kind` tag in `loc` (U-7 ruling 2026-10-09).
  function answer422(loc: (string | number)[], msg: string) {
    server.use(
      http.post("*/api/v1/scan", () =>
        HttpResponse.json(
          { detail: [{ type: "x", loc: ["body", "rule", ...loc], msg, input: null }] },
          { status: 422 },
        ),
      ),
    );
  }

  async function expectOnField(field: HTMLElement, message: string) {
    await waitFor(() => expect(field).toHaveAttribute("aria-invalid", "true"));
    expect(field).toHaveAccessibleDescription(expect.stringContaining(message));
  }

  it("puts a tagged right ind n (right.ind.n) on that row's right Window (n) (AC-7)", async () => {
    answer422(["conditions", 1, "right", "ind", "n"], "must be between 2 and 252");
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await expectOnField(
      within(side(2, "Right side")).getByLabelText("Window (n)"),
      "Must be between 2 and 252",
    );
    expect(within(row(2)).getAllByText("Must be between 2 and 252")).toHaveLength(1);
    expect(within(side(2, "Left side")).queryByText(/Must be/)).not.toBeInTheDocument();
  });

  it("puts a tagged right value (right.value.value) on that row's Number (AC-7)", async () => {
    answer422(["conditions", 2, "right", "value", "value"], "input should be a valid number");
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await expectOnField(
      within(side(3, "Right side")).getByLabelText("Number"),
      "Input should be a valid number",
    );
    expect(within(row(3)).getAllByText("Input should be a valid number")).toHaveLength(1);
  });

  it("puts a tagged right ind (right.ind.ind) on that row's right Indicator (AC-7)", async () => {
    answer422(["conditions", 0, "right", "ind", "ind"], "input should be 'open'");
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await expectOnField(
      within(side(1, "Right side")).getByLabelText("Indicator"),
      "Input should be 'open'",
    );
  });

  it("puts the untagged left n (left.n) on that row's left Window (n) (AC-7)", async () => {
    const rule: Rule = {
      ...breakout.rule,
      conditions: [
        {
          left: { kind: "ind", ind: "sma", n: 20, offset: 0, mult: 1 },
          op: ">",
          right: { kind: "value", value: 5 },
        },
      ],
    };
    answer422(["conditions", 0, "left", "n"], "must be between 2 and 252");
    const { user } = setup(rule);
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await expectOnField(
      within(side(1, "Left side")).getByLabelText("Window (n)"),
      "Must be between 2 and 252",
    );
  });

  it("labels results stale after an edit until Run scan", async () => {
    recordScans();
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await user.selectOptions(within(row(1)).getByLabelText("Operator"), ">=");
    expect(await screen.findByText(STALE_TEXT)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await waitFor(() => expect(screen.queryByText(STALE_TEXT)).not.toBeInTheDocument());
  });

  it("has no axe violations, with an indicator right side and the JSON panel open (AC-10)", async () => {
    const { user, container } = setup();
    await user.click(screen.getByText("Rule as JSON"));
    await expectNoAxeViolations(container);
  });
});

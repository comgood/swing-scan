import { describe, expect, it } from "vitest";

import ruleNOutOfRange from "../../../../contracts/mocks/422.rule.n_out_of_range.json";
import scanNotImplemented from "../../../../contracts/mocks/501.scan.json";

import { errorAt, errorsUnder, fieldErrorsFrom422 } from "./field-errors";

describe("fieldErrorsFrom422 (AC-7)", () => {
  it("maps the contract's 422 mock to its field path with a capitalised message", () => {
    const errors = fieldErrorsFrom422(ruleNOutOfRange);
    expect(errors).toEqual({
      fields: { "rule.conditions.0.left.n": "Must be between 2 and 50" },
      form: [],
    });
  });

  it("drops only a leading body prefix and keeps others such as query", () => {
    const errors = fieldErrorsFrom422({
      detail: [
        {
          type: "x",
          loc: ["body", "rule", "conditions", 2, "left", "n"],
          msg: "bad",
          input: 1,
          ctx: {},
        },
        { type: "x", loc: ["query", "as_of"], msg: "bad date", input: "x", ctx: {} },
      ],
    });
    expect(Object.keys(errors.fields)).toEqual(["rule.conditions.2.left.n", "query.as_of"]);
  });

  it("sends body level errors to form, keeps the first error per key, and drops duplicate form errors", () => {
    const errors = fieldErrorsFrom422({
      detail: [
        { type: "x", loc: ["body"], msg: "rule needs a condition", input: null },
        { type: "x", loc: ["body"], msg: "rule needs a condition", input: null },
        { type: "x", loc: ["body", "sim", "slippage_pct"], msg: "first", input: 9 },
        { type: "x", loc: ["body", "sim", "slippage_pct"], msg: "second", input: 9 },
      ],
    });
    expect(errors.form).toEqual(["Rule needs a condition"]);
    expect(errors.fields).toEqual({ "sim.slippage_pct": "First" });
  });

  it("puts a string detail in form", () => {
    expect(fieldErrorsFrom422(scanNotImplemented)).toEqual({
      fields: {},
      form: [scanNotImplemented.detail],
    });
  });

  it.each([null, "oops", {}, { detail: 5 }, { detail: [{ nope: true }] }])(
    "falls back for an unexpected shape: %j",
    (body) => {
      expect(fieldErrorsFrom422(body)).toEqual({ fields: {}, form: ["The request was rejected."] });
    },
  );
});

describe("errorAt and errorsUnder", () => {
  const errors = {
    fields: {
      "rule.conditions.2": "Row error",
      "rule.conditions.2.left.n": "Must be between 2 and 50",
      "rule.conditions.20.left.n": "Other row",
    },
    form: [],
  };

  it("errorAt returns only the exact match", () => {
    expect(errorAt(errors, "rule.conditions.2.left.n")).toBe("Must be between 2 and 50");
    expect(errorAt(errors, "rule.conditions.2.left")).toBeUndefined();
    expect(errorAt(errors, "toString")).toBeUndefined();
  });

  it("errorsUnder returns the prefix and its children, not siblings sharing the text", () => {
    expect(errorsUnder(errors, "rule.conditions.2")).toEqual({
      "rule.conditions.2": "Row error",
      "rule.conditions.2.left.n": "Must be between 2 and 50",
    });
  });
});

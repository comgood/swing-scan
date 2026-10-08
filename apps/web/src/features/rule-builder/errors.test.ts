// covers: spec 0008 AC-7 (each 422 path lands on its control, nothing is dropped)
import { describe, expect, it } from "vitest";

import { fieldErrorsFrom422 } from "@/lib/field-errors";

import { builderErrors } from "./errors";

function issue(loc: (string | number)[], msg = "bad") {
  return { loc: ["body", ...loc], msg, type: "x" };
}

function map(issues: ReturnType<typeof issue>[], rows = 3) {
  return builderErrors(fieldErrorsFrom422({ detail: issues }), rows);
}

describe("builderErrors", () => {
  it("returns empty rows when there is no 422", () => {
    expect(builderErrors(undefined, 2)).toEqual({
      rows: [
        { left: {}, right: {} },
        { left: {}, right: {} },
      ],
      top: [],
    });
  });

  it.each(["ind", "n", "offset", "mult"] as const)("puts left.%s on that row's left field", (f) => {
    const out = map([issue(["rule", "conditions", 1, "left", f], "must be between 2 and 50")]);
    expect(out.rows[1].left[f]).toBe("Must be between 2 and 50");
    expect(out.rows[0].left).toEqual({});
  });

  it("tells a left n from a right n", () => {
    const out = map([
      issue(["rule", "conditions", 2, "right", "n"], "right n"),
      issue(["rule", "conditions", 2, "left", "n"], "left n"),
    ]);
    expect(out.rows[2].right.n).toBe("Right n");
    expect(out.rows[2].left.n).toBe("Left n");
  });

  it("puts the operator, a right value and a bad kind tag on their controls", () => {
    const out = map([
      issue(["rule", "conditions", 0, "op"], "op"),
      issue(["rule", "conditions", 0, "right", "value"], "value"),
      issue(["rule", "conditions", 1, "right"], "kind"),
      issue(["rule", "conditions", 1, "left"], "left kind"),
    ]);
    expect(out.rows[0].op).toBe("Op");
    expect(out.rows[0].right.value).toBe("Value");
    expect(out.rows[1].right.group).toBe("Kind");
    expect(out.rows[1].left.group).toBe("Left kind");
  });

  it("shows anything else under a row as a row message", () => {
    const out = map([issue(["rule", "conditions", 0, "left", "ema", "n"], "deep")]);
    expect(out.rows[0].row).toBe("Deep");
  });

  it("puts conditions, unmatched and out of range rows above the rows", () => {
    const out = map([
      issue(["rule", "conditions"], "must be between 1 and 8"),
      issue(["rule", "conditions", 7, "op"], "row 8"),
      issue(["as_of"], "not a session"),
    ]);
    expect(out.top).toEqual(["Must be between 1 and 8", "Row 8", "Not a session"]);
  });

  it("puts name on the Name field, and form messages above the rows", () => {
    expect(map([issue(["rule", "name"], "too long")]).name).toBe("Too long");
    expect(builderErrors(fieldErrorsFrom422({ detail: "nope" }), 1).top).toEqual(["nope"]);
  });
});

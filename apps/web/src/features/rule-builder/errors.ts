// Where each 422 issue shows in the builder (spec 0008, "422 path to control"). Paths come from
// `fieldErrorsFrom422`, e.g. `rule.conditions.2.right.n`. Nothing is dropped: an issue with no
// field of its own shows above the rows.
import type { FieldErrors } from "@/lib/field-errors";

export interface OperandErrors {
  /** A bad `kind` tag on the whole side. */
  group?: string;
  ind?: string;
  n?: string;
  offset?: string;
  mult?: string;
  value?: string;
}

export interface RowErrors {
  left: OperandErrors;
  right: OperandErrors;
  op?: string;
  row?: string;
}

export interface BuilderErrors {
  name?: string;
  rows: RowErrors[];
  /** Above the rows: form level issues, `conditions` itself, and anything unmatched. */
  top: string[];
}

const FIELDS = ["ind", "n", "offset", "mult", "value"] as const;

function emptyRow(): RowErrors {
  return { left: {}, right: {} };
}

export function builderErrors(errors: FieldErrors | undefined, rowCount: number): BuilderErrors {
  const out: BuilderErrors = { rows: Array.from({ length: rowCount }, emptyRow), top: [] };
  if (!errors) return out;
  out.top.push(...errors.form);
  for (const [path, message] of Object.entries(errors.fields)) {
    const parts = path.split(".");
    if (parts[0] !== "rule") {
      out.top.push(message);
      continue;
    }
    if (parts.length === 2 && parts[1] === "name") {
      out.name = message;
      continue;
    }
    const index = Number(parts[2]);
    const row = parts[1] === "conditions" && Number.isInteger(index) ? out.rows[index] : undefined;
    if (!row) {
      out.top.push(message);
      continue;
    }
    const [, , , side, field] = parts;
    if ((side === "left" || side === "right") && parts.length <= 5) {
      const target = row[side];
      const key = FIELDS.find((f) => f === field);
      if (field === undefined) target.group ??= message;
      else if (key) target[key] ??= message;
      else row.row ??= message;
    } else if (side === "op" && parts.length === 4) {
      row.op ??= message;
    } else {
      row.row ??= message;
    }
  }
  return out;
}

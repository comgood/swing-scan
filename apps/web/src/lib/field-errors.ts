// Maps a FastAPI 422 body to field errors keyed by path (spec 0003 AC-7, U-7).
// `["body", "rule", "conditions", 2, "left", "n"]` → `rule.conditions.2.left.n`.

export interface FieldErrors {
  fields: Record<string, string>;
  form: string[];
}

const FALLBACK = "The request was rejected.";

interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
}

function isIssue(value: unknown): value is ValidationIssue {
  if (typeof value !== "object" || value === null) return false;
  const { loc, msg } = value as Record<string, unknown>;
  return (
    Array.isArray(loc) &&
    loc.every((part) => typeof part === "string" || typeof part === "number") &&
    typeof msg === "string"
  );
}

function capitalise(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function fieldErrorsFrom422(body: unknown): FieldErrors {
  const detail =
    typeof body === "object" && body !== null ? (body as { detail?: unknown }).detail : undefined;

  if (typeof detail === "string") return { fields: {}, form: [detail] };
  if (!Array.isArray(detail) || !detail.every(isIssue)) return { fields: {}, form: [FALLBACK] };

  const fields: Record<string, string> = {};
  const form: string[] = [];
  for (const issue of detail) {
    const message = capitalise(issue.msg);
    const path = issue.loc[0] === "body" ? issue.loc.slice(1) : issue.loc;
    if (path.length === 0) {
      if (!form.includes(message)) form.push(message);
      continue;
    }
    const key = path.join(".");
    if (!(key in fields)) fields[key] = message;
  }
  return { fields, form };
}

/** The error for exactly this path, if any. */
export function errorAt(errors: FieldErrors, path: string): string | undefined {
  return Object.hasOwn(errors.fields, path) ? errors.fields[path] : undefined;
}

/** Every error at or below `prefix`, for a row that shows its children's errors. */
export function errorsUnder(errors: FieldErrors, prefix: string): Record<string, string> {
  return Object.fromEntries(
    Object.entries(errors.fields).filter(([key]) => key === prefix || key.startsWith(`${prefix}.`)),
  );
}

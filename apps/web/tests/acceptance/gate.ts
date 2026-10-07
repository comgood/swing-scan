// QA acceptance gate for Vitest, mirroring tests/acceptance/conftest.py (doc 02 section 15.4).
//
// `acIt(ids, name, fn)` reads tests/acceptance/status.yaml. If any ID is `required`, it is a
// plain `it`: a failure fails the web suite and CI. If every ID is `pending`, the test still
// runs, but a failure is reported as skipped with the reason (a non strict xfail), so QA can
// write tests for UI that is not on `main` yet without turning CI red. When such a test passes,
// it shows as passed: the cue to flip the ID once it passes on `main`.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { it, type TestContext } from "vitest";

// jsdom gives `import.meta.url` an http scheme, so resolve from the file's directory instead.
const STATUS_PATH = resolve(import.meta.dirname, "../../../../tests/acceptance/status.yaml");

type Status = "pending" | "required";

function loadStatus(): Map<string, Status> {
  const status = new Map<string, Status>();
  for (const raw of readFileSync(STATUS_PATH, "utf-8").split("\n")) {
    const line = raw.replace(/#.*/, "").trim();
    if (!line) continue;
    const match = /^([A-Z]-\d+[A-Z]?):\s*(pending|required)$/.exec(line);
    if (!match) throw new Error(`status.yaml: bad line "${raw}"`);
    status.set(match[1], match[2] as Status);
  }
  return status;
}

const STATUS = loadStatus();

export function isPending(ids: readonly string[]): boolean {
  return ids.every((id) => {
    const value = STATUS.get(id);
    if (value === undefined) throw new Error(`unknown criterion ID ${id} (status.yaml)`);
    return value === "pending";
  });
}

/** An acceptance test gated on its doc 01 IDs. The name should start with the IDs. */
export function acIt(
  ids: readonly string[],
  name: string,
  fn: (context: TestContext) => Promise<void> | void,
  // Longer than Vitest's 5 s default: a test-level timeout cannot be caught, so the waits
  // inside a test must always run out first.
  timeout = 15_000,
) {
  if (!isPending(ids)) {
    it(name, fn, timeout);
    return;
  }
  it(
    name,
    async (context) => {
      try {
        await fn(context);
      } catch (error) {
        const reason = error instanceof Error ? error.message.split("\n")[0] : String(error);
        context.skip(`pending ${ids.join(", ")} (status.yaml): ${reason}`);
      }
    },
    timeout,
  );
}

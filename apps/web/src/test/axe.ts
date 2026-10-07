// Runs axe on a rendered fragment (spec 0003 AC-16). Contrast, regions and the single main
// landmark are off: jsdom has no layout, and fragments have no landmarks. Contrast is covered
// by the design.md table and a browser pass in /check verify.
import axe from "axe-core";
import { expect } from "vitest";

export async function expectNoAxeViolations(container: Element): Promise<void> {
  const results = await axe.run(container, {
    rules: {
      "color-contrast": { enabled: false },
      region: { enabled: false },
      "landmark-one-main": { enabled: false },
    },
  });
  const summary = results.violations.map(
    (v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(", ")})`,
  );
  expect(summary).toEqual([]);
}

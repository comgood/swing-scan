// @vitest-environment node
// The tokens in globals.css match apps/web/design.md (spec 0003 AC-1, AC-13).
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./globals.css", import.meta.url), "utf8");
const design = readFileSync(new URL("../../design.md", import.meta.url), "utf8");

/** `--name: value;` pairs inside the first block that follows `marker`. */
function declarations(marker: RegExp): Record<string, string> {
  const start = css.search(marker);
  expect(start, `block ${String(marker)} in globals.css`).toBeGreaterThanOrEqual(0);
  const open = css.indexOf("{", css.indexOf(":root", start));
  const close = css.indexOf("}", open);
  const block = css.slice(open + 1, close);
  return Object.fromEntries(
    [...block.matchAll(/--([\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]),
  );
}

/** Rows of the design.md colour table: token names with their light and dark values. */
function designTokens(): { name: string; light: string; dark: string }[] {
  const table = design.slice(design.indexOf("## Colour tokens"), design.indexOf("### Contrast"));
  return table
    .split("\n")
    .filter((line) => /^\|\s*`/.test(line))
    .flatMap((line) => {
      const [names, light, dark] = line
        .split("|")
        .slice(1, 4)
        .map((c) => c.trim());
      const tokenNames = [...names.matchAll(/`([\w-]+)`/g)].map((m) => m[1]);
      const lights = [...light.matchAll(/#[0-9a-f]{6}/g)].map((m) => m[0]);
      const darks = [...dark.matchAll(/#[0-9a-f]{6}/g)].map((m) => m[0]);
      if (lights.length === 0) return []; // popover rows are aliases, checked separately
      return tokenNames.map((name, i) => ({
        name,
        light: lights[i] ?? lights[0],
        dark: darks[i] ?? darks[0],
      }));
    });
}

const light = declarations(/^:root\s*{/m);
const dark = declarations(/@media \(prefers-color-scheme: dark\)\s*{/);

// covers: AC-1
describe("globals.css tokens (AC-1)", () => {
  const tokens = designTokens();

  it("reads the design.md colour table", () => {
    expect(tokens.length).toBeGreaterThanOrEqual(28);
  });

  it.each(tokens)(
    "defines --$name with the design.md light and dark values",
    ({ name, light: l, dark: d }) => {
      expect(light[name]).toBe(l);
      expect(dark[name]).toBe(d);
      expect(css).toContain(`--color-${name}: var(--${name});`);
    },
  );

  it("aliases popover to card instead of giving it its own colour", () => {
    expect(light.popover).toBe("var(--card)");
    expect(light["popover-foreground"]).toBe("var(--card-foreground)");
  });

  it("sets the radius and color-scheme on :root", () => {
    expect(light.radius).toBe("0.5rem");
    expect(css).toMatch(/:root\s*{\s*color-scheme: light dark;/);
  });

  it("follows the OS theme and never a .dark class", () => {
    expect(css).toContain("@custom-variant dark (@media (prefers-color-scheme: dark));");
    expect(css).not.toMatch(/^\s*\.dark\b/m);
    expect(css).not.toContain("&:is(.dark");
  });

  it("drops preset variables design.md does not name, and the Arial rule", () => {
    expect(css).not.toMatch(/--sidebar|--chart-[1-5]\b/);
    expect(css).not.toContain("Arial");
    expect(css).toContain("--font-sans: var(--font-geist-sans);");
  });
});

// covers: AC-13
describe("global focus and motion rules (AC-13)", () => {
  it("draws one full contrast focus outline from the ring token", () => {
    expect(css).toMatch(
      /:focus-visible\s*{\s*outline: 2px solid var\(--ring\);\s*outline-offset: 2px;\s*}/,
    );
  });

  it("cuts animations and transitions under reduced motion", () => {
    const reduced = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)"));
    expect(reduced).toContain("animation-duration: 0.01ms !important;");
    expect(reduced).toContain("transition-duration: 0.01ms !important;");
  });
});

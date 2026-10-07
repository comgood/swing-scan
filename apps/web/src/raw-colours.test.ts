// @vitest-environment node
// No raw colours in source: everything comes from the design.md tokens (spec 0003 AC-2).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SRC = fileURLToPath(new URL(".", import.meta.url));

const PATTERNS = [
  /#[0-9a-fA-F]{3,8}\b/,
  /rgb\(/,
  /hsl\(/,
  /oklch\(/,
  /\b(bg|text|border|ring|fill|stroke|from|to|outline)-(white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)\b/,
];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    if (!/\.tsx?$/.test(name) || /\.test\.tsx?$/.test(name)) return [];
    return [path];
  });
}

describe("raw colour check (AC-2)", () => {
  it("finds source files, including the generated ui folder", () => {
    const files = sourceFiles(SRC).map((f) => relative(SRC, f));
    expect(files).toContain(join("components", "ui", "button.tsx"));
  });

  it("no .ts or .tsx file under src/ contains a raw colour", () => {
    const hits = sourceFiles(SRC).flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .flatMap((line, i) =>
          PATTERNS.some((p) => p.test(line))
            ? [`${relative(SRC, file)}:${i + 1}: ${line.trim()}`]
            : [],
        ),
    );
    expect(hits).toEqual([]);
  });
});

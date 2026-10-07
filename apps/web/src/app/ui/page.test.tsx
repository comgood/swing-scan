import { describe, expect, it } from "vitest";

import { metadata } from "./page";

// covers: AC-15 (the gallery page is hidden from search engines)
describe("/ui page metadata (AC-15)", () => {
  it("asks search engines not to index the gallery", () => {
    expect(metadata.robots).toEqual({ index: false });
  });
});

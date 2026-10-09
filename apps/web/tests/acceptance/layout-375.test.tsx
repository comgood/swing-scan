// QA acceptance: U-6, structural half only, from doc 01 section 6.6 and spec 0003 AC-5, AC-8,
// AC-14. "Given a 375 px viewport, builder rows stack, tables scroll inside their containers,
// and the page has no horizontal scroll."
//
// jsdom applies no CSS and has no layout, so these tests check the structure the layout rests
// on: the stacking grid, the table's own scroll box, and no fixed width wider than 375 px.
// Still owed to a real browser (manual in /check verify, or Playwright if it is added):
// measuring `scrollWidth <= 375` on every page, the actual column stacking below 640 px, and
// the real builder rows (feature 10), which do not exist yet.
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { FormRow } from "@/components/form-row";

import { PAGES, renderPage } from "./pages";

// The App Router is not mounted in jsdom; `/backtest` reads its inputs through `useSearchParams`.
vi.mock("next/navigation", async (importOriginal) =>
  (await import("./navigation")).emulatedNavigation(await importOriginal<object>()),
);

const VIEWPORT_PX = 375;

/** Fixed widths in px that a page could carry: Tailwind arbitrary values and inline styles. */
function fixedWidthsOver(root: HTMLElement, limit: number): string[] {
  const offenders: string[] = [];
  const arbitrary = /(?:^|\s)(?:[a-z0-9]+:)*(?:min-)?w-\[(\d+(?:\.\d+)?)px\]/g;
  for (const el of [root, ...root.querySelectorAll<HTMLElement>("*")]) {
    const cls = el.getAttribute("class") ?? "";
    for (const match of cls.matchAll(arbitrary)) {
      if (Number(match[1]) > limit)
        offenders.push(`${el.tagName.toLowerCase()}.${match[0].trim()}`);
    }
    for (const prop of ["width", "minWidth"] as const) {
      const value = el.style[prop];
      const px = /^(\d+(?:\.\d+)?)px$/.exec(value);
      if (px && Number(px[1]) > limit)
        offenders.push(`${el.tagName.toLowerCase()} style ${prop}: ${value}`);
    }
  }
  return offenders;
}

describe.each(PAGES)("page $path", ({ Page }) => {
  it("U-6: carries no fixed width wider than a 375 px viewport", async () => {
    const { container } = renderPage(Page);
    await screen.findByText(/API ready/);
    expect(fixedWidthsOver(container, VIEWPORT_PX)).toEqual([]);
  });

  it("U-6: every table on the page sits inside its own scroll box", async () => {
    renderPage(Page);
    await screen.findByText(/API ready/);
    for (const table of screen.queryAllByRole("table")) {
      const box = table.closest('[role="region"]');
      expect(box, "table outside a scroll region").not.toBeNull();
      expect(box).toHaveClass("overflow-auto");
    }
  });
});

interface WideRow {
  id: string;
  [column: string]: string | number;
}

const WIDE_COLUMNS: DataTableColumn<WideRow>[] = Array.from({ length: 12 }, (_, i) => ({
  accessorKey: `c${i}`,
  header: `Column ${i + 1}`,
  meta: { numeric: true },
}));

const WIDE_ROWS: WideRow[] = Array.from({ length: 3 }, (_, r) => ({
  id: `r${r}`,
  ...Object.fromEntries(Array.from({ length: 12 }, (_, i) => [`c${i}`, r * 100 + i])),
}));

describe("U-6 shared parts", () => {
  it("U-6: a 12 column table scrolls inside a labelled, keyboard focusable box", () => {
    render(
      <DataTable
        columns={WIDE_COLUMNS}
        data={WIDE_ROWS}
        getRowId={(row) => row.id}
        caption="Twelve columns"
      />,
    );
    const box = screen.getByRole("region", { name: "Twelve columns" });
    expect(box).toHaveClass("overflow-auto");
    expect(box).toHaveAttribute("tabindex", "0");
    expect(within(box).getByRole("table")).toBeInTheDocument();
    expect(within(box).getAllByRole("columnheader")).toHaveLength(12);
  });

  it.each([2, 3, 4] as const)(
    "U-6: a %i column form row is one column by default and widens only at the sm breakpoint",
    (columns) => {
      const { container } = render(
        <FormRow columns={columns}>
          <label>
            A <input />
          </label>
          <label>
            B <input />
          </label>
        </FormRow>,
      );
      const row = container.firstElementChild as HTMLElement;
      const classes = (row.getAttribute("class") ?? "").split(/\s+/);
      expect(classes).toContain("grid-cols-1");
      expect(classes).toContain(`sm:grid-cols-${columns}`);
      const unprefixedMulti = classes.filter((c) => /^grid-cols-(?!1$)/.test(c));
      expect(unprefixedMulti).toEqual([]);
      expect(classes).toContain("*:min-w-0");
    },
  );
});

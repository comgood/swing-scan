import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { DataTable, type DataTableColumn } from "./data-table";

interface Row {
  id: string;
  name: string;
  score: number | null;
  best?: boolean;
}

const COLUMNS: DataTableColumn<Row>[] = [
  { accessorKey: "name", header: "Name" },
  {
    accessorKey: "score",
    header: "Score",
    meta: { numeric: true, highlight: (row) => row.best === true },
  },
];

const ROWS: Row[] = [
  { id: "a", name: "bravo", score: 2 },
  { id: "b", name: "Alpha", score: null },
  { id: "c", name: "charlie", score: 5, best: true },
  { id: "d", name: "delta", score: 2 },
  { id: "e", name: "alpha", score: null },
];

function names(): string[] {
  const body = screen.getAllByRole("rowgroup")[1];
  return within(body)
    .getAllByRole("row")
    .map((row) => within(row).getAllByRole("cell")[0].textContent ?? "");
}

function header(name: string) {
  return screen.getByRole("columnheader", { name: new RegExp(name) });
}

describe("DataTable (AC-8)", () => {
  it("sorts numeric columns descending first, then ascending, then clears; nulls last both ways", async () => {
    const user = userEvent.setup();
    render(<DataTable columns={COLUMNS} data={ROWS} getRowId={(r) => r.id} caption="Scores" />);
    const score = header("Score");
    expect(score).toHaveAttribute("aria-sort", "none");

    await user.click(within(score).getByRole("button"));
    expect(score).toHaveAttribute("aria-sort", "descending");
    expect(names()).toEqual(["charlie", "bravo", "delta", "Alpha", "alpha"]);

    await user.click(within(score).getByRole("button"));
    expect(score).toHaveAttribute("aria-sort", "ascending");
    expect(names()).toEqual(["bravo", "delta", "charlie", "Alpha", "alpha"]);

    await user.click(within(score).getByRole("button"));
    expect(score).toHaveAttribute("aria-sort", "none");
    expect(names()).toEqual(["bravo", "Alpha", "charlie", "delta", "alpha"]);
  });

  it("sorts text ascending first, case insensitive, keeping input order on ties", async () => {
    const user = userEvent.setup();
    render(<DataTable columns={COLUMNS} data={ROWS} getRowId={(r) => r.id} caption="Scores" />);
    await user.click(within(header("Name")).getByRole("button"));
    expect(header("Name")).toHaveAttribute("aria-sort", "ascending");
    expect(names()).toEqual(["Alpha", "alpha", "bravo", "charlie", "delta"]);
    expect(header("Score")).toHaveAttribute("aria-sort", "none");
  });

  it("shows n/a for nulls, right aligns numbers, and paints highlighted cells", () => {
    render(<DataTable columns={COLUMNS} data={ROWS} getRowId={(r) => r.id} caption="Scores" />);
    const cells = screen.getAllByRole("cell").filter((c) => c.textContent === "n/a");
    expect(cells).toHaveLength(2);
    expect(cells[0]).toHaveClass("text-right", "tabular-nums");
    expect(screen.getByRole("cell", { name: "5" })).toHaveClass("bg-accent");
    for (const cell of screen.getAllByRole("cell", { name: "2" })) {
      expect(cell).not.toHaveClass("bg-accent");
    }
  });

  it("scrolls inside a focusable region named by the caption, which is hidden unless visible", () => {
    render(<DataTable columns={COLUMNS} data={ROWS} getRowId={(r) => r.id} caption="Scores" />);
    const region = screen.getByRole("region", { name: "Scores" });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region).toHaveClass("overflow-auto");
    expect(screen.getByRole("table", { name: "Scores" })).toBeInTheDocument();
    expect(screen.getByText("Scores", { selector: "caption" })).toHaveClass("sr-only");
  });

  it("shows the empty node when there are no rows", () => {
    render(
      <DataTable
        columns={COLUMNS}
        data={[]}
        getRowId={(r) => r.id}
        caption="Scores"
        empty="Nothing yet"
      />,
    );
    expect(screen.getByText("Nothing yet")).toBeInTheDocument();
  });

  it("pages, disables the ends, and returns to page 1 on sort and on new data", async () => {
    const user = userEvent.setup();
    const many: Row[] = Array.from({ length: 7 }, (_, i) => ({
      id: `r${i}`,
      name: `n${i}`,
      score: i,
    }));
    const { rerender } = render(
      <DataTable
        columns={COLUMNS}
        data={many}
        getRowId={(r) => r.id}
        caption="Scores"
        pageSize={3}
      />,
    );
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Page 3 of 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(names()).toEqual(["n6"]);

    await user.click(within(header("Score")).getByRole("button"));
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
    expect(names()).toEqual(["n6", "n5", "n4"]);

    await user.click(screen.getByRole("button", { name: "Next" }));
    rerender(
      <DataTable
        columns={COLUMNS}
        data={[...many]}
        getRowId={(r) => r.id}
        caption="Scores"
        pageSize={3}
      />,
    );
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
  });

  it("hides the page controls when everything fits on one page", () => {
    render(
      <DataTable
        columns={COLUMNS}
        data={ROWS}
        getRowId={(r) => r.id}
        caption="Scores"
        pageSize={50}
      />,
    );
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
  });

  it("starts from initialSort and shows a visible caption when asked", () => {
    render(
      <DataTable
        columns={COLUMNS}
        data={ROWS}
        getRowId={(r) => r.id}
        caption="Scores"
        captionVisible
        initialSort={{ id: "score", desc: true }}
      />,
    );
    expect(header("Score")).toHaveAttribute("aria-sort", "descending");
    expect(names()).toEqual(["charlie", "bravo", "delta", "Alpha", "alpha"]);
    expect(screen.getByText("Scores", { selector: "caption" })).not.toHaveClass("sr-only");
  });

  it("gives a column with sortable false no button and no aria-sort", () => {
    const columns: DataTableColumn<Row>[] = [
      { accessorKey: "name", header: "Name", meta: { sortable: false } },
      COLUMNS[1],
    ];
    render(<DataTable columns={columns} data={ROWS} getRowId={(r) => r.id} caption="Scores" />);
    expect(header("Name")).not.toHaveAttribute("aria-sort");
    expect(within(header("Name")).queryByRole("button")).not.toBeInTheDocument();
  });

  it("hides the sort icon from assistive tech, so the button is named by its header text", () => {
    render(<DataTable columns={COLUMNS} data={ROWS} getRowId={(r) => r.id} caption="Scores" />);
    const button = within(header("Score")).getByRole("button", { name: "Score" });
    expect(button.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("uses the row id from getRowId, so rows keep identity across sorts", async () => {
    const user = userEvent.setup();
    render(
      <DataTable columns={COLUMNS} data={ROWS} getRowId={(r) => `row-${r.id}`} caption="Scores" />,
    );
    const before = screen.getByRole("cell", { name: "charlie" }).closest("tr");
    await user.click(within(header("Score")).getByRole("button"));
    expect(screen.getByRole("cell", { name: "charlie" }).closest("tr")).toBe(before);
  });
});

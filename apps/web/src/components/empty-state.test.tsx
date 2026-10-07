import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "./empty-state";

// covers: AC-11 (EmptyState: title plus one line hint)
describe("EmptyState (AC-11)", () => {
  it("shows the title and the hint", () => {
    render(<EmptyState title="No hits today" hint="Try another template or date." />);
    expect(screen.getByText("No hits today")).toBeInTheDocument();
    expect(screen.getByText("Try another template or date.")).toBeInTheDocument();
  });

  it("shows only the title when there is no hint", () => {
    const { container } = render(<EmptyState title="No trades yet" />);
    expect(container).toHaveTextContent(/^No trades yet$/);
  });
});

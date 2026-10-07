import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Banner } from "./banner";

describe("Banner (AC-11)", () => {
  it("gives danger role=alert and leaves info and warning static", () => {
    render(
      <>
        <Banner variant="info">Info text</Banner>
        <Banner variant="warning">Warning text</Banner>
        <Banner variant="danger">Danger text</Banner>
      </>,
    );
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByRole("alert")).toHaveTextContent("Danger text");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("hides the icon and wraps long text", () => {
    const { container } = render(
      <Banner variant="warning">Synthetic market: not real prices</Banner>,
    );
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("Synthetic market: not real prices")).toHaveClass("break-words");
  });
});

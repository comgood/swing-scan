import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FormErrorSummary } from "./form-error-summary";

// covers: AC-7 (FormErrorSummary lists form errors in a role="alert" region)
describe("FormErrorSummary (AC-7)", () => {
  it("renders nothing when there are no form errors", () => {
    const { container } = render(<FormErrorSummary errors={[]} />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("announces a single error in an alert", () => {
    render(<FormErrorSummary errors={["Rule needs at least one condition"]} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Fix this before running");
    expect(alert).toHaveTextContent("Rule needs at least one condition");
  });

  it("lists several errors in order, with a custom title", () => {
    render(
      <FormErrorSummary errors={["First problem", "Second problem"]} title="Can't run this rule" />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Can't run this rule");
    const items = within(alert)
      .getAllByRole("listitem")
      .map((li) => li.textContent);
    expect(items).toEqual(["First problem", "Second problem"]);
  });
});

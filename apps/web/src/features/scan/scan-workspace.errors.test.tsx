// covers the UAT fix (batch 1): a 422 on the rule's name is not suppressed when a row is added,
// because the name does not move with the rows. Row errors still are.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/mocks/node";
import { renderWithQuery } from "@/test/render";

import { ScanWorkspace } from "./scan-workspace";

const NAME_422 = "Name must be given";
const ROW_422 = "Must be between 2 and 50";

function reject() {
  server.use(
    http.post("*/api/v1/scan", () =>
      HttpResponse.json(
        {
          detail: [
            { type: "value_error", loc: ["body", "rule", "name"], msg: NAME_422, input: null },
            {
              type: "value_error",
              loc: ["body", "rule", "conditions", 0, "left", "n"],
              msg: ROW_422,
              input: null,
            },
          ],
        },
        { status: 422 },
      ),
    ),
  );
}

describe("ScanWorkspace 422 after the rows changed", () => {
  it("keeps the name error and drops the row error when a condition is added", async () => {
    reject();
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    await screen.findByLabelText("Template");

    await waitFor(() => expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid"));
    const row1 = () => screen.getByRole("group", { name: "Condition 1" });
    expect(within(row1()).getByText(ROW_422)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Add condition" }));

    expect(screen.getByLabelText("Name")).toHaveAccessibleDescription(
      expect.stringContaining(NAME_422),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(NAME_422);
    expect(within(row1()).queryByText(ROW_422)).not.toBeInTheDocument();
  });
});

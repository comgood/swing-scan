// covers: spec 0014 AC-2 (a saved rule loads back into the builder), AC-6 (the whole feature is
// absent while the API answers 501). The component's own behaviour is in saved-rules.test.tsx;
// this is the wiring: the section is mounted on the page, and Load reaches the real builder.
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { STALE_TEXT } from "@/features/rule-builder";
import { mocks, savedRulesHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { renderWithQuery } from "@/test/render";

import { ScanWorkspace } from "./scan-workspace";

const SAVED = mocks.savedRules[1]!;

describe("ScanWorkspace saved rules", () => {
  it("has no saved rules section while the API answers 501 (AC-6)", async () => {
    renderWithQuery(<ScanWorkspace />); // the default handler is the 501
    await screen.findByLabelText("Template");
    expect(screen.queryByRole("heading", { name: "Saved rules" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save this rule" })).not.toBeInTheDocument();
  });

  it("loads a saved rule into the builder, name and conditions (AC-2)", async () => {
    server.use(savedRulesHandler());
    renderWithQuery(<ScanWorkspace />);
    // The section waits on the templates, the catalog and its own list, so give it room.
    await screen.findByRole("heading", { name: "Saved rules" }, { timeout: 4000 });
    await userEvent.click(screen.getByRole("button", { name: `Load ${SAVED.rule.name}` }));

    // The builder now holds the saved rule, not the template it opened on.
    expect(screen.getByLabelText("Name")).toHaveValue(SAVED.rule.name);
    expect(screen.getAllByText(/^Condition \d+$/)).toHaveLength(SAVED.rule.conditions.length);
    // Loading does not run a scan: the rule is yours to edit first (spec 0008 AC-8).
    expect(await screen.findByText(STALE_TEXT)).toBeVisible();
  });
});

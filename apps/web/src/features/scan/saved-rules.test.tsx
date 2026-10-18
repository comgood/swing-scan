// covers: spec 0014 AC-2 (a loaded rule is the saved rule), AC-3 (a 422 is readable),
// AC-4 (a duplicate name says so), AC-6 (the whole feature is hidden on a 501)
import type { Rule, SavedRule } from "@swing-scan/api-client";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { mocks, savedRulesHandler, saveRuleHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";
import { renderWithQuery } from "@/test/render";

import { EMPTY_TEXT, SavedRules } from "./saved-rules";

const RULE = mocks.templates[0]!.rule;

/**
 * The three routes over one list that saving and deleting really change, so a refetch answers
 * with what the last write left behind rather than a body the test swapped in at the right
 * moment. Name uniqueness ignores case, as the database's `lower(name)` index does.
 */
function store(rows: SavedRule[]): SavedRule[] {
  server.use(
    http.get("*/api/v1/rules", () => HttpResponse.json(rows)),
    http.post("*/api/v1/rules", async ({ request }) => {
      const rule = (await request.json()) as Rule;
      if (rows.some((r) => r.rule.name.toLowerCase() === rule.name.toLowerCase())) {
        return HttpResponse.json(
          { detail: `A rule named '${rule.name}' is already saved.` },
          {
            status: 409,
          },
        );
      }
      const saved = { id: `0000000${rows.length}-0000-4000-8000-000000000000`, rule };
      rows.push(saved);
      return HttpResponse.json(saved);
    }),
    http.delete("*/api/v1/rules/:id", ({ params }) => {
      const at = rows.findIndex((r) => r.id === params.id);
      if (at === -1)
        return HttpResponse.json({ detail: "No saved rule has that id." }, { status: 404 });
      rows.splice(at, 1);
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return rows;
}

function show(onLoad: (rule: Rule) => void = () => {}) {
  return renderWithQuery(<SavedRules rule={RULE} onLoad={onLoad} />);
}

const save = () => screen.findByRole("button", { name: "Save this rule" });

describe("SavedRules", () => {
  it("renders nothing when the API answers 501, which is the deployed demo (AC-6)", async () => {
    const { container } = show(); // the default handler is the 501
    // Nothing appears later either: the query does not retry, so one 501 is the final answer.
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(screen.queryByRole("button", { name: "Save this rule" })).not.toBeInTheDocument();
  });

  it("says so while nothing is saved, then lists what is", async () => {
    const rows = store([]);
    const { container } = show();
    expect(await screen.findByText(EMPTY_TEXT)).toBeVisible();

    await userEvent.click(await save());
    expect(await screen.findByText(RULE.name)).toBeVisible();
    expect(rows).toHaveLength(1);
    await expectNoAxeViolations(container);
  });

  it("loads a saved rule back, field for field (AC-2)", async () => {
    const saved = mocks.savedRules[1]!;
    store([saved]);
    const onLoad = vi.fn();
    show(onLoad);
    await userEvent.click(await screen.findByRole("button", { name: "Load" }));
    expect(onLoad).toHaveBeenCalledWith(saved.rule);
  });

  it("says a name is already taken rather than overwriting it (AC-4)", async () => {
    // Saved under the same name, in a different case: the 409 is the database's own index.
    store([
      {
        id: "0000000a-0000-4000-8000-000000000000",
        rule: { ...RULE, name: RULE.name.toUpperCase() },
      },
    ]);
    show();
    await userEvent.click(await save());
    expect(await screen.findByRole("alert")).toHaveTextContent("already saved");
  });

  it("shows a rejected rule's own field error (AC-3)", async () => {
    // The same 422 body `/scan` produces, through the same `fieldErrorsFrom422` mapping.
    server.use(savedRulesHandler("empty"), saveRuleHandler("422.rule.unknown_indicator"));
    show();
    await userEvent.click(await save());
    // The message is the contract's own, unchanged: the indicator is not one it knows.
    expect(await screen.findByRole("alert")).toHaveTextContent("Input should be 'open'");
  });

  it("deletes one and shows the list without it", async () => {
    const saved = mocks.savedRules[0]!;
    const rows = store([saved]);
    show();
    const name = saved.rule.name;
    await userEvent.click(await screen.findByRole("button", { name: `Delete ${name}` }));
    expect(await screen.findByText(EMPTY_TEXT)).toBeVisible();
    expect(rows).toHaveLength(0);
  });
});

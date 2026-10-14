// covers: spec 0008 decision 10 (JSON panel: Copy, Load, "Not a rule" changes nothing), AC-1,
// AC-10 (labels and axe)
import type { Rule } from "@swing-scan/api-client";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mocks } from "@/mocks/handlers";
import { expectNoAxeViolations } from "@/test/axe";

import { JsonPanel, NOT_A_RULE, parseRuleText } from "./json-panel";

const NAMES = mocks.indicators.map((s) => s.name);
const breakout = mocks.templates.find((t) => t.id === "breakout_52w")!.rule;
const pullback = mocks.templates.find((t) => t.id === "pullback_ema21")!.rule;

function setup(props: { rule?: Rule; defaultDraft?: string; defaultError?: boolean } = {}) {
  const user = userEvent.setup();
  const onLoad = vi.fn<(rule: Rule) => void>();
  const view = render(
    <JsonPanel rule={breakout} names={NAMES} onLoad={onLoad} defaultOpen {...props} />,
  );
  const paste = () => screen.getByLabelText("Paste a rule");
  const load = () => screen.getByRole("button", { name: "Load rule" });
  return { user, onLoad, paste, load, ...view };
}

async function pasteText(user: ReturnType<typeof userEvent.setup>, box: HTMLElement, text: string) {
  await user.click(box);
  await user.paste(text);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("parseRuleText", () => {
  it("returns the rule for its own JSON, compact or pretty", () => {
    expect(parseRuleText(JSON.stringify(pullback), NAMES)).toEqual(pullback);
    expect(parseRuleText(JSON.stringify(pullback, null, 2), NAMES)).toEqual(pullback);
  });

  it.each([
    ["empty text", ""],
    ["broken JSON", '{"name": '],
    ["a bare string", '"rule"'],
    ["a rule with an unknown indicator", JSON.stringify({ ...breakout, conditions: [{}] })],
  ])("returns null for %s", (_label, text) => {
    expect(parseRuleText(text, NAMES)).toBeNull();
  });
});

describe("JsonPanel", () => {
  it("shows the rule as pretty printed JSON", () => {
    setup();
    expect(screen.getByLabelText("Rule JSON").textContent).toBe(JSON.stringify(breakout, null, 2));
  });

  it("copies the shown JSON and says Copied", async () => {
    const { user } = setup();
    expect(screen.getByRole("status")).toHaveTextContent("");
    await user.click(screen.getByRole("button", { name: "Copy JSON" }));
    expect(await navigator.clipboard.readText()).toBe(JSON.stringify(breakout, null, 2));
    expect(screen.getByRole("status")).toHaveTextContent("Copied");
  });

  it("says nothing when the clipboard refuses", async () => {
    const { user } = setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
    await user.click(screen.getByRole("button", { name: "Copy JSON" }));
    expect(screen.getByRole("status")).toHaveTextContent("");
  });

  it("loads a valid rule in canonical form and clears the paste box", async () => {
    const { user, onLoad, paste, load } = setup();
    const withoutN = structuredClone(pullback) as unknown as {
      conditions: { left: Record<string, unknown> }[];
    };
    for (const c of withoutN.conditions) if (c.left.n === null) delete c.left.n;
    await pasteText(user, paste(), JSON.stringify(withoutN));
    await user.click(load());
    expect(onLoad).toHaveBeenCalledTimes(1);
    expect(onLoad).toHaveBeenCalledWith(pullback);
    expect(paste()).toHaveValue("");
    expect(screen.queryByText(NOT_A_RULE)).not.toBeInTheDocument();
  });

  it.each([
    ["text that is not JSON", "close > sma(50)"],
    ["JSON that is not a rule", '{"name": "x"}'],
    [
      "a rule with nine conditions",
      JSON.stringify({ name: "r", conditions: Array(9).fill(breakout.conditions[0]) }),
    ],
  ])("says Not a rule for %s and changes nothing", async (_label, text) => {
    const { user, onLoad, paste, load } = setup();
    await pasteText(user, paste(), text);
    await user.click(load());
    expect(screen.getByText(NOT_A_RULE)).toBeInTheDocument();
    expect(onLoad).not.toHaveBeenCalled();
    expect(paste()).toHaveValue(text);
    expect(paste()).toHaveAttribute("aria-invalid", "true");
    expect(paste()).toHaveAccessibleDescription(expect.stringContaining(NOT_A_RULE));
    expect(screen.getByLabelText("Rule JSON").textContent).toBe(JSON.stringify(breakout, null, 2));
  });

  it("clears Not a rule as soon as you edit the paste box", async () => {
    const { user, paste, load } = setup();
    await pasteText(user, paste(), "nope");
    await user.click(load());
    expect(screen.getByText(NOT_A_RULE)).toBeInTheDocument();
    await user.type(paste(), "!");
    expect(screen.queryByText(NOT_A_RULE)).not.toBeInTheDocument();
  });

  it("disables Load rule while the paste box is empty or only spaces", async () => {
    const { user, paste, load } = setup();
    expect(load()).toBeDisabled();
    await user.type(paste(), "   ");
    expect(load()).toBeDisabled();
  });

  it("copies and loads from the keyboard alone", async () => {
    const { user, onLoad, paste } = setup();
    screen.getByRole("button", { name: "Copy JSON" }).focus();
    await user.keyboard("{Enter}");
    expect(await navigator.clipboard.readText()).toBe(JSON.stringify(breakout, null, 2));
    await user.tab();
    expect(paste()).toHaveFocus();
    await user.paste(JSON.stringify(pullback));
    await user.tab();
    expect(screen.getByRole("button", { name: "Load rule" })).toHaveFocus();
    await user.keyboard(" ");
    expect(onLoad).toHaveBeenCalledWith(pullback);
  });

  it("has no axe violations while it shows Not a rule", async () => {
    const { container } = setup({ defaultDraft: "nope", defaultError: true });
    expect(screen.getByText(NOT_A_RULE)).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { NumberInput, parseNumberText, type NumberInputProps } from "./number-input";

function setup(props: Partial<NumberInputProps> = {}) {
  const onValueChange = vi.fn();
  const view = render(
    <NumberInput label="Lookback" value={20} onValueChange={onValueChange} {...props} />,
  );
  return { onValueChange, input: screen.getByLabelText("Lookback"), ...view };
}

describe("parseNumberText (AC-6)", () => {
  it.each([
    ["", null],
    ["  ", null],
    ["2", 2],
    ["-2.5", -2.5],
    [".5", 0.5],
    ["2.", 2],
    ["2.50", 2.5],
    ["-0", 0],
  ])("accepts %j as %j", (text, value) => {
    const parsed = parseNumberText(text, false);
    expect(parsed).toEqual({ ok: true, value });
    if (parsed.ok && value === 0) expect(Object.is(parsed.value, -0)).toBe(false);
  });

  it.each(["abc", "1e3", "1,000", "+5", "Infinity", "--1", "."])("rejects %j", (text) => {
    expect(parseNumberText(text, false)).toEqual({ ok: false, message: "Enter a number" });
  });

  it("asks for a whole number in integer mode, but accepts 2.0", () => {
    expect(parseNumberText("2.5", true)).toEqual({ ok: false, message: "Enter a whole number" });
    expect(parseNumberText("2.0", true)).toEqual({ ok: true, value: 2 });
  });
});

describe("NumberInput (AC-6)", () => {
  it("is a labelled text input with a decimal or numeric keyboard", () => {
    const { input } = setup();
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveAttribute("inputmode", "decimal");
    setup({ label: "Bars", integer: true });
    expect(screen.getByLabelText("Bars")).toHaveAttribute("inputmode", "numeric");
  });

  it("commits on blur and shows the canonical text", async () => {
    const user = userEvent.setup();
    const { input, onValueChange } = setup();
    await user.clear(input);
    await user.type(input, " 2.50 ");
    expect(onValueChange).not.toHaveBeenCalled();
    await user.tab();
    expect(onValueChange).toHaveBeenCalledWith(2.5);
    expect(input).toHaveValue("2.5");
  });

  it("commits on Enter without blocking the form submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    const onValueChange = vi.fn();
    render(
      <form onSubmit={onSubmit}>
        <NumberInput label="Lookback" value={20} onValueChange={onValueChange} />
        <button type="submit">Run</button>
      </form>,
    );
    const input = screen.getByLabelText("Lookback");
    await user.clear(input);
    await user.type(input, "30{Enter}");
    expect(onValueChange).toHaveBeenCalledWith(30);
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("gives null for empty text", async () => {
    const user = userEvent.setup();
    const { input, onValueChange } = setup();
    await user.clear(input);
    await user.tab();
    expect(onValueChange).toHaveBeenCalledWith(null);
  });

  it("emits nothing when the committed value is unchanged", async () => {
    const user = userEvent.setup();
    const { input, onValueChange } = setup();
    await user.clear(input);
    await user.type(input, "20.0");
    await user.tab();
    expect(onValueChange).not.toHaveBeenCalled();
    expect(input).toHaveValue("20");
  });

  it.each(["abc", "1e3"])(
    "keeps the draft %j, emits nothing, and shows the error, wired to the input",
    async (text) => {
      const user = userEvent.setup();
      const { input, onValueChange } = setup();
      await user.clear(input);
      await user.type(input, text);
      await user.tab();
      expect(onValueChange).not.toHaveBeenCalled();
      expect(input).toHaveValue(text);
      expect(input).toHaveAttribute("aria-invalid", "true");
      expect(input).toHaveAccessibleDescription(expect.stringContaining("Enter a number"));
    },
  );

  it("shows Enter a whole number for 2.5 in integer mode", async () => {
    const user = userEvent.setup();
    const { input } = setup({ integer: true });
    await user.clear(input);
    await user.type(input, "2.5");
    await user.tab();
    expect(screen.getByText("Enter a whole number")).toBeInTheDocument();
  });

  it("clears the local error as soon as you edit", async () => {
    const user = userEvent.setup();
    const { input } = setup();
    await user.clear(input);
    await user.type(input, "abc");
    await user.tab();
    expect(screen.getByText("Enter a number")).toBeInTheDocument();
    await user.type(input, "x");
    expect(screen.queryByText("Enter a number")).not.toBeInTheDocument();
  });

  it("never clamps: 999 with max 260 is emitted unchanged", async () => {
    const user = userEvent.setup();
    const { input, onValueChange } = setup({ min: 2, max: 260, integer: true });
    await user.clear(input);
    await user.type(input, "999");
    await user.tab();
    expect(onValueChange).toHaveBeenCalledWith(999);
  });

  it("shows the range hint only with both min and max", () => {
    setup({ min: 2, max: 260 });
    expect(screen.getByText("Allowed: 2 to 260")).toBeInTheDocument();
    setup({ label: "Only min", min: 2 });
    expect(screen.getByLabelText("Only min")).not.toHaveAccessibleDescription(
      expect.stringContaining("Allowed"),
    );
  });

  it("shows a server error, which a local parse error replaces, with the hint kept", async () => {
    const user = userEvent.setup();
    const { input } = setup({ min: 2, max: 260, error: "Must be between 2 and 260" });
    expect(input).toHaveAccessibleDescription(expect.stringContaining("Must be between 2 and 260"));
    expect(input).toHaveAccessibleDescription(expect.stringContaining("Allowed: 2 to 260"));
    await user.clear(input);
    await user.type(input, "abc");
    await user.tab();
    expect(screen.getByText("Enter a number")).toBeInTheDocument();
    expect(screen.queryByText("Must be between 2 and 260")).not.toBeInTheDocument();
    expect(screen.getByText("Allowed: 2 to 260")).toBeInTheDocument();
  });

  it("replaces the draft when the value changes from outside while not focused", async () => {
    function Harness() {
      const [value, setValue] = useState<number | null>(20);
      return (
        <>
          <NumberInput label="Lookback" value={value} onValueChange={setValue} />
          <button type="button" onClick={() => setValue(55)}>
            Load template
          </button>
        </>
      );
    }
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Load template" }));
    expect(screen.getByLabelText("Lookback")).toHaveValue("55");
  });
});

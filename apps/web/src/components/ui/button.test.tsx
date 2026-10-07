import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Field, FieldDescription, FieldError, FieldLabel } from "./field";
import { Button } from "./button";
import { Input } from "./input";
import { NativeSelect, NativeSelectOption } from "./native-select";

describe("Button loading (AC-5)", () => {
  it("is busy, ignores clicks, keeps focus, and keeps its label for width", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Run backtest
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Run backtest" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).not.toBeDisabled();
    await user.click(button);
    expect(onClick).not.toHaveBeenCalled();
    expect(button).toHaveFocus();
    // jsdom applies no Tailwind CSS, so guard the class itself: `invisible` (visibility:
    // hidden) would drop the label from the accessibility tree and leave the button unnamed.
    const label = screen.getByText("Run backtest");
    expect(label).toHaveClass("opacity-0");
    for (const hiding of ["invisible", "hidden", "sr-only"]) expect(label).not.toHaveClass(hiding);
  });

  it("does not submit its form while loading", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <Button type="submit" loading>
          Run
        </Button>
      </form>,
    );
    await user.click(screen.getByRole("button", { name: "Run" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("clicks normally when not loading", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await user.click(screen.getByRole("button", { name: "Go" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe("Field wiring (AC-5)", () => {
  it("labels the input and lists the description and error in aria-describedby", () => {
    render(
      <Field invalid>
        <FieldLabel>Ticker</FieldLabel>
        <Input />
        <FieldDescription>Letters only</FieldDescription>
        <FieldError>Use letters only</FieldError>
      </Field>,
    );
    const input = screen.getByLabelText("Ticker");
    expect(input).toHaveAttribute("aria-invalid", "true");
    const ids = (input.getAttribute("aria-describedby") ?? "").split(" ");
    const described = ids.map((id) => document.getElementById(id)?.textContent);
    expect(described).toEqual(expect.arrayContaining(["Letters only", "Use letters only"]));
    const error = screen.getByText("Use letters only").parentElement;
    expect(error).toHaveClass("text-destructive");
    expect(error?.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("has no error and no aria-invalid when valid", () => {
    render(
      <Field>
        <FieldLabel>Name</FieldLabel>
        <Input />
        <FieldError>{undefined}</FieldError>
      </Field>,
    );
    expect(screen.getByLabelText("Name")).not.toHaveAttribute("aria-invalid", "true");
  });

  it("labels a native select through the same Field", () => {
    render(
      <Field invalid>
        <FieldLabel>Template</FieldLabel>
        <NativeSelect defaultValue="b">
          <NativeSelectOption value="a">Breakout</NativeSelectOption>
          <NativeSelectOption value="b">Pullback</NativeSelectOption>
        </NativeSelect>
        <FieldError>Pick one</FieldError>
      </Field>,
    );
    const select = screen.getByRole("combobox", { name: "Template" });
    expect(select).toHaveValue("b");
    expect(select).toHaveAttribute("aria-invalid", "true");
    expect(select).toHaveAccessibleDescription("Pick one");
  });
});

import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WarmupNotice } from "./warmup-notice";

describe("WarmupNotice (AC-9)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("is an always present polite live region, empty while not pending", () => {
    render(<WarmupNotice pending={false} />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toBeEmptyDOMElement();
  });

  it("stays empty for 1,499 ms, shows at 1,500 ms, and empties when pending ends", () => {
    const { rerender } = render(<WarmupNotice pending />);
    const region = screen.getByRole("status");
    act(() => vi.advanceTimersByTime(1499));
    expect(region).toBeEmptyDOMElement();
    act(() => vi.advanceTimersByTime(1));
    expect(region).toHaveTextContent("Warming up the engine…");
    expect(region.querySelector("svg")).toHaveAttribute("aria-hidden", "true");

    rerender(<WarmupNotice pending={false} />);
    expect(region).toBeEmptyDOMElement();
  });

  it("restarts the timer on the next request", () => {
    const { rerender } = render(<WarmupNotice pending />);
    act(() => vi.advanceTimersByTime(1000));
    rerender(<WarmupNotice pending={false} />);
    rerender(<WarmupNotice pending />);
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    act(() => vi.advanceTimersByTime(500));
    expect(screen.getByRole("status")).toHaveTextContent("Warming up the engine…");
  });
});

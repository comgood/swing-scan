import { render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

// A fake worker that, like MSW, refuses a second start on the same page.
const start = vi.fn(async () => {
  if (start.mock.calls.length > 1) {
    throw new Error("cannot configure an already enabled network");
  }
});
vi.mock("./browser", () => ({ worker: { start } }));

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
  start.mockClear();
});

async function loadProvider(mock: "1" | "") {
  vi.stubEnv("NEXT_PUBLIC_API_MOCK", mock);
  vi.resetModules();
  return (await import("./mock-provider")).MockProvider;
}

describe("MockProvider (spec 0002 AC-13, spec 0003 AC-4)", () => {
  it("starts the worker once and then renders, even when React runs effects twice", async () => {
    const MockProvider = await loadProvider("1");
    render(
      <StrictMode>
        <MockProvider>
          <p>App content</p>
        </MockProvider>
      </StrictMode>,
    );
    expect(await screen.findByText("App content")).toBeInTheDocument();
    expect(start).toHaveBeenCalledTimes(1);
    expect(start).toHaveBeenCalledWith({ onUnhandledRequest: "bypass" });
  });

  it("holds the children back until the worker has started", async () => {
    let finish: () => void = () => undefined;
    start.mockImplementationOnce(() => new Promise<void>((resolve) => (finish = resolve)));
    const MockProvider = await loadProvider("1");
    render(
      <MockProvider>
        <p>App content</p>
      </MockProvider>,
    );
    await vi.waitFor(() => expect(start).toHaveBeenCalled());
    expect(screen.queryByText("App content")).not.toBeInTheDocument();
    finish();
    expect(await screen.findByText("App content")).toBeInTheDocument();
  });

  it("renders straight away and never loads the worker with mocks off", async () => {
    const MockProvider = await loadProvider("");
    render(
      <StrictMode>
        <MockProvider>
          <p>App content</p>
        </MockProvider>
      </StrictMode>,
    );
    expect(screen.getByText("App content")).toBeInTheDocument();
    expect(start).not.toHaveBeenCalled();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { toApiError } from "@/lib/api-error";
import { scanHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { http, HttpResponse } from "msw";

import { ErrorState } from "./error-state";

const REQUEST = { rule: { conditions: [] }, as_of: null } as never;

describe("toApiError (AC-10)", () => {
  it("keeps the string detail of a 501 from the contract mock", async () => {
    server.use(scanHandler("501.scan"));
    const result = await api.POST("/api/v1/scan", { body: REQUEST });
    expect(toApiError(result)).toEqual({
      kind: "http",
      status: 501,
      detail: "scan is not implemented yet; it arrives with scope feature 8 (Template scan).",
    });
  });

  it("drops a list detail and maps 504 to a timeout", async () => {
    server.use(scanHandler("422.rule.n_out_of_range"));
    expect(toApiError(await api.POST("/api/v1/scan", { body: REQUEST }))).toEqual({
      kind: "http",
      status: 422,
    });
    server.use(http.post("*/api/v1/scan", () => HttpResponse.json({}, { status: 504 })));
    expect(toApiError(await api.POST("/api/v1/scan", { body: REQUEST }))).toEqual({
      kind: "timeout",
    });
  });

  it("maps a thrown network error and an abort or timeout", async () => {
    server.use(http.post("*/api/v1/scan", () => HttpResponse.error()));
    const thrown = await api.POST("/api/v1/scan", { body: REQUEST }).catch((e: unknown) => e);
    expect(toApiError(thrown)).toEqual({ kind: "network" });
    expect(toApiError(new DOMException("t", "TimeoutError"))).toEqual({ kind: "timeout" });
  });
});

describe("ErrorState (AC-10)", () => {
  it.each([
    [
      { kind: "network" } as const,
      "Can't reach the engine",
      "Check your connection and try again.",
    ],
    [{ kind: "timeout" } as const, "The engine took too long", "It may be starting up. Try again."],
    [
      { kind: "http", status: 504 } as const,
      "The engine took too long",
      "It may be starting up. Try again.",
    ],
    [
      { kind: "http", status: 500 } as const,
      "Something went wrong",
      "The API answered with status 500.",
    ],
  ])("shows %j with a working Try again", async (error, title, body) => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorState error={error} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent(body);
    expect(screen.getByRole("heading", { level: 2, name: title })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows Not built yet with the detail and no Try again for a 501", () => {
    render(
      <ErrorState
        error={{ kind: "http", status: 501, detail: "Arrives later." }}
        onRetry={() => undefined}
        headingLevel={3}
      />,
    );
    expect(screen.getByRole("heading", { level: 3, name: "Not built yet" })).toBeInTheDocument();
    expect(screen.getByText("Arrives later.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });
});

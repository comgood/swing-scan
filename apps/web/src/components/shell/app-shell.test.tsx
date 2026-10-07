import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { healthHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { renderWithQuery } from "@/test/render";

import { AppShell } from "./app-shell";
import { LIVE_TEXT, SYNTHETIC_TEXT } from "./data-mode-banner";

function renderShell() {
  return renderWithQuery(
    <AppShell>
      <p>Page content</p>
    </AppShell>,
  );
}

describe("AppShell (AC-3, AC-4)", () => {
  it("shows the synthetic banner before and after a synthetic health ping", async () => {
    renderShell();
    expect(screen.getByText(SYNTHETIC_TEXT)).toBeInTheDocument();
    expect(screen.getByText("Checking the API…")).toBeInTheDocument();
    expect(
      await screen.findByText("API ready (data: synthetic, version 0.1.0)"),
    ).toBeInTheDocument();
    expect(screen.getByText(SYNTHETIC_TEXT)).toBeInTheDocument();
  });

  it("switches to the live banner only when data_mode is exactly live", async () => {
    server.use(healthHandler("live"));
    renderShell();
    expect(await screen.findByText(LIVE_TEXT)).toBeInTheDocument();
    expect(screen.queryByText(SYNTHETIC_TEXT)).not.toBeInTheDocument();
  });

  it("keeps the synthetic banner and says the API is not reachable after the retry fails", async () => {
    server.use(healthHandler("network_error"));
    renderShell();
    expect(await screen.findByText("API not reachable", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText(SYNTHETIC_TEXT)).toBeInTheDocument();
  });

  it("orders skip link, header, main with the banner first, then the footer", async () => {
    const user = userEvent.setup();
    renderShell();
    await user.tab();
    const skip = screen.getByRole("link", { name: "Skip to content" });
    expect(skip).toHaveFocus();
    expect(skip).toHaveAttribute("href", "#main");

    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", "main");
    expect(main).toHaveAttribute("tabindex", "-1");
    expect(main).toHaveClass("max-w-7xl");
    expect(main.firstElementChild).toHaveTextContent(SYNTHETIC_TEXT);
    expect(screen.getByRole("link", { name: "Swing Scan" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("contentinfo")).toHaveTextContent(
      "Portfolio project. Not investment advice.",
    );
    await screen.findByText(/API ready/);
  });
});

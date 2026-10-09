// covers: spec 0005 AC-12 (warm up, error, 501 and empty states)
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { indicatorsHandler, mocks, scanHandler, templatesHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";
import { renderWithQuery } from "@/test/render";

import { ScanWorkspace } from "./scan-workspace";

const WARMUP_TEXT = "Warming up the engine…";

describe("ScanWorkspace states", () => {
  it("shows the warm up notice when the scan is pending past 1.5 s", async () => {
    server.use(scanHandler("ok", { delayMs: "infinite" }));
    renderWithQuery(<ScanWorkspace />);
    await screen.findByLabelText("Template");
    expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument();
    expect(await screen.findByText(WARMUP_TEXT, {}, { timeout: 2500 })).toBeVisible();
  });

  it("offers Try again after a failed scan, and it runs the scan again", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/v1/scan", () => {
        calls += 1;
        return calls === 1 ? HttpResponse.error() : HttpResponse.json(mocks.scan);
      }),
    );
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByText("Can't reach the engine")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("shows Not built yet with no retry on a 501", async () => {
    server.use(scanHandler("501.scan"));
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByText("Not built yet")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("replaces the workspace with an error when the templates fail, and retries them", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/templates", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ detail: "boom" }, { status: 500 })
          : HttpResponse.json(mocks.templates);
      }),
    );
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByText("Something went wrong")).toBeInTheDocument();
    expect(screen.queryByLabelText("Template")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByLabelText("Template")).toHaveValue("breakout_52w");
    expect(calls).toBe(2);
  });

  it("says there are no hits and suggests the other template", async () => {
    server.use(scanHandler("empty"));
    const { container } = renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByText(`No hits on ${mocks.scanEmpty.as_of}`)).toBeInTheDocument();
    expect(screen.getByText("Try the other template.")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("keeps the skeleton while templates load", async () => {
    server.use(templatesHandler({ delayMs: "infinite" }));
    renderWithQuery(<ScanWorkspace />);
    await waitFor(() => expect(screen.getByText("Loading templates…")).toBeInTheDocument());
    expect(screen.getByRole("heading", { level: 1, name: "Template scan" })).toBeInTheDocument();
  });

  it("hides the warm up notice once a slow scan answers", async () => {
    server.use(scanHandler("ok", { delayMs: 1700 }));
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByText(WARMUP_TEXT, {}, { timeout: 2500 })).toBeVisible();
    expect(await screen.findByRole("table", {}, { timeout: 2500 })).toBeInTheDocument();
    expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument();
  });

  it("shows Something went wrong with Try again when the scan answers 500", async () => {
    server.use(http.post("*/api/v1/scan", () => HttpResponse.json({}, { status: 500 })));
    renderWithQuery(<ScanWorkspace />);
    expect(
      await screen.findByRole("heading", { level: 3, name: "Something went wrong" }),
    ).toBeInTheDocument();
    expect(screen.getByText("The API answered with status 500.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("replaces the workspace with an error when the indicator catalog fails, and retries it", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/indicators", () => {
        calls += 1;
        return calls === 1 ? HttpResponse.error() : HttpResponse.json(mocks.indicators);
      }),
    );
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    expect(await screen.findByText("Can't reach the engine")).toBeInTheDocument();
    expect(screen.queryByLabelText("Template")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByLabelText("Template")).toHaveValue("breakout_52w");
    expect(calls).toBe(2);
  });

  it("runs no scan while the indicator catalog is still loading", async () => {
    server.use(indicatorsHandler({ delayMs: "infinite" }));
    let scans = 0;
    server.use(
      http.post("*/api/v1/scan", () => {
        scans += 1;
        return HttpResponse.json(mocks.scan);
      }),
    );
    renderWithQuery(<ScanWorkspace />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.getByText("Loading templates…")).toBeInTheDocument();
    expect(scans).toBe(0);
  });

  it("still names the session date in the heading when there are no hits", async () => {
    server.use(scanHandler("empty"));
    renderWithQuery(<ScanWorkspace />);
    expect(
      await screen.findByRole("heading", { level: 2, name: `Hits on ${mocks.scanEmpty.as_of}` }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: /pages$/ })).not.toBeInTheDocument();
  });
});

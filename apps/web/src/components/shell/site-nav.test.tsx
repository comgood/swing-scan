import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SiteNav } from "./site-nav";

const nav = vi.hoisted(() => ({ pathname: "/" as string | null }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));

describe("SiteNav", () => {
  it("lists both pages and marks the one you are on", () => {
    nav.pathname = "/backtest";
    render(<SiteNav />);
    const links = screen.getAllByRole("link");
    expect(links.map((l) => [l.textContent, l.getAttribute("href")])).toEqual([
      ["Screener", "/"],
      ["Testing", "/backtest"],
    ]);
    expect(screen.getByRole("link", { name: "Testing" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Screener" })).not.toHaveAttribute("aria-current");
  });

  it("marks the screener on /", () => {
    nav.pathname = "/";
    render(<SiteNav />);
    expect(screen.getByRole("link", { name: "Screener" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Testing" })).not.toHaveAttribute("aria-current");
  });

  it("marks nothing on another page or with no router, and stays keyboard reachable", async () => {
    nav.pathname = null;
    const { container } = render(<SiteNav />);
    expect(container.querySelector("[aria-current]")).toBeNull();
    const user = userEvent.setup();
    await user.tab();
    expect(screen.getByRole("link", { name: "Screener" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Testing" })).toHaveFocus();
  });
});

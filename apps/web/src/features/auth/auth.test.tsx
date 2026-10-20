// covers: spec 0015 AC-3 (no account's rows survive into another's session), AC-4 (there is no
// sign in where accounts do not run), AC-12 (signed out says so rather than vanishing), and
// AC-2 (a rejected password is never shown back)
//
// The three answers `GET /auth/me` can give are what everything here turns on: 501 (not
// available), 401 (signed out) and 200 (signed in). Confusing any two is how a header ends up
// claiming you are signed in on a site that has no login, so each gets its own test.
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { loginHandler, meHandler, mocks, savedRulesHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";
import { renderWithQuery } from "@/test/render";

import { AccountStatus } from "./account-status";
import { AuthForm } from "./auth-form";
import { NOT_HERE_TITLE, SignInRoute } from "./auth-routes";

describe("the header's account state", () => {
  it("shows nothing at all where accounts do not run", async () => {
    server.use(meHandler("501.rules"));
    renderWithQuery(<AccountStatus />);
    // Nothing appears, and nothing ever will: waiting proves it is not merely slow.
    await waitFor(() => expect(screen.queryByText(/sign in/i)).not.toBeInTheDocument());
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("offers sign in when the surface is here and you are signed out", async () => {
    server.use(meHandler("signed_out"));
    renderWithQuery(<AccountStatus />);
    const link = await screen.findByRole("link", { name: /sign in/i });
    expect(link).toHaveAttribute("href", "/sign-in");
  });

  it("shows your email, and names whose account it is for a screen reader", async () => {
    server.use(meHandler("signed_in"));
    renderWithQuery(<AccountStatus />);
    const link = await screen.findByRole("link", { name: `Your account, ${mocks.account.email}` });
    expect(link).toHaveAttribute("href", "/account");
    expect(link).toHaveTextContent(mocks.account.email);
  });
});

describe("the sign in page", () => {
  it("explains itself instead of offering a password field that cannot work", async () => {
    server.use(meHandler("501.rules"));
    renderWithQuery(<SignInRoute />);
    expect(await screen.findByText(NOT_HERE_TITLE)).toBeInTheDocument();
    // The important half: no password input exists on the deployed demo (AC-4).
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  it("shows the one shared message when credentials are wrong, naming neither half", async () => {
    server.use(meHandler("signed_out"), loginHandler("wrong"));
    renderWithQuery(<SignInRoute />);
    await userEvent.type(await screen.findByLabelText(/email/i), "you@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "a long enough password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/do not match an account/i);
    // It must not say which of the two was wrong (AC-7).
    expect(alert).not.toHaveTextContent(/email .*not found|no such account|wrong password/i);
  });
});

describe("the form itself", () => {
  it("shows a 422 against its field, and never shows the password back", async () => {
    const rejected = "tooshort";
    renderWithQuery(
      <AuthForm
        mode="register"
        fieldErrors={{ fields: { password: "Value should have at least 12 items" }, form: [] }}
        onSubmit={() => undefined}
      />,
    );
    expect(screen.getByText(/at least 12 items/i)).toBeInTheDocument();
    // AC-2: the API strips the rejected value, so there is nothing here to render. This is the
    // browser side half of the check the API test makes on the 422 body.
    expect(screen.queryByText(new RegExp(rejected))).not.toBeInTheDocument();
  });

  it("is accessible in both modes", async () => {
    const { container } = renderWithQuery(
      <AuthForm mode="sign-in" message="That did not work" onSubmit={() => undefined} />,
    );
    await expectNoAxeViolations(container);
  });
});

describe("the saved rules panel, signed out", () => {
  it("says to sign in rather than disappearing", async () => {
    const { SavedRules } = await import("@/features/scan/saved-rules");
    server.use(savedRulesHandler("501.rules"));
    // 401 is not one of the named error mocks, so it is served directly: the panel has to tell
    // "you are signed out" from "this is not available here" (AC-12).
    const { http, HttpResponse } = await import("msw");
    server.use(
      http.get("*/api/v1/rules", () =>
        HttpResponse.json({ detail: "You are not signed in." }, { status: 401 }),
      ),
    );
    renderWithQuery(<SavedRules rule={mocks.templates[0]!.rule} onLoad={() => undefined} />);
    const link = await screen.findByRole("link", { name: /sign in/i });
    expect(link).toHaveAttribute("href", "/sign-in");
    expect(screen.getByRole("heading", { name: /saved rules/i })).toBeInTheDocument();
  });

  it("still disappears entirely where the surface does not exist", async () => {
    const { SavedRules } = await import("@/features/scan/saved-rules");
    server.use(savedRulesHandler("501.rules"));
    const { container } = renderWithQuery(
      <SavedRules rule={mocks.templates[0]!.rule} onLoad={() => undefined} />,
    );
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});

"use client";

// The connected sign in and register pages (spec 0015), and the "not available here" state
// they show on the deployed demo.
//
// Both pages ship in the static export, because there is only one build. What changes is what
// they say: where accounts do not run, they explain that rather than offering a password field
// that cannot work, which is the same honesty rule the rest of the app follows (feature 13).
import { Banner } from "@/components/banner";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, httpStatus } from "@/lib/api-error";

import { AuthForm } from "./auth-form";
import { goTo } from "./navigate";
import { CredentialsRejectedError, useLogin, useMe, useRegister } from "./queries";

export const NOT_HERE_TITLE = "There is no sign in here";
export const NOT_HERE_BODY =
  "Accounts run only on the machine this project is developed on, so the public demo has no " +
  "login and nothing to attack. Everything else on the site works without one: scan a rule, " +
  "run a backtest, compare exits.";

/** The 501 state, shared by both pages. */
export function AccountsNotHere() {
  return (
    <section aria-labelledby="auth-title" className="flex min-w-0 max-w-xl flex-col gap-4">
      <h1 id="auth-title" className="text-2xl font-semibold">
        Sign in
      </h1>
      <Banner variant="info" title={NOT_HERE_TITLE}>
        {NOT_HERE_BODY}
      </Banner>
    </section>
  );
}

/** A 501 from `me` means the whole surface is off; anything else is a real problem. */
function notAvailable(error: unknown): boolean {
  return httpStatus(error) === 501;
}

/** The message a failed attempt should show, when it is not a per field 422. */
function formMessage(error: Error | null): string | undefined {
  if (!error || error instanceof CredentialsRejectedError) return undefined;
  if (error instanceof ApiRequestError && error.apiError.kind === "http") {
    return error.apiError.detail ?? `The API answered with status ${error.apiError.status}.`;
  }
  return "Could not reach the engine. Check it is running and try again.";
}

function fieldErrorsOf(error: Error | null) {
  return error instanceof CredentialsRejectedError ? error.fieldErrors : undefined;
}

export function SignInRoute() {
  const me = useMe();
  const login = useLogin();

  if (me.isPending) return <Skeleton className="h-64 w-full max-w-xl" />;
  if (notAvailable(me.error)) return <AccountsNotHere />;

  return (
    <AuthForm
      mode="sign-in"
      pending={login.isPending}
      fieldErrors={fieldErrorsOf(login.error)}
      message={formMessage(login.error)}
      // Back to the screener once you are in: there is no server to hold a return path, so
      // there is no return path to honour (spec 0015).
      onSubmit={(credentials) => login.mutate(credentials, { onSuccess: () => goTo("/") })}
    />
  );
}

export function RegisterRoute() {
  const me = useMe();
  const register = useRegister();

  if (me.isPending) return <Skeleton className="h-64 w-full max-w-xl" />;
  if (notAvailable(me.error)) return <AccountsNotHere />;

  return (
    <AuthForm
      mode="register"
      pending={register.isPending}
      fieldErrors={fieldErrorsOf(register.error)}
      message={formMessage(register.error)}
      onSubmit={(credentials) => register.mutate(credentials, { onSuccess: () => goTo("/") })}
    />
  );
}

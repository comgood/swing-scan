"use client";

// The sign in and register surface (spec 0015). Presentational on purpose: it takes its state
// as props and owns no query, so the `/ui` gallery can mount it with no QueryClient. The
// connected versions are `SignInRoute` and `RegisterRoute`.
import Link from "next/link";
import { useState } from "react";

import { Banner } from "@/components/banner";
import { FormErrorSummary } from "@/components/form-error-summary";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import type { FieldErrors } from "@/lib/field-errors";

export const PASSWORD_MIN = 12;

/** Why an account exists at all, said once rather than assumed. Honesty copy, like the rest:
 * it tells you what signing in does and does not do before you type anything. */
export const PURPOSE =
  "An account is only for keeping the rules you save. Scanning, backtesting and the exit lab " +
  "all work without one, and nothing you do here is ever shared or sent anywhere.";

export const LOCAL_ONLY =
  "This runs on your own machine only. There is no sign in on the public demo, which is why " +
  "there is nothing out there to attack.";

export interface AuthFormProps {
  mode: "sign-in" | "register";
  /** Field level messages from a 422, keyed as `fieldErrorsFrom422` produces them. */
  fieldErrors?: FieldErrors;
  /** A whole form failure, such as the 409 on a taken email or the shared 401. */
  message?: string;
  pending?: boolean;
  onSubmit: (credentials: { email: string; password: string }) => void;
}

const COPY = {
  "sign-in": {
    title: "Sign in",
    lead: "Sign in to see the rules you have saved.",
    action: "Sign in",
    switchLead: "No account yet?",
    switchLabel: "Create one",
    switchHref: "/register",
  },
  register: {
    title: "Create an account",
    lead: "Pick an email and a password. Nothing is ever sent to the address.",
    action: "Create account",
    switchLead: "Already have an account?",
    switchLabel: "Sign in",
    switchHref: "/sign-in",
  },
} as const;

export function AuthForm({ mode, fieldErrors, message, pending = false, onSubmit }: AuthFormProps) {
  const copy = COPY[mode];
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const emailError = fieldErrors?.fields.email;
  const passwordError = fieldErrors?.fields.password;
  // A 409 or a 401 belongs to the whole form, not to one field: on sign in the API deliberately
  // will not say which half was wrong, so pinning it to a field would invent information.
  const formErrors = [...(message ? [message] : []), ...(fieldErrors?.form ?? [])];

  return (
    <section aria-labelledby="auth-title" className="flex min-w-0 max-w-xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 id="auth-title" className="text-2xl font-semibold">
          {copy.title}
        </h1>
        <p className="text-sm text-muted-foreground">{copy.lead}</p>
      </div>

      <Banner variant="info" title="What an account is for">
        {PURPOSE}
      </Banner>

      <form
        noValidate
        className="flex min-w-0 flex-col gap-5"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit({ email, password });
        }}
      >
        <FormErrorSummary errors={formErrors} title="That did not work" />

        <Field invalid={Boolean(emailError)}>
          <FieldLabel>Email</FieldLabel>
          <Input
            type="email"
            name="email"
            autoComplete="email"
            value={email}
            maxLength={254}
            onChange={(event) => setEmail(event.target.value)}
          />
          <FieldError>{emailError}</FieldError>
        </Field>

        <Field invalid={Boolean(passwordError)}>
          <FieldLabel>Password</FieldLabel>
          <Input
            type="password"
            name="password"
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            value={password}
            maxLength={128}
            onChange={(event) => setPassword(event.target.value)}
          />
          <FieldDescription>
            At least {PASSWORD_MIN} characters. Length is all that matters, so a few plain words
            beat one short word with symbols in it.
          </FieldDescription>
          <FieldError>{passwordError}</FieldError>
        </Field>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={pending}>
            {pending && <Spinner />}
            {copy.action}
          </Button>
          <p className="text-sm text-muted-foreground">
            {copy.switchLead}{" "}
            <Link href={copy.switchHref} className="text-primary underline underline-offset-4">
              {copy.switchLabel}
            </Link>
          </p>
        </div>
      </form>

      <p className="text-xs text-muted-foreground">{LOCAL_ONLY}</p>
    </section>
  );
}

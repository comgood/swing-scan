"use client";

// Accounts (spec 0015): who you are, and the four things you can do about it.
//
// `me` is the single source of truth for "am I signed in". Nothing keeps a second copy, so
// there is no state to go stale and no flash of the wrong header.
//
// Every transition clears the whole query cache. That is not tidiness: without it, signing out
// and in as another account leaves the first account's rules in the cache, and AC-3 says one
// account never sees another's rows. A `where` clause in Postgres cannot protect against a
// stale copy that is already in the browser.
import type { Account } from "@swing-scan/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { ApiRequestError, toApiError, type ApiError } from "@/lib/api-error";
import { fieldErrorsFrom422, type FieldErrors } from "@/lib/field-errors";

/** Credentials the API rejected with 422, so the form can show which field was wrong. */
export class CredentialsRejectedError extends ApiRequestError {
  constructor(
    apiError: ApiError,
    readonly fieldErrors: FieldErrors,
  ) {
    super(apiError);
    this.name = "CredentialsRejectedError";
  }
}

export const ME_KEY = ["auth", "me"] as const;

export interface Credentials {
  email: string;
  password: string;
}

/** Signed out (401), or not available here (501): both mean "no account", and the caller
 * tells them apart by `status`, because locally they mean very different things. */
export class NoAccountError extends ApiRequestError {}

async function fetchMe({ signal }: { signal: AbortSignal }): Promise<Account | null> {
  let result;
  try {
    result = await api.GET("/api/v1/auth/me", { signal });
  } catch (error) {
    throw new ApiRequestError(toApiError(error));
  }
  // 401 is the ordinary signed out answer, not a failure: `null` rather than a thrown error,
  // so the header renders a sign in link instead of an error banner.
  if (result.response.status === 401) return null;
  if (!result.data) throw new NoAccountError(toApiError(result));
  return result.data;
}

/**
 * Who you are, or `null` when you are signed out.
 *
 * A 501 throws, because "accounts do not run here" is a different thing from "you are not
 * signed in" and the pages render differently for each. `retry: false` so a signed out page
 * does not hammer the API.
 */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: fetchMe,
    retry: false,
    staleTime: 30_000,
  });
}

interface PostResult {
  data?: Account;
  error?: unknown;
  response: Response;
}

/**
 * The shared half: turn one credential post into an `Account` or the right error.
 *
 * The two calls are written out separately below rather than sharing a `path` parameter,
 * because openapi-fetch resolves its body and response types from a literal path: a union of
 * two paths collapses the generic to `never` and the body stops being typed at all.
 */
function accountOrThrow(result: PostResult): Account {
  if (result.response.status === 422) {
    throw new CredentialsRejectedError(toApiError(result), fieldErrorsFrom422(result.error));
  }
  if (!result.data) throw new ApiRequestError(toApiError(result));
  return result.data;
}

async function postRegister(body: Credentials): Promise<Account> {
  try {
    return accountOrThrow(await api.POST("/api/v1/auth/register", { body }));
  } catch (error) {
    if (error instanceof ApiRequestError) throw error;
    throw new ApiRequestError(toApiError(error));
  }
}

async function postLogin(body: Credentials): Promise<Account> {
  try {
    return accountOrThrow(await api.POST("/api/v1/auth/login", { body }));
  } catch (error) {
    if (error instanceof ApiRequestError) throw error;
    throw new ApiRequestError(toApiError(error));
  }
}

/** Clearing everything, not just `me`: another account's rules must not survive a switch. */
function useClearOnChange() {
  const queryClient = useQueryClient();
  return async (account: Account | null) => {
    queryClient.clear();
    if (account) queryClient.setQueryData(ME_KEY, account);
  };
}

export function useRegister() {
  const reset = useClearOnChange();
  return useMutation({
    mutationFn: postRegister,
    onSuccess: reset,
  });
}

export function useLogin() {
  const reset = useClearOnChange();
  return useMutation({
    mutationFn: postLogin,
    onSuccess: reset,
  });
}

export function useLogout() {
  const reset = useClearOnChange();
  return useMutation({
    mutationFn: async () => {
      // Deliberately ignores the status: the cookie is cleared server side either way, and a
      // browser that cannot reach the API should still end up looking signed out.
      await api.POST("/api/v1/auth/logout", {}).catch(() => undefined);
    },
    onSuccess: () => reset(null),
  });
}

export function useDeleteAccount() {
  const reset = useClearOnChange();
  return useMutation({
    mutationFn: async () => {
      const result = await api.DELETE("/api/v1/auth/account", {});
      if (result.response.status !== 204) throw new ApiRequestError(toApiError(result));
    },
    onSuccess: () => reset(null),
  });
}

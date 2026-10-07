// Turns an openapi-fetch result or a thrown fetch error into one ApiError (spec 0003 AC-10).

export type ApiError =
  { kind: "network" } | { kind: "timeout" } | { kind: "http"; status: number; detail?: string };

interface FetchResultLike {
  error?: unknown;
  response: Response;
}

function isFetchResult(value: unknown): value is FetchResultLike {
  return typeof value === "object" && value !== null && "response" in value;
}

/** Abort and timeout errors are DOMExceptions, which are not always `Error` instances. */
function isTimeout(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  const { name } = value as { name?: unknown };
  return name === "TimeoutError" || name === "AbortError";
}

export function toApiError(result: unknown): ApiError {
  if (isFetchResult(result)) {
    const { status } = result.response;
    if (status === 504) return { kind: "timeout" };
    const body = result.error;
    const detail =
      typeof body === "object" && body !== null ? (body as { detail?: unknown }).detail : undefined;
    return typeof detail === "string" ? { kind: "http", status, detail } : { kind: "http", status };
  }
  if (isTimeout(result)) return { kind: "timeout" };
  return { kind: "network" };
}

/** Thrown by query functions so TanStack Query carries the ApiError to the page. */
export class ApiRequestError extends Error {
  constructor(readonly apiError: ApiError) {
    super(apiError.kind === "http" ? `HTTP ${apiError.status}` : apiError.kind);
    this.name = "ApiRequestError";
  }
}

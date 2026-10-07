// The one API client for the web app (spec 0001, spec 0002). Fetch is looked up per call, so
// MSW, which patches the global fetch after this module loads, still answers in tests.
import { createClient } from "@swing-scan/api-client";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const api = createClient({
  baseUrl: API_URL,
  fetch: (request) => globalThis.fetch(request),
});

// The one API client for the web app (spec 0001, spec 0002). Fetch is looked up per call, so
// MSW, which patches the global fetch after this module loads, still answers in tests.
import { createClient } from "@swing-scan/api-client";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const api = createClient({
  baseUrl: API_URL,
  fetch: (request) => globalThis.fetch(request),
  // The session cookie (spec 0015). Without this the browser never attaches it and every
  // signed in request looks signed out, with no error anywhere to explain why.
  //
  // The API is a different origin, so this also needs `allow_credentials` on the server. And
  // because the cookie is `SameSite=Lax` and a browser compares hostnames while ignoring
  // ports, signing in works only when the page and the API share a hostname: open the app at
  // `http://127.0.0.1:3000`, not `localhost:3000`.
  credentials: "include",
});

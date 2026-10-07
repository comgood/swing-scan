// MSW is on by default in Vitest; an unmocked request fails the test.
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./node";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

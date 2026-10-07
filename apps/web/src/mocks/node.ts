// MSW for Vitest (Node). On by default through vitest.setup.ts.
import { setupServer } from "msw/node";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);

// MSW in the browser, started by MockProvider when NEXT_PUBLIC_API_MOCK=1.
import { setupWorker } from "msw/browser";

import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);

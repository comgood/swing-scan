// Ships MSW's service worker only when mocks are on (spec 0002): copies it into public/
// when NEXT_PUBLIC_API_MOCK=1 and removes it otherwise, so a production export never has it.
import { copyFileSync, rmSync } from "node:fs";
import { createRequire } from "node:module";

const target = new URL("../public/mockServiceWorker.js", import.meta.url);

if (process.env.NEXT_PUBLIC_API_MOCK === "1") {
  const require = createRequire(import.meta.url);
  copyFileSync(require.resolve("msw/mockServiceWorker.js"), target);
  console.log("API mocks on: copied mockServiceWorker.js into public/");
} else {
  rmSync(target, { force: true });
}

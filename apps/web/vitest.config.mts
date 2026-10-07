import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    // jsdom for component tests (spec 0003); MSW's node server still patches fetch.
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}", "tests/acceptance/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/mocks/vitest.setup.ts", "./src/test/setup.ts"],
  },
});

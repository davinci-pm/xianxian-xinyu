import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    environmentOptions: { jsdom: { url: "http://127.0.0.1" } },
    include: ["tests/unit/**/*.test.{ts,tsx}"],
  },
});

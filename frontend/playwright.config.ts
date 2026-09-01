import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "APP_ENV=test AUTH_REQUIRED=false INVITE_CODES=E2E-SOUL-V3-001 DATABASE_URL=sqlite+pysqlite:////tmp/first-sage-e2e.db LLM_PROVIDER=mock WEB_SEARCH_ENABLED=false RATE_LIMIT_ENABLED=false FRONTEND_ORIGIN=http://127.0.0.1:3100 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8876",
      cwd: "../backend",
      url: "http://127.0.0.1:8876/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "BACKEND_URL=http://127.0.0.1:8876 npm run build && cp -R .next/static .next/standalone/.next/static && cp -R public .next/standalone/public && BACKEND_URL=http://127.0.0.1:8876 HOSTNAME=127.0.0.1 PORT=3100 node .next/standalone/server.js",
      cwd: ".",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});

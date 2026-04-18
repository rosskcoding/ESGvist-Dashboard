import { defineConfig } from "@playwright/test";

const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT || "3015";
const apiPort = process.env.PLAYWRIGHT_API_PORT || "8015";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://localhost:${frontendPort}`;
const databaseUrl =
  process.env.DATABASE_URL || "sqlite+aiosqlite:///./playwright_framework_catalog.db";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["framework-catalog.spec.ts"],
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  outputDir: "../artifacts/screens/framework-catalog/test-results",
  reporter: [
    ["list"],
    [
      "html",
      { outputFolder: "../artifacts/screens/framework-catalog/playwright-report", open: "never" },
    ],
  ],
  use: {
    baseURL,
    browserName: "chromium",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "bash scripts/start_playwright_guided_backend.sh",
      cwd: "../backend",
      url: `http://127.0.0.1:${apiPort}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        PORT: apiPort,
        DATABASE_URL: databaseUrl,
        DEMO_BASE_URL: baseURL,
        DEMO_API_URL: `http://localhost:${apiPort}/api`,
        CORS_ORIGINS: process.env.CORS_ORIGINS || JSON.stringify([baseURL]),
      },
    },
    {
      command: "bash scripts/start_playwright_guided_frontend.sh",
      cwd: ".",
      url: `${baseURL}/login`,
      reuseExistingServer: false,
      timeout: 240_000,
      env: {
        ...process.env,
        PORT: frontendPort,
        API_PORT: apiPort,
      },
    },
  ],
});

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "login-screen.spec.ts",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  outputDir: "../artifacts/screens/login/test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/screens/login/playwright-report", open: "never" }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3002",
    browserName: "chromium",
    channel: "chrome",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});

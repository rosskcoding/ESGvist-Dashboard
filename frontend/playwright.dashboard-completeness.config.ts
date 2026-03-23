import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["dashboard-screen.spec.ts", "completeness-screen.spec.ts"],
  timeout: 90_000,
  fullyParallel: false,
  workers: 1,
  outputDir: "../artifacts/screens/dashboard-completeness/test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/screens/dashboard-completeness/playwright-report", open: "never" }],
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

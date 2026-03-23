import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["role-journeys-phase2.spec.ts"],
  timeout: 180_000,
  fullyParallel: false,
  workers: 1,
  outputDir: "../artifacts/screens/phase-2-role-journeys/test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/screens/phase-2-role-journeys/playwright-report", open: "never" }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3002",
    browserName: "chromium",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});

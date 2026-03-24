import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["edge-cases-phase3.spec.ts"],
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  outputDir: "../artifacts/screens/phase-3-edge-cases/test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/screens/phase-3-edge-cases/playwright-report", open: "never" }],
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

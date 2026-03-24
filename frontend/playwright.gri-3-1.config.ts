import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["gri-3-1-manual-import.spec.ts"],
  timeout: 360_000,
  fullyParallel: false,
  workers: 1,
  outputDir: "../artifacts/screens/gri-3-1-manual-import/test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/screens/gri-3-1-manual-import/playwright-report", open: "never" }],
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

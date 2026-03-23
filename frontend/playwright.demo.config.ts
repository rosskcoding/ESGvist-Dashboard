import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "demo-scenarios.spec.ts",
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  outputDir: "../artifacts/demo/test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/demo/playwright-report", open: "never" }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3002",
    browserName: "webkit",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});

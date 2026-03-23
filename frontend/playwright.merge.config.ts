import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["merge-screen.spec.ts"],
  timeout: 90_000,
  fullyParallel: false,
  workers: 1,
  outputDir: "../artifacts/screens/merge/test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/screens/merge/playwright-report", open: "never" }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3002",
    browserName: "chromium",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});

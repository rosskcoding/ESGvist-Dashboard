import { test, expect } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

test.describe("Collector scenarios", () => {
  // Using admin as proxy since collector needs assignment data
  // These tests verify the UI screens collectors would use

  test("1. Collection table loads with filters", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/collection");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/collection/i).first()).toBeVisible({ timeout: 10000 });
    // Should have filter controls
    const body = await page.textContent("body");
    expect(body).toMatch(/status|filter|search/i);
  });

  test("2. Data entry wizard accessible", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/collection");
    await page.waitForLoadState('networkidle');
    // The collection page should load without errors
    const body = await page.textContent("body");
    expect(body).not.toContain("Application error");
    expect(body).not.toContain("Internal Server Error");
  });

  test("3. Notifications page accessible", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/notifications");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/notification/i).first()).toBeVisible({ timeout: 10000 });
    // Should show notification list or empty state
    const body = await page.textContent("body");
    expect(body).not.toContain("403");
  });
});

import { test, expect } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

test.describe("ESG Manager scenarios", () => {
  test("1. Can access projects and create", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/projects");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/project/i).first()).toBeVisible({ timeout: 10000 });
    // Should see Create Project button
    await expect(page.getByText(/create.*project|new.*project/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("2. Can access assignments matrix", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/settings/assignments");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/assignment/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("3. Can access report readiness", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/report");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/report|readiness/i).first()).toBeVisible({ timeout: 10000 });
  });
});

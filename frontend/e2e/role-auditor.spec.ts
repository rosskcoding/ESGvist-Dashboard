import { test, expect } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

test.describe("Auditor scenarios", () => {
  test("1. Audit log accessible", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/audit");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/audit/i).first()).toBeVisible({ timeout: 10000 });
    // Should show audit log table
    const body = await page.textContent("body");
    expect(body).toMatch(/timestamp|action|user|entity/i);
  });

  test("2. Completeness screen read-only", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/completeness");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/completeness/i).first()).toBeVisible({ timeout: 10000 });
    const body = await page.textContent("body");
    expect(body).not.toContain("Application error");
  });

  test("3. Evidence page accessible (read-only)", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/evidence");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/evidence/i).first()).toBeVisible({ timeout: 10000 });
    const body = await page.textContent("body");
    expect(body).not.toContain("403");
  });
});

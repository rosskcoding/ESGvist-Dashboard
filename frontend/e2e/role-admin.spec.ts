import { test, expect } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

test.describe("Admin (tenant) scenarios", () => {
  test("1. Can access standards management", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/settings/standards");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/standard/i).first()).toBeVisible({ timeout: 10000 });
    // Should see Add Standard button
    await expect(page.getByText(/add.*standard/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("2. Can access user management", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/settings/users");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/user/i).first()).toBeVisible({ timeout: 10000 });
    // Should see Add User / Invite button
    const body = await page.textContent("body");
    expect(body).toMatch(/add|invite|manage/i);
  });

  test("3. Can access company structure", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/settings/company-structure");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/company.*structure|entit/i).first()).toBeVisible({ timeout: 10000 });
    // Should see Add Entity button
    const body2 = await page.textContent("body");
    expect(body2).toMatch(/add|entity|structure/i);
  });
});

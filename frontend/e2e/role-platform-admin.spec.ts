import { test, expect } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

test.describe("Platform Admin scenarios", () => {
  test("1. Can view tenant list", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/platform/tenants");
    await page.waitForLoadState('networkidle');
    // Platform admin should see the page without 403
    const body = await page.textContent("body");
    expect(body).not.toContain("403");
    expect(body).not.toContain("Forbidden");
    expect(body).toMatch(/tenant|organization|create/i);
  });

  test("2. Can navigate to create tenant wizard", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/platform/tenants/new");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/create|new.*organization|tenant/i).first()).toBeVisible({ timeout: 10000 });
    // Should see step 1 of wizard
    await expect(page.getByText(/name|organization/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("3. Sidebar shows Platform section", async ({ page }) => {
    await loginAsAdmin(page);
    await page.waitForLoadState('networkidle');
    // Platform admin sees the Platform nav group
    await expect(page.getByText("Tenants").first()).toBeVisible({ timeout: 10000 });
  });
});

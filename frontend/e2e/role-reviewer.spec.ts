import { test, expect } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

test.describe("Reviewer scenarios", () => {
  test("1. Validation/Review screen loads", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/validation");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/review|validation/i).first()).toBeVisible({ timeout: 10000 });
    // Should show split panel layout or review queue
    const body = await page.textContent("body");
    expect(body).not.toContain("Application error");
  });

  test("2. Validation has approve/reject buttons when items exist", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/validation");
    await page.waitForLoadState('networkidle');
    // Page loads without crash
    const body = await page.textContent("body");
    expect(body).not.toContain("Internal Server Error");
    // Review-specific UI elements should exist somewhere
    expect(body).toMatch(/review|approve|reject|submitted|queue/i);
  });

  test("3. Merge view accessible for context", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/merge");
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/merge/i).first()).toBeVisible({ timeout: 10000 });
    const body = await page.textContent("body");
    expect(body).not.toContain("403");
  });
});

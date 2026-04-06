import { test, expect } from "@playwright/test";

// Helper to login before each test
async function loginAsAdmin(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@esgvist.com");
  await page.getByLabel("Password").fill("Admin12345");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 10000 });
}

test.describe("Dashboard", () => {
  test("shows sidebar navigation", async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page.getByText("ESGvist").first()).toBeVisible();
    await expect(page.getByText("Dashboard").first()).toBeVisible();
    await expect(page.getByText("Collection").first()).toBeVisible();
    await expect(page.getByText("Validation").first()).toBeVisible();
    await expect(page.getByText("Coverage Matrix").first()).toBeVisible();
    await expect(page.getByText("Projects").first()).toBeVisible();
  });

  test("shows dashboard cards", async ({ page }) => {
    await loginAsAdmin(page);
    // Dashboard loads without crash
    await page.waitForTimeout(2000);
    const body = await page.textContent("body");
    expect(body).not.toContain("Application error");
    expect(body).toMatch(/completion|data.*point|dashboard/i);
  });

  test("navigate to projects page", async ({ page }) => {
    await loginAsAdmin(page);
    await page.getByText("Projects").first().click();
    await expect(page).toHaveURL(/projects/, { timeout: 5000 });
  });

  test("navigate to collection page", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/collection");
    await expect(page).toHaveURL(/collection/, { timeout: 15000 });
  });
});

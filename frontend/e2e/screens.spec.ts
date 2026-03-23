import { test, expect } from "@playwright/test";

async function loginAsAdmin(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@esgvist.com");
  await page.getByLabel("Password").fill("Admin12345");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 10000 });
}

const screens = [
  { path: "/collection", title: /collection/i },
  { path: "/validation", title: /review|validation/i },
  { path: "/merge", title: /merge/i },
  { path: "/projects", title: /project/i },
  { path: "/completeness", title: /completeness/i },
  { path: "/evidence", title: /evidence/i },
  { path: "/report", title: /report|readiness/i },
  { path: "/audit", title: /audit/i },
  { path: "/notifications", title: /notification/i },
  { path: "/settings", title: /organization|settings/i },
  { path: "/settings/standards", title: /standard/i },
  { path: "/settings/shared-elements", title: /shared.*element|mapping/i },
  { path: "/settings/boundaries", title: /boundar/i },
  { path: "/settings/users", title: /user/i },
  { path: "/settings/company-structure", title: /company.*structure|entity/i },
  { path: "/settings/assignments", title: /assignment/i },
  { path: "/settings/profile", title: /profile/i },
  { path: "/settings/webhooks", title: /webhook/i },
  { path: "/platform/tenants", title: /tenant|organization/i },
];

test.describe("All screens load without error", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  for (const screen of screens) {
    test(`${screen.path} loads`, async ({ page }) => {
      await page.goto(screen.path);
      await page.waitForLoadState('networkidle');
      // Should not show a crash / error page
      const body = await page.textContent("body");
      expect(body).not.toContain("Application error");
      expect(body).not.toContain("Internal Server Error");
      // Page should have some content matching the expected pattern
      await expect(page.getByText(screen.title).first()).toBeVisible({ timeout: 10000 });
    });
  }
});

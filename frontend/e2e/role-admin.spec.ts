import { expect, test } from "@playwright/test";

import { createTenantAdminUser, loginThroughUi } from "./screen-helpers";

test.describe("Admin (tenant) scenarios", () => {
  test("cannot access standards management", async ({ page, request }) => {
    const tenantAdmin = await createTenantAdminUser(request, `role-admin-standards-${Date.now()}`);

    await loginThroughUi(page, tenantAdmin.email, tenantAdmin.password, /\/dashboard$/);
    await page.goto("/settings/standards");

    await expect(page.getByRole("heading", { name: "Standards Management" })).toBeVisible();
    await expect(page.getByText("Access denied")).toBeVisible();
    await expect(
      page.getByText("Only framework admin and platform admin roles can manage standards."),
    ).toBeVisible();
  });

  test("can access user management", async ({ page, request }) => {
    const tenantAdmin = await createTenantAdminUser(request, `role-admin-users-${Date.now()}`);

    await loginThroughUi(page, tenantAdmin.email, tenantAdmin.password, /\/dashboard$/);
    await page.goto("/settings/users");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/user/i).first()).toBeVisible({ timeout: 10_000 });
    const body = await page.textContent("body");
    expect(body).toMatch(/add|invite|manage/i);
  });

  test("can access company structure", async ({ page, request }) => {
    const tenantAdmin = await createTenantAdminUser(
      request,
      `role-admin-company-structure-${Date.now()}`,
    );

    await loginThroughUi(page, tenantAdmin.email, tenantAdmin.password, /\/dashboard$/);
    await page.goto("/settings/company-structure");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/company.*structure|entit/i).first()).toBeVisible({
      timeout: 10_000,
    });
    const body = await page.textContent("body");
    expect(body).toMatch(/add|entity|structure/i);
  });
});

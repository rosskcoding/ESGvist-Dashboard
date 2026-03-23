import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();
const seededUsers = [
  { email: demoState.users.admin.email, role: "platform_admin" },
  { email: demoState.users.esg_manager.email, role: "esg_manager" },
  { email: demoState.users.collector_energy.email, role: "collector" },
  { email: demoState.users.collector_climate.email, role: "collector" },
  { email: demoState.users.reviewer.email, role: "reviewer" },
  { email: demoState.users.auditor.email, role: "auditor" },
];

test.describe("Screen 1 - Login", () => {
  test("renders login form and seeded personas", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByText("ESGvist").first()).toBeVisible();
    await expect(page.getByText("ESG data management platform")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
    await expect(page.getByText("Dev accounts (password: Test1234)")).toBeVisible();

    for (const user of seededUsers) {
      await expect(page.getByText(user.email)).toBeVisible();
      await expect(page.getByText(user.role).first()).toBeVisible();
    }
  });

  test("shows backend validation message for invalid credentials", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
    await page.getByLabel("Email").fill("wrong@example.com");
    await page.getByLabel("Password").fill("wrong-password");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/login/);
    await expect(page.getByText("Invalid email or password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  for (const user of seededUsers) {
    test(`logs in successfully as ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByText("Dashboard").first()).toBeVisible();

      const storage = await page.evaluate(() => ({
        accessToken: localStorage.getItem("access_token"),
        refreshToken: localStorage.getItem("refresh_token"),
        organizationId: localStorage.getItem("organization_id"),
      }));

      expect(storage.accessToken).toBeTruthy();
      expect(storage.refreshToken).toBeTruthy();
      expect(storage.organizationId).toBeTruthy();
    });
  }

  test("navigates to registration screen from footer link", async ({ page }) => {
    await page.goto("/login");

    await page.getByRole("link", { name: "Create one" }).click();
    await expect(page).toHaveURL(/register/, { timeout: 10_000 });
  });
});

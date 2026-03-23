import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const allowedUsers = [demoState.users.admin, demoState.users.esg_manager];
const deniedUsers = [
  demoState.users.collector_energy,
  demoState.users.collector_climate,
  demoState.users.reviewer,
  demoState.users.auditor,
];

test.describe("Screen 8 - Company Structure", () => {
  for (const user of allowedUsers) {
    test(`renders company structure for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/settings/company-structure");

      await expect(page.getByRole("heading", { name: "Company Structure" })).toBeVisible();
      await expect(
        page.getByText("Manage your corporate entity hierarchy, ownership, and control relationships")
      ).toBeVisible();
      await expect(page.getByRole("button", { name: "Add Entity" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Structure" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Control" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Boundary", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: /Northwind Renewables Group/ })).toBeVisible();
    });
  }

  test("creates a new entity as platform_admin", async ({ page }) => {
    const nonce = Date.now();
    const entityName = `Screen Entity ${nonce}`;
    const entityCode = `SCR-ENT-${nonce}`;

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings/company-structure");

    await page.getByRole("button", { name: "Add Entity" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Name").fill(entityName);
    await dialog.getByLabel("Code").fill(entityCode);
    await dialog.getByLabel("Type").selectOption("facility");
    await dialog.getByLabel("Country").fill("GB");
    await dialog.getByLabel("Jurisdiction").fill("England");
    await dialog.getByRole("button", { name: "Create Entity" }).click();

    await expect(page.getByText(entityName, { exact: true })).toBeVisible();
  });

  for (const user of deniedUsers) {
    test(`hides company structure nav and blocks direct access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Company Structure" })).toHaveCount(0);
      await page.goto("/settings/company-structure");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only admin and ESG manager roles can manage company structure.")
      ).toBeVisible();
    });
  }
});

import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const deniedUsers = [
  demoState.users.esg_manager,
  demoState.users.collector_energy,
  demoState.users.collector_climate,
  demoState.users.reviewer,
  demoState.users.auditor,
];

test.describe("Screen 9 - Boundary Definitions", () => {
  test("renders boundaries page for platform_admin", async ({ page }) => {
    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings/boundaries");

    await expect(page.getByRole("heading", { name: "Boundaries" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Boundary" })).toBeVisible();
    await expect(page.getByText("FY2025 Sustainability Boundary")).toBeVisible();

    await page.getByRole("row", { name: /FY2025 Sustainability Boundary/i }).click();
    await expect(page.getByText("Entity Membership")).toBeVisible();
    await expect(page.getByText("Snapshot History")).toBeVisible();
  });

  test("creates a new boundary as platform_admin", async ({ page }) => {
    const nonce = Date.now();
    const boundaryName = `Screen Boundary ${nonce}`;

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings/boundaries");

    await page.getByRole("button", { name: "Add Boundary" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Name").fill(boundaryName);
    await dialog.getByLabel("Type").selectOption("custom");
    await dialog.getByLabel("Description").fill("Boundary created by screen pack");
    await dialog.getByRole("button", { name: "Create Boundary" }).click();

    await expect(page.getByText(boundaryName, { exact: true })).toBeVisible();
  });

  for (const user of deniedUsers) {
    test(`hides boundaries nav and blocks direct access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Boundaries" })).toHaveCount(0);
      await page.goto("/settings/boundaries");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(page.getByText("Only admin roles can manage boundaries.")).toBeVisible();
    });
  }
});

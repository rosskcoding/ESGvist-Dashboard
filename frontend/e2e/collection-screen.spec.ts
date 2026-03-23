import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const allowedUsers = [
  demoState.users.admin,
  demoState.users.esg_manager,
  demoState.users.collector_energy,
  demoState.users.collector_climate,
];
const deniedUsers = [demoState.users.reviewer, demoState.users.auditor];

test.describe("Screen 13 - Collection Table", () => {
  for (const user of allowedUsers) {
    test(`renders collection table for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/collection");

      await expect(page.getByRole("heading", { name: "Data Collection" })).toBeVisible();
      await expect(
        page.getByText("Manage and enter ESG data points for the current reporting period.")
      ).toBeVisible();
      await expect(page.getByPlaceholder("Search by code or name...")).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Element Code" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Boundary" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Enter Data" }).first()).toBeVisible();
    });
  }

  test("filters the collection table for ESG manager", async ({ page }) => {
    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto("/collection");

    await page.getByPlaceholder("Search by code or name...").fill("SCOPE1");
    await expect(page.getByText("SCOPE1_TCO2E")).toBeVisible();
    await expect(page.getByText("ENERGY_TOTAL_MWH")).toHaveCount(0);
  });

  test("collector sees only their own seeded collection entries", async ({ page }) => {
    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto("/collection");

    await expect(page.getByRole("cell", { name: "ENERGY_TOTAL_MWH" }).first()).toBeVisible();
    await expect(page.getByText("SCOPE1_TCO2E")).toHaveCount(0);
  });

  for (const user of deniedUsers) {
    test(`hides collection nav and blocks direct access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Collection" })).toHaveCount(0);
      await page.goto("/collection");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only collectors and ESG managers can access data collection.")
      ).toBeVisible();
    });
  }
});

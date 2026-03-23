import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const allowedUsers = [
  demoState.users.admin,
  demoState.users.esg_manager,
  demoState.users.auditor,
];

const deniedUsers = [
  demoState.users.collector_energy,
  demoState.users.collector_climate,
  demoState.users.reviewer,
];

test.describe("Screen 7 - Completeness", () => {
  for (const user of allowedUsers) {
    test(`renders completeness screen for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/completeness");

      await expect(page.getByRole("heading", { name: "Completeness" })).toBeVisible();
      await expect(page.getByText("Overall Completeness")).toBeVisible();
      await expect(page.getByText("Completion by Standard")).toBeVisible();
      await expect(page.getByText("Disclosure Details")).toBeVisible();
      await expect(page.getByText("FY2025 Sustainability Boundary")).toBeVisible();
    });
  }

  for (const user of deniedUsers) {
    test(`hides completeness nav and blocks direct access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Completeness" })).toHaveCount(0);

      await page.goto("/completeness");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only admin, ESG manager, and auditor roles can view completeness.")
      ).toBeVisible();
    });
  }
});

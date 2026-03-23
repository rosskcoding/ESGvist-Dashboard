import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const dashboardUsers = [
  demoState.users.admin,
  demoState.users.esg_manager,
  demoState.users.collector_energy,
  demoState.users.collector_climate,
  demoState.users.reviewer,
  demoState.users.auditor,
];

test.describe("Screen 6 - Overview Dashboard", () => {
  for (const user of dashboardUsers) {
    test(`loads dashboard for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
      await expect(page.getByText("Overall Completion")).toBeVisible();
      await expect(page.getByText("Overdue Assignments")).toBeVisible();
      await expect(page.getByText("Completion by Standard")).toBeVisible();
      await expect(page.getByText("Boundary Summary")).toBeVisible();
      await expect(page.getByText("Priority Tasks", { exact: true })).toBeVisible();
      await expect(page.getByText("FY2025 Sustainability Boundary")).toBeVisible();
    });
  }
});

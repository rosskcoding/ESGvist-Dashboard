import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const allowedAssignmentsUsers = [demoState.users.admin, demoState.users.esg_manager];
const deniedAssignmentsUsers = [
  demoState.users.collector_energy,
  demoState.users.collector_climate,
  demoState.users.reviewer,
  demoState.users.auditor,
];

test.describe("Screen 19 - Assignments Matrix", () => {
  for (const user of allowedAssignmentsUsers) {
    test(`renders assignments matrix for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/settings/assignments");

      await expect(page.getByRole("heading", { name: "Assignments Matrix" })).toBeVisible();
      await expect(page.getByText("Manage data collection assignments, collectors, and reviewers")).toBeVisible();
      await expect(page.getByText("Total assignments:", { exact: true })).toBeVisible();
      await expect(page.getByText("Overdue:", { exact: true })).toBeVisible();
      await expect(page.getByText("Completed:", { exact: true })).toBeVisible();
      await expect(page.getByText("Unassigned:", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Add Assignment" })).toBeVisible();
    });
  }

  test("creates a new assignment as platform_admin", async ({ page }) => {
    const nonce = Date.now();
    const code = `SCREEN_ASSIGN_${nonce}`;
    const name = `Screen Assignment ${nonce}`;

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings/assignments");

    await page.getByRole("button", { name: "Add Assignment" }).click();
    await page.getByLabel("Element Code").fill(code);
    await page.getByLabel("Element Name").fill(name);
    await page.getByLabel("Entity").selectOption(String(demoState.entities.root.id));
    await page.getByLabel("Collector").selectOption(String(demoState.users.collector_energy.id));
    await page.getByLabel("Reviewer").selectOption(String(demoState.users.reviewer.id));
    await page.getByLabel("Deadline").fill("2026-12-31");
    await page.getByRole("button", { name: "Create Assignment" }).click();

    await expect(page.getByText(code, { exact: true })).toBeVisible();
    const assignmentRow = page.getByRole("row", { name: new RegExp(`${code}.*${demoState.entities.root.name}`) });
    await expect(assignmentRow).toBeVisible();
    await expect(assignmentRow.getByText(demoState.entities.root.name, { exact: true })).toBeVisible();
    await expect(assignmentRow.getByText(demoState.users.collector_energy.full_name, { exact: true })).toBeVisible();
    await expect(assignmentRow.getByText(demoState.users.reviewer.full_name, { exact: true })).toBeVisible();
  });

  for (const user of deniedAssignmentsUsers) {
    test(`hides assignments nav and blocks direct access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Assignments" })).toHaveCount(0);
      await page.goto("/settings/assignments");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only admin and ESG manager roles can manage assignments.")
      ).toBeVisible();
    });
  }
});

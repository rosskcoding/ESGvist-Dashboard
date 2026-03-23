import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const deniedUsersUsers = [
  demoState.users.esg_manager,
  demoState.users.collector_energy,
  demoState.users.collector_climate,
  demoState.users.reviewer,
  demoState.users.auditor,
];

test.describe("Screen 20 - User Management", () => {
  test("renders user management for platform_admin", async ({ page }) => {
    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings/users");

    await expect(page.getByRole("heading", { name: "User Management" })).toBeVisible();
    await expect(page.getByText("Manage users and invitations for your organization")).toBeVisible();
    await expect(page.getByText("Pending Invitations", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add User" })).toBeVisible();
    await expect(page.getByText("manager@greentech.com")).toBeVisible();
  });

  test("invites and cancels a pending user as platform_admin", async ({ page }) => {
    const inviteEmail = `screen.users.${Date.now()}@example.com`;

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings/users");

    await page.getByRole("button", { name: "Add User" }).click();
    const inviteDialog = page.getByRole("dialog");
    await inviteDialog.getByLabel("Email").fill(inviteEmail);
    await inviteDialog.getByLabel("Role").selectOption("reviewer");
    await inviteDialog.getByLabel("Custom Message (optional)").fill("Screen pack invite flow");
    await inviteDialog.getByRole("button", { name: "Send Invite" }).click();

    await expect(page.getByText(inviteEmail)).toBeVisible();
    const inviteCard = page
      .getByText(inviteEmail, { exact: true })
      .locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]");
    await inviteCard.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByText(inviteEmail)).toHaveCount(0);
  });

  for (const user of deniedUsersUsers) {
    test(`hides users nav and blocks direct access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Users" })).toHaveCount(0);
      await page.goto("/settings/users");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only admin roles can manage organization users.")
      ).toBeVisible();
    });
  }
});

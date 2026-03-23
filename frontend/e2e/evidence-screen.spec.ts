import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const readableUsers = [
  demoState.users.admin,
  demoState.users.esg_manager,
  demoState.users.collector_energy,
  demoState.users.collector_climate,
  demoState.users.auditor,
];

test.describe("Screen 15 - Evidence Repository", () => {
  for (const user of readableUsers) {
    test(`renders evidence repository for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/evidence");

      await expect(page.getByRole("heading", { name: "Evidence Repository" })).toBeVisible();
      await expect(page.getByText("Manage supporting evidence for disclosures")).toBeVisible();
      await expect(page.getByText("Evidence Items")).toBeVisible();
    });
  }

  test("collector adds and deletes a link evidence item", async ({ page }) => {
    const title = `Playwright Evidence Link ${Date.now()}`;

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto("/evidence");

    await page.getByRole("button", { name: "Add Link" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Title").fill(title);
    await dialog.getByLabel("URL").fill("https://example.com/evidence");
    await dialog.getByLabel("Description").fill("Screen-level evidence link");
    await dialog.getByRole("button", { name: "Add Link" }).click();

    const row = page.getByRole("row", { name: new RegExp(title) });
    await expect(row).toBeVisible();

    await row.getByTitle("Delete").click();
    const deleteDialog = page.getByRole("dialog");
    await deleteDialog.getByRole("button", { name: "Delete" }).click();

    await expect(page.getByText(title)).toHaveCount(0);
  });

  test("auditor sees read-only evidence controls", async ({ page }) => {
    await loginThroughUi(page, demoState.users.auditor.email, demoState.password);
    await page.goto("/evidence");

    await expect(
      page.getByText("Auditor access is read-only. Upload, add link, and delete actions are disabled.")
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Link" })).toBeDisabled();
    await expect(page.getByTitle("Delete").first()).toBeDisabled();
  });

  test("reviewer is blocked from evidence repository", async ({ page }) => {
    await loginThroughUi(page, demoState.users.reviewer.email, demoState.password);

    await expect(page.getByRole("link", { name: "Evidence" })).toHaveCount(0);
    await page.goto("/evidence");
    await expect(page.getByText("Access denied")).toBeVisible();
    await expect(
      page.getByText("Reviewers cannot access the evidence repository.")
    ).toBeVisible();
  });
});

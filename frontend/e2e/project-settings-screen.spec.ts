import { expect, test, type Page } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const deniedSettingsUsers = [
  demoState.users.collector_energy,
  demoState.users.collector_climate,
  demoState.users.reviewer,
  demoState.users.auditor,
];

async function createProjectAndOpenSettings(page: Page, projectName: string) {
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  await page.getByRole("button", { name: "Create Project" }).click();
  await page.getByLabel("Project Name").fill(projectName);
  await page.getByRole("button", { name: "Create", exact: true }).click();

  const projectRow = page.getByRole("row", { name: new RegExp(projectName) });
  await expect(projectRow).toBeVisible();
  await projectRow.click();
  await expect(page).toHaveURL(/\/projects\/\d+\/settings/);
  await expect(page.getByRole("heading", { name: projectName })).toBeVisible();
}

async function selectFirstAvailableStandard(page: Page) {
  const standardSelect = page.getByLabel("Standard");
  await expect(standardSelect).toBeVisible();
  const value = await standardSelect
    .locator("option:not([disabled])")
    .first()
    .getAttribute("value");
  expect(value).toBeTruthy();
  await standardSelect.selectOption(value!);
}

test.describe("Screen 12 - Project Settings", () => {
  test("configures a new project end-to-end as platform_admin", async ({ page }) => {
    const projectName = `Project Settings Flow ${Date.now()}`;

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await createProjectAndOpenSettings(page, projectName);

    await expect(page.getByRole("tab", { name: "General" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Standards" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Boundary" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Team" })).toBeVisible();

    await page.getByRole("tab", { name: "Standards" }).click();
    await page.getByRole("button", { name: "Add Standard" }).click();
    await selectFirstAvailableStandard(page);
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByText("No standards attached yet. Add a standard to begin.")).toHaveCount(0);

    await page.getByRole("tab", { name: "Boundary" }).click();
    await page.getByLabel("Boundary").selectOption(String(demoState.boundaries.sustainability.id));
    await expect(page.getByLabel("Boundary")).toHaveValue(String(demoState.boundaries.sustainability.id));
    await page.getByRole("button", { name: "Save Snapshot" }).click();
    await expect(page.getByText("locked", { exact: true })).toBeVisible();

    await page.getByRole("tab", { name: "General" }).click();
    await page.getByRole("button", { name: "Activate" }).click();
    await expect(page.getByRole("button", { name: "Start Review" })).toBeVisible();
  });

  test("renders seeded project settings for esg_manager", async ({ page }) => {
    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto(`/projects/${demoState.project.id}/settings`);

    await expect(page.getByRole("heading", { name: demoState.project.name })).toBeVisible();
    await expect(page.getByText("Project Settings")).toBeVisible();
    await expect(page.getByRole("tab", { name: "General" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Standards" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Boundary" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Team" })).toBeVisible();
  });

  test("shows an inline error when attaching a standard fails", async ({ page }) => {
    const projectName = `Project Settings Error ${Date.now()}`;

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await createProjectAndOpenSettings(page, projectName);
    await page.route("**/api/projects/*/standards", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "PROJECT_STANDARD_ATTACH_FAILED",
            message: "Standard could not be attached to the project.",
            details: [],
            requestId: "pw-project-standard-failure",
          },
        }),
      });
    });

    await page.getByRole("tab", { name: "Standards" }).click();
    await page.getByRole("button", { name: "Add Standard" }).click();
    await selectFirstAvailableStandard(page);
    await page.getByRole("button", { name: "Add", exact: true }).click();

    await expect(
      page.getByText("Standard could not be attached to the project.", { exact: true }).first()
    ).toBeVisible();
  });

  for (const user of deniedSettingsUsers) {
    test(`blocks direct project settings access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto(`/projects/${demoState.project.id}/settings`);
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only admin and ESG manager roles can access project settings.")
      ).toBeVisible();
    });
  }
});

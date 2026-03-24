import { expect, test, type Page } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const allowedProjectUsers = [demoState.users.admin, demoState.users.esg_manager];
const deniedProjectUsers = [
  demoState.users.collector_energy,
  demoState.users.collector_climate,
  demoState.users.reviewer,
  demoState.users.auditor,
];

async function createProjectThroughUi(page: Page, projectName: string) {
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  await page.getByRole("button", { name: "Create Project" }).click();
  await page.getByLabel("Project Name").fill(projectName);
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("row", { name: new RegExp(projectName) })).toBeVisible();
}

test.describe("Screen 11 - Project List", () => {
  for (const user of allowedProjectUsers) {
    test(`renders project list for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/projects");

      await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
      await expect(page.getByText("Manage your ESG reporting projects")).toBeVisible();
      await expect(page.getByText(demoState.project.name)).toBeVisible();
      await expect(page.getByText("All Projects")).toBeVisible();
      await expect(page.getByText("Status")).toBeVisible();
      await expect(page.getByRole("button", { name: "Create Project" })).toBeVisible();
    });
  }

  test("creates a project from the project list as platform_admin", async ({ page }) => {
    const projectName = `Screen Pack Project ${Date.now()}`;

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await createProjectThroughUi(page, projectName);

    const projectRow = page.getByRole("row", { name: new RegExp(projectName) });
    await expect(projectRow).toBeVisible();
    await expect(projectRow.getByText("Draft", { exact: true })).toBeVisible();
  });

  test("shows an inline error when project creation fails", async ({ page }) => {
    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.route("**/api/projects", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "PROJECT_CREATE_FAILED",
            message: "Project could not be created.",
            details: [],
            requestId: "pw-project-create-failure",
          },
        }),
      });
    });

    await page.goto("/projects");
    await page.getByRole("button", { name: "Create Project" }).click();
    await page.getByLabel("Project Name").fill(`Broken Project ${Date.now()}`);
    await page.getByRole("button", { name: "Create", exact: true }).click();

    await expect(
      page.getByText("Project could not be created.", { exact: true }).first()
    ).toBeVisible();
  });

  for (const user of deniedProjectUsers) {
    test(`hides projects nav and blocks direct access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Projects" })).toHaveCount(0);
      await page.goto("/projects");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only admin and ESG manager roles can access project management.")
      ).toBeVisible();
    });
  }
});

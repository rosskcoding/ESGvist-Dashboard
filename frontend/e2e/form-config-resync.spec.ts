import { expect, test } from "@playwright/test";

import {
  createFormConfigResyncScenario,
  loadDemoState,
  loginThroughUi,
} from "./screen-helpers";

const demoState = loadDemoState();

test.describe("Form config stale/resync regressions", () => {
  test("collection shows stale warning and clears it after resync", async ({
    page,
    request,
  }) => {
    const scenario = await createFormConfigResyncScenario(
      request,
      `collection-${Date.now()}`
    );

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto(`/collection?projectId=${scenario.projectId}`);

    await expect(page.getByRole("heading", { name: "Data Collection" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Guided Collection" })).toBeVisible();
    await expect(page.getByText(scenario.generatedConfigName)).toBeVisible();
    await expect(page.getByText("Stale config")).toBeVisible();
    await expect(
      page.getByText("This guided config is out of sync with the current assignments or boundary.")
    ).toBeVisible();
    await expect(page.getByText(scenario.staleIssueMessage)).toBeVisible();

    await page.getByRole("button", { name: "Re-sync Config" }).click();

    await expect(
      page.getByText("Guided collection config re-synced from live assignments.")
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(scenario.resyncedConfigName)).toBeVisible();
    await expect(page.getByText("Stale config")).toHaveCount(0);
    await expect(page.getByText(scenario.staleIssueMessage)).toHaveCount(0);
  });

  test("form config admin view reports stale health and resyncs to healthy", async ({
    page,
    request,
  }) => {
    const scenario = await createFormConfigResyncScenario(
      request,
      `admin-${Date.now()}`
    );

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto("/settings/form-configs");

    await expect(page.getByRole("heading", { name: "Form Configurations" })).toBeVisible();

    const configRow = page
      .locator("tbody tr", {
        has: page.getByText(scenario.generatedConfigName, { exact: true }),
      })
      .first();
    await expect(configRow).toBeVisible();
    await expect(configRow.getByText("Stale", { exact: true })).toBeVisible();
    await configRow.getByRole("button", { name: "Edit" }).click();

    await expect(page.getByText(scenario.generatedConfigName, { exact: true })).toBeVisible();
    await expect(page.getByText(scenario.staleIssueCode, { exact: true })).toBeVisible();
    await expect(page.getByText(scenario.staleIssueMessage)).toBeVisible();

    await page.getByRole("button", { name: "Re-sync Project Config" }).click();

    await expect(
      page.getByText("Project configuration re-synced from live assignments.")
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(scenario.resyncedConfigName)).toBeVisible();
    await expect(
      page.getByText("This config matches the current project assignments and boundary.")
    ).toBeVisible();
    await expect(page.getByText(scenario.staleIssueCode, { exact: true })).toHaveCount(0);
  });
});

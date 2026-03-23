import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

test.describe("Screen 10 - Boundary Preview / Compare", () => {
  test("renders boundary tab in project settings for esg_manager", async ({ page }) => {
    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto(`/projects/${demoState.project.id}/settings`);

    await page.getByRole("tab", { name: "Boundary" }).click();

    await expect(page.getByText("Boundary Selection")).toBeVisible();
    await expect(page.getByText("Boundary Details")).toBeVisible();
    await expect(page.getByLabel("Boundary")).toBeVisible();
    await expect(page.getByText("Entities in scope")).toBeVisible();
    await expect(page.getByText("Excluded entities")).toBeVisible();
    await expect(page.getByText("Snapshot Status")).toBeVisible();
  });
});

import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

test.describe("Screen 27-29 - Report and Audit", () => {
  test("manager sees blocking readiness state and empty preview route", async ({ page }) => {
    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto("/report");

    await expect(page.getByRole("heading", { name: "Report & Export" })).toBeVisible();
    await expect(page.getByText("Readiness Summary")).toBeVisible();
    await expect(page.getByText("Boundary Validation")).toBeVisible();
    await expect(page.getByText("Export Formats")).toBeVisible();
    await expect(page.getByText("Blocking Issues")).toBeVisible();

    await page.goto("/report/preview");
    await expect(page.getByRole("heading", { name: "Report Preview" })).toBeVisible();
    await expect(page.getByText("No export jobs found.")).toBeVisible();
  });

  for (const user of [demoState.users.collector_energy, demoState.users.auditor, demoState.users.admin]) {
    test(`blocks report screen for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/report");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only admin and ESG manager roles can access report readiness and export.")
      ).toBeVisible();
    });
  }

  test("auditor sees audit log and can filter entries", async ({ page }) => {
    await loginThroughUi(page, demoState.users.auditor.email, demoState.password);
    await page.goto("/audit");

    await expect(page.getByRole("heading", { name: "Audit Log" })).toBeVisible();
    await expect(page.getByText("Filters")).toBeVisible();

    const firstRow = page.locator("tbody tr").first();
    const visibleEntityType = (await firstRow.locator("td").nth(3).textContent())?.trim() ?? "";

    await page.getByLabel("Entity Type").fill(visibleEntityType);
    await expect(page.locator("tbody tr").first()).toBeVisible();

    await page.locator("tbody tr").first().click();
    await expect(page.getByText("Request ID")).toBeVisible();
    await expect(page.getByText("Changes", { exact: true })).toBeVisible();
  });

  for (const user of [demoState.users.collector_energy, demoState.users.esg_manager, demoState.users.admin]) {
    test(`blocks audit screen for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/audit");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(page.getByText("Only admin and auditor roles can access audit logs.")).toBeVisible();
    });
  }
});

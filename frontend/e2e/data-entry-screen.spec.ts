import { expect, test, type APIRequestContext } from "@playwright/test";

import { apiPost, loadDemoState, loginByApi, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

async function createDraftEnergyDataPoint(request: APIRequestContext) {
  const auth = await loginByApi(
    request,
    demoState.users.collector_energy.email,
    demoState.password,
  );

  return apiPost<{ id: number }>(
    request,
    `${demoState.api_url!.replace("localhost", "127.0.0.1")}/projects/${demoState.project.id}/data-points`,
    auth.headers,
    {
      shared_element_id: demoState.shared_elements!.energy_total_mwh.id,
      entity_id: demoState.entities!.generation.id,
      numeric_value: 120000.5,
      unit_code: "MWH",
    },
  );
}

test.describe("Screen 14 - Data Entry Wizard", () => {
  test("collector submits a draft numeric data point through the wizard", async ({ page, request }) => {
    const draft = await createDraftEnergyDataPoint(request);

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto(`/collection/${draft.id}`);

    await expect(page.getByRole("button", { name: "Back to Collection" })).toBeVisible();
    await expect(page.getByText("ENERGY_TOTAL_MWH", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Value").fill("130000.7");
    await page.getByLabel("Unit").selectOption("MWH");
    await page.getByLabel("Methodology").selectOption("Utility bill reconciliation");
    await page.locator('input[type="file"]').setInputFiles({
      name: "meter-evidence.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 demo evidence"),
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByText("Preview & Gate Check")).toBeVisible();
    await page.getByRole("button", { name: "Run Gate Check" }).click();
    await expect(page.getByText("All checks passed. Ready to submit.")).toBeVisible();

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByText("Confirm Submission")).toBeVisible();
    await page.getByRole("button", { name: "Submit Data Point" }).click();

    await expect(page.getByText("Data point submitted successfully")).toBeVisible();
    await expect(page.getByRole("button", { name: "Back to Collection" }).last()).toBeVisible();
  });

  test("shows read-only banner for an approved collector data point", async ({ page }) => {
    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto("/collection/1");

    await expect(page.getByText("This data point is read-only while it is in the")).toBeVisible();
    await expect(page.getByRole("button", { name: "Next", exact: true })).toBeDisabled();
  });

  for (const user of [demoState.users.reviewer, demoState.users.auditor]) {
    test(`blocks direct wizard access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/collection/1");

      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only collectors and ESG managers can edit collection entries.")
      ).toBeVisible();
    });
  }
});

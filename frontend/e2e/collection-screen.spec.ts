import { expect, test } from "@playwright/test";

import {
  apiPost,
  createGuidedCollectionConfig,
  createJourneyAssignment,
  loadDemoState,
  loginByApi,
  loginThroughUi,
} from "./screen-helpers";

const demoState = loadDemoState();

const allowedUsers = [
  demoState.users.admin,
  demoState.users.esg_manager,
  demoState.users.collector_energy,
  demoState.users.collector_climate,
];
const deniedUsers = [demoState.users.reviewer, demoState.users.auditor];

test.describe("Screen 13 - Collection Table", () => {
  for (const user of allowedUsers) {
    test(`renders collection table for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);
      await page.goto("/collection");

      await expect(page.getByRole("heading", { name: "Data Collection" })).toBeVisible();
      await expect(
        page.getByText("Track assigned metrics, open data entry, and submit values for the current reporting period.")
      ).toBeVisible();
      await expect(
        page.getByText("This is not a Jira-style task board. Each row is one assigned metric")
      ).toBeVisible();
      await expect(page.getByPlaceholder("Search by metric code or name...")).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Metric Code" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Reporting Boundary" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Enter Data" }).first()).toBeVisible();
    });
  }

  test("filters the collection table for ESG manager", async ({ page }) => {
    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto("/collection");

    await page.getByPlaceholder("Search by metric code or name...").fill("SCOPE1");
    await expect(page.getByText("SCOPE1_TCO2E")).toBeVisible();
    await expect(page.getByText("ENERGY_TOTAL_MWH")).toHaveCount(0);
  });

  test("collector sees only their own seeded collection entries", async ({ page }) => {
    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto("/collection");

    await expect(page.getByRole("cell", { name: "ENERGY_TOTAL_MWH" }).first()).toBeVisible();
    await expect(page.getByText("SCOPE1_TCO2E")).toHaveCount(0);
  });

  test("guided quick entry creates a draft, saves it, and can open the full wizard", async ({
    page,
    request,
  }) => {
    const suffix = `guided-save-${Date.now()}`;
    const journey = await createJourneyAssignment(request, suffix);
    await createGuidedCollectionConfig(request, suffix, [
      {
        shared_element_id: journey.sharedElementId,
        assignment_id: journey.assignmentId,
        entity_id: journey.entityId,
        help_text: `Quick entry for ${journey.code}`,
        tooltip: `${journey.code}: ${journey.name}`,
      },
    ]);

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto(`/collection?projectId=${demoState.project.id}`);

    await expect(page.getByRole("heading", { name: "Guided Collection" })).toBeVisible();
    const guidedCard = page
      .locator("div.rounded-2xl", { has: page.getByText(journey.code, { exact: true }) })
      .first();
    await expect(guidedCard).toBeVisible();
    await guidedCard.getByRole("button", { name: "Quick entry" }).click();

    const dialog = page.locator("dialog[open]");
    await expect(dialog.getByText("Guided Quick Entry")).toBeVisible();
    await dialog.getByLabel("Value").fill("125500.1");
    await dialog.getByLabel("Unit").selectOption("MWH");
    await dialog.getByLabel("Methodology").selectOption("Utility bill reconciliation");
    await dialog.getByRole("button", { name: "Save Draft" }).click();

    await expect(dialog.getByText("Draft saved in guided collection.")).toBeVisible();
    await dialog.getByRole("button", { name: "Close", exact: true }).first().click();

    await expect(guidedCard.getByRole("button", { name: "Continue entry" })).toBeVisible();
    await guidedCard.getByRole("button", { name: "Continue entry" }).click();

    const reopenedDialog = page.locator("dialog[open]");
    await reopenedDialog.getByRole("button", { name: "Open Full Wizard" }).click();

    await expect(page).toHaveURL(new RegExp(`/collection/\\d+\\?projectId=${demoState.project.id}`));
    await expect(page.getByRole("button", { name: "Back to Collection" })).toBeVisible();
  });

  test("collector submits a guided quick entry directly from collection", async ({
    page,
    request,
  }) => {
    const suffix = `guided-submit-${Date.now()}`;
    const journey = await createJourneyAssignment(request, suffix);
    await createGuidedCollectionConfig(request, suffix, [
      {
        shared_element_id: journey.sharedElementId,
        assignment_id: journey.assignmentId,
        entity_id: journey.entityId,
        help_text: `Submission quick entry for ${journey.code}`,
        tooltip: `${journey.code}: ${journey.name}`,
      },
    ]);

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto(`/collection?projectId=${demoState.project.id}`);

    const guidedCard = page
      .locator("div.rounded-2xl", { has: page.getByText(journey.code, { exact: true }) })
      .first();
    await guidedCard.getByRole("button", { name: "Quick entry" }).click();

    const dialog = page.locator("dialog[open]");
    await dialog.getByLabel("Value").fill("130000.7");
    await dialog.getByLabel("Unit").selectOption("MWH");
    await dialog.getByLabel("Methodology").selectOption("Utility bill reconciliation");
    await dialog.locator('input[type="file"]').setInputFiles({
      name: "guided-meter-evidence.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 guided evidence"),
    });

    await dialog.getByRole("button", { name: "Check Readiness" }).click();
    await expect(dialog.getByText("Gate checks passed. Field is ready to submit.")).toBeVisible({
      timeout: 15_000,
    });

    await dialog.getByRole("button", { name: "Submit" }).click();
    await expect(
      dialog.getByText("Data point submitted and moved into review.")
    ).toBeVisible({ timeout: 15_000 });
    await expect(dialog.getByText("in_review").first()).toBeVisible();
  });

  test("legacy guided config falls back to table when a field resolves to multiple contexts", async ({
    page,
    request,
  }) => {
    const suffix = `guided-multi-${Date.now()}`;
    const adminAuth = await loginByApi(request, demoState.users.admin.email, demoState.password);
    const code = `GUIDED_MULTI_${suffix}`;
    const name = `Guided Multi Context ${suffix}`;

    const firstAssignment = await apiPost<{ id: number; shared_element_id: number }>(
      request,
      `${demoState.api_url!.replace("localhost", "127.0.0.1")}/projects/${demoState.project.id}/assignments`,
      adminAuth.headers,
      {
        shared_element_code: code,
        shared_element_name: name,
        entity_id: demoState.entities.generation.id,
        collector_id: demoState.users.collector_energy.id,
        reviewer_id: demoState.users.reviewer.id,
      }
    );

    await apiPost<{ id: number; shared_element_id: number }>(
      request,
      `${demoState.api_url!.replace("localhost", "127.0.0.1")}/projects/${demoState.project.id}/assignments`,
      adminAuth.headers,
      {
        shared_element_code: code,
        shared_element_name: name,
        entity_id: demoState.entities.grid.id,
        collector_id: demoState.users.collector_energy.id,
        reviewer_id: demoState.users.reviewer.id,
      }
    );

    await createGuidedCollectionConfig(request, suffix, [
      {
        shared_element_id: firstAssignment.shared_element_id,
        help_text: "Legacy config without assignment context",
        tooltip: `${code}: ${name}`,
      },
    ]);

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto(`/collection?projectId=${demoState.project.id}`);

    const guidedCard = page
      .locator("div.rounded-2xl", { has: page.getByText(code, { exact: true }) })
      .first();
    await expect(guidedCard.getByText("2 contexts")).toBeVisible();
    await guidedCard.getByRole("button", { name: "Show rows" }).click();

    await expect(page.getByPlaceholder("Search by metric code or name...")).toHaveValue(code);
    const matchingRows = page.locator("#collection-table tbody tr").filter({ hasText: code });
    await expect(matchingRows).toHaveCount(2);
  });

  test("collection resolves organization default guided config when project has no project-specific config", async ({
    page,
    request,
  }) => {
    const suffix = `guided-org-default-${Date.now()}`;
    const adminAuth = await loginByApi(request, demoState.users.admin.email, demoState.password);
    const apiUrl = demoState.api_url!.replace("localhost", "127.0.0.1");

    const project = await apiPost<{ id: number; name: string }>(
      request,
      `${apiUrl}/projects`,
      adminAuth.headers,
      { name: `Guided Org Default ${suffix}` }
    );

    const assignment = await apiPost<{ id: number; shared_element_id: number }>(
      request,
      `${apiUrl}/projects/${project.id}/assignments`,
      adminAuth.headers,
      {
        shared_element_code: `GUIDED_ORG_${suffix}`,
        shared_element_name: `Guided Org Default Metric ${suffix}`,
        entity_id: demoState.entities.root.id,
        collector_id: demoState.users.collector_energy.id,
        reviewer_id: demoState.users.reviewer.id,
      }
    );

    const configName = `PW Org Default ${suffix}`;
    await createGuidedCollectionConfig(
      request,
      suffix,
      [
        {
          shared_element_id: assignment.shared_element_id,
          entity_id: demoState.entities.root.id,
          help_text: "Organization default guided config",
        },
      ],
      {
        projectId: null,
        name: configName,
        description: "Organization default coverage for guided collection.",
      }
    );

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto(`/collection?projectId=${project.id}`);

    await expect(page.getByRole("heading", { name: "Guided Collection" })).toBeVisible();
    await expect(page.getByText(`${configName} (organization default)`)).toBeVisible();
    await expect(page.getByText(`GUIDED_ORG_${suffix}`, { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Quick entry" })).toBeVisible();
  });

  test("shows an inline error when creating a data point from collection fails", async ({
    page,
  }) => {
    const code = `PW-COLLECT-FAIL-${Date.now()}`;

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.route("**/api/projects/*/assignments", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          assignments: [
            {
              id: 999001,
              shared_element_id: 555001,
              shared_element_code: code,
              shared_element_name: "Playwright Collection Failure",
              entity_id: 101,
              entity_name: "Scenario Entity",
              facility_id: null,
              facility_name: null,
              boundary_included: true,
              consolidation_method: "full",
              status: "assigned",
            },
          ],
        }),
      });
    });
    await page.route("**/api/projects/*/data-points", async (route) => {
      if (route.request().method() === "GET") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "DATA_POINT_CREATE_FAILED",
            message: "Unable to create a draft data point right now.",
            details: [],
            requestId: "pw-collection-failure",
          },
        }),
      });
    });

    await page.goto(`/collection?projectId=${demoState.project.id}`);
    await page.getByPlaceholder("Search by metric code or name...").fill(code);
    const row = page.getByRole("row", { name: new RegExp(code) });
    await expect(row).toBeVisible({ timeout: 15_000 });
    await row.getByRole("button", { name: "Enter Data" }).click();

    await expect(
      page.getByText("Unable to create a draft data point right now.")
    ).toBeVisible();
  });

  for (const user of deniedUsers) {
    test(`hides collection nav and blocks direct access for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Collection" })).toHaveCount(0);
      await page.goto("/collection");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Only collectors and ESG managers can access data collection.")
      ).toBeVisible();
    });
  }
});

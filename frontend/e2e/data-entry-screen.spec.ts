import { expect, test } from "@playwright/test";

import {
  createApprovedCollectionItem,
  createAssignedDraftCollectionItem,
  loadDemoState,
  loginThroughUi,
} from "./screen-helpers";

const demoState = loadDemoState();

test.describe("Screen 14 - Data Entry Wizard", () => {
  test("collector submits a draft numeric data point through the wizard", async ({ page, request }) => {
    const draft = await createAssignedDraftCollectionItem(request, `wizard-${Date.now()}`);

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto(`/collection/${draft.id}`);

    await expect(
      page.getByRole("button", { name: "Back to Collection" })
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(draft.code, { exact: true })).toBeVisible({ timeout: 15_000 });

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
    await expect(page.getByText("Preview & Gate Check")).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: "Run Gate Check" }).click();
    await expect(page.getByText("All checks passed. Ready to submit.")).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByText("Confirm Submission")).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: "Submit Data Point" }).click();

    await expect(page.getByText("Data point submitted successfully")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("button", { name: "Back to Collection" }).last()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("shows read-only banner for an approved collector data point", async ({ page, request }) => {
    const approved = await createApprovedCollectionItem(request, `readonly-${Date.now()}`);

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto(`/collection/${approved.id}`);

    await expect(page.getByText("This data point is read-only while it is in the")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("button", { name: "Next", exact: true })).toBeDisabled();
  });

  test("shows a gate-check error banner when preview preparation fails", async ({
    page,
    request,
  }) => {
    const draft = await createAssignedDraftCollectionItem(request, `wizard-gate-fail-${Date.now()}`);

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.route("**/api/gate-check", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "GATE_CHECK_ERROR",
            message: "Gate check service is temporarily unavailable.",
            details: [],
            requestId: "pw-gate-failure",
          },
        }),
      });
    });

    await page.goto(`/collection/${draft.id}`);
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
    await page.getByRole("button", { name: "Run Gate Check" }).click();

    await expect(
      page.getByText("Gate check service is temporarily unavailable.", { exact: true })
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Blocker:")).toBeVisible();
  });

  test("legacy wizard gate check preview does not save the draft or upload evidence", async ({
    page,
    request,
  }) => {
    const draft = await createAssignedDraftCollectionItem(request, `legacy-preview-safe-${Date.now()}`);
    let patchCalls = 0;
    let uploadCalls = 0;
    let linkCalls = 0;

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.route(`**/api/data-points/${draft.id}`, async (route) => {
      if (route.request().method() === "PATCH") {
        patchCalls += 1;
      }
      await route.continue();
    });
    await page.route("**/api/evidences/upload", async (route) => {
      uploadCalls += 1;
      await route.continue();
    });
    await page.route(`**/api/data-points/${draft.id}/evidences`, async (route) => {
      if (route.request().method() === "POST") {
        linkCalls += 1;
      }
      await route.continue();
    });

    await page.goto(`/collection/${draft.id}`);
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Value").fill("130000.7");
    await page.getByLabel("Unit").selectOption("MWH");
    await page.getByLabel("Methodology").selectOption("Utility bill reconciliation");
    await page.locator('input[type="file"]').setInputFiles({
      name: "legacy-preview-evidence.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 legacy preview evidence"),
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Run Gate Check" }).click();
    await expect(page.getByText("All checks passed. Ready to submit.")).toBeVisible({
      timeout: 15_000,
    });

    expect(patchCalls).toBe(0);
    expect(uploadCalls).toBe(0);
    expect(linkCalls).toBe(0);
  });

  test("legacy wizard uploads a second evidence batch after a failed submit", async ({
    page,
    request,
  }) => {
    const draft = await createAssignedDraftCollectionItem(request, `legacy-evidence-batches-${Date.now()}`);
    let submitCalls = 0;
    let uploadCalls = 0;
    let linkCalls = 0;

    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.route(`**/api/data-points/${draft.id}/submit`, async (route) => {
      submitCalls += 1;
      if (submitCalls === 1) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "SUBMIT_FAILED",
              message: "First submit attempt failed.",
              details: [],
              requestId: "pw-submit-failure",
            },
          }),
        });
        return;
      }
      await route.continue();
    });
    await page.route("**/api/evidences/upload", async (route) => {
      uploadCalls += 1;
      await route.continue();
    });
    await page.route(`**/api/data-points/${draft.id}/evidences`, async (route) => {
      if (route.request().method() === "POST") {
        linkCalls += 1;
      }
      await route.continue();
    });

    await page.goto(`/collection/${draft.id}`);
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Value").fill("130000.7");
    await page.getByLabel("Unit").selectOption("MWH");
    await page.getByLabel("Methodology").selectOption("Utility bill reconciliation");
    await page.locator('input[type="file"]').setInputFiles({
      name: "legacy-first-batch.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 first evidence batch"),
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Run Gate Check" }).click();
    await expect(page.getByText("All checks passed. Ready to submit.")).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Submit Data Point" }).click();
    await expect(page.getByText("First submit attempt failed.", { exact: true })).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("button", { name: "Back", exact: true }).click();
    await page.getByRole("button", { name: "Back", exact: true }).click();
    await page.locator('input[type="file"]').setInputFiles({
      name: "legacy-second-batch.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 second evidence batch"),
    });
    await expect(page.getByText("legacy-second-batch.pdf")).toBeVisible();

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Run Gate Check" }).click();
    await expect(page.getByText("All checks passed. Ready to submit.")).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Submit Data Point" }).click();
    await expect(page.getByText("Data point submitted successfully")).toBeVisible({
      timeout: 15_000,
    });

    expect(uploadCalls).toBe(2);
    expect(linkCalls).toBe(2);
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

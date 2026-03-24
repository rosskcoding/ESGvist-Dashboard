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

  test("manager sees an inline error when queueing an export fails", async ({ page }) => {
    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.route("**/api/projects/*/export/readiness", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ready: true,
          overall_ready: true,
          completion_percent: 100,
          total_items: 5,
          complete: 5,
          partial: 0,
          missing: 0,
          blocking_issues: 0,
          warnings: 0,
          blocking_issue_details: [],
          warning_details: [],
          boundary_validation: {
            selected_boundary: "Scenario Boundary",
            snapshot_locked: true,
            entities_in_scope: 2,
            manual_overrides: 0,
            boundary_differs_from_default: false,
            entities_without_data: [],
          },
        }),
      });
    });
    await page.route("**/api/projects/*/exports", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      });
    });
    await page.route("**/api/projects/*/export/report*", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "EXPORT_QUEUE_FAILED",
            message: "Export job could not be queued.",
            details: [],
            requestId: "pw-report-queue-failure",
          },
        }),
      });
    });

    await page.goto("/report");
    await page.getByRole("button", { name: "Queue Full Report PDF" }).click();
    await expect(page.getByText("Export job could not be queued.")).toBeVisible();
  });

  test("preview screen shows failed export job details", async ({ page }) => {
    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.route("**/api/projects/*/exports", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: 99001,
              report_type: "project_report",
              export_format: "pdf",
              status: "failed",
              artifact_name: "broken-report.pdf",
              artifact_encoding: null,
              created_at: new Date().toISOString(),
              completed_at: null,
              error_message: "Export worker failed to build the artifact.",
            },
          ],
          total: 1,
        }),
      });
    });

    await page.goto("/report/preview?projectId=1&jobId=99001");
    await expect(page.getByRole("heading", { name: "Report Preview" })).toBeVisible();
    await expect(page.getByText("Export worker failed to build the artifact.")).toBeVisible();
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

import { expect, test, type Page } from "@playwright/test";

import {
  captureMatchingPageProblems,
  createManagerExportJourneyProject,
  createPendingExportPreviewScenario,
  loadDemoState,
  loginThroughUi,
} from "./screen-helpers";

const demoState = loadDemoState();

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function setSwitchState(page: Page, label: string, checked: boolean) {
  const control = page.getByRole("switch", { name: label });
  await expect(control).toBeVisible();
  const current = (await control.getAttribute("aria-checked")) === "true";
  if (current !== checked) {
    await control.click();
  }
  await expect(control).toHaveAttribute("aria-checked", checked ? "true" : "false");
}

test.describe("Phase 3 - Edge and error-path scenarios", () => {
  test("notifications screen renders without React asChild console errors", async ({ page }) => {
    const problems = captureMatchingPageProblems(page, [
      /React does not recognize the `asChild` prop/i,
      /aschilde?/i,
      /hydration error/i,
    ]);

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto("/notifications");

    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    await expect(page.getByText("Delivery Preferences")).toBeVisible();
    await page.waitForTimeout(300);

    expect(problems, problems.join("\n")).toEqual([]);
  });

  test("company structure tree renders without nested-button hydration errors", async ({ page }) => {
    const problems = captureMatchingPageProblems(page, [
      /cannot be a descendant of <button>/i,
      /validateDOMNesting/i,
      /hydration error/i,
    ]);

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings/company-structure");

    await expect(page.getByRole("heading", { name: "Company Structure" })).toBeVisible();
    await expect(page.getByRole("button", { name: new RegExp(`Collapse ${demoState.entities.root.name}`) })).toBeVisible();
    const generationRow = page.getByRole(
      "button",
      { name: new RegExp(`^${escapeRegex(demoState.entities.generation.name)} active$`) }
    );
    await expect(generationRow).toBeVisible();

    await page.getByRole("button", { name: new RegExp(`Collapse ${demoState.entities.root.name}`) }).click();
    await expect(generationRow).toHaveCount(0);

    await page.getByRole("button", { name: new RegExp(`Expand ${demoState.entities.root.name}`) }).click();
    await expect(generationRow).toBeVisible();
    await page.waitForTimeout(300);

    expect(problems, problems.join("\n")).toEqual([]);
  });

  test("organization settings rejects disabling every login method", async ({ page }) => {
    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings");

    await expect(page.getByRole("heading", { name: "Organization Settings" })).toBeVisible();
    await expect(page.getByText("Authentication Policy", { exact: true })).toBeVisible();

    await setSwitchState(page, "Allow password login", false);
    await setSwitchState(page, "Allow SSO login", false);
    await setSwitchState(page, "Enforce SSO", false);
    await page.getByRole("button", { name: "Save Auth Policy" }).click();

    await expect(page.getByText("Organization must allow at least one login method")).toBeVisible();
  });

  test("report preview shows empty state for a fresh project without export jobs", async ({ page, request }) => {
    const scenario = await createManagerExportJourneyProject(request, `${Date.now()}-phase3-empty`);

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto(`/report/preview?projectId=${scenario.projectId}`);

    await expect(page.getByRole("heading", { name: "Report Preview" })).toBeVisible();
    await expect(page.getByText("No export jobs found.")).toBeVisible();
  });

  test("report preview shows pending warning before export worker completes the job", async ({ page, request }) => {
    const scenario = await createPendingExportPreviewScenario(request, `${Date.now()}-phase3-pending`);

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto(`/report/preview?projectId=${scenario.projectId}&jobId=${scenario.jobId}`);

    await expect(page.getByRole("heading", { name: "Report Preview" })).toBeVisible();
    await expect(page.getByText("This export job is not completed yet. Run export jobs or wait for processing before previewing.")).toBeVisible();
    await expect(page.getByText("queued", { exact: true })).toBeVisible();
  });

  test("collector is blocked from direct access to report preview", async ({ page }) => {
    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);
    await page.goto(`/report/preview?projectId=${demoState.project.id}`);

    await expect(page.getByText("Access denied")).toBeVisible();
    await expect(page.getByText("Only admin and ESG manager roles can preview report exports.")).toBeVisible();
  });
});

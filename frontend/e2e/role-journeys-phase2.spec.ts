import { expect, test, type Browser, type Page } from "@playwright/test";

import {
  apiGet,
  createManagerExportJourneyProject,
  createJourneyAssignment,
  loadDemoState,
  loginByApi,
  loginThroughUi,
  makeProjectReadyForExport,
  runExportJobs,
} from "./screen-helpers";

const demoState = loadDemoState();
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3002";

type AuditResponse = {
  items: Array<{
    id: number;
    entity_type: string;
    entity_id: number | null;
    action: string;
  }>;
  total: number;
};


type ApiHeaders = Record<string, string>;

async function apiPost<T>(request: Parameters<typeof loginByApi>[0], url: string, headers: ApiHeaders, data: unknown) {
  const response = await request.post(url, { headers, data });
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as T;
}

test.describe.configure({ mode: "serial" });

async function openRolePage(browser: Browser, email: string) {
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  await loginThroughUi(page, email, demoState.password);
  return { context, page };
}

function collectionRow(page: Page, code: string) {
  return page.locator("tbody tr", { hasText: code }).first();
}

function reviewQueueItem(page: Page, code: string) {
  return page.getByRole("button", { name: new RegExp(code) }).first();
}

test("collector revision cycle ends in reviewer approval and auditor-visible audit trail", async ({
  browser,
  request,
}) => {
  const suffix = `${Date.now()}`;
  const journey = await createJourneyAssignment(request, suffix, "collector_energy");
  let dataPointId = 0;

  const collectorSession = await openRolePage(browser, demoState.users.collector_energy.email);
  try {
    const page = collectorSession.page;
    await page.goto("/collection");
    await page.getByPlaceholder("Search by code or name...").fill(journey.code);
    await expect(collectionRow(page, journey.code)).toBeVisible();
    await collectionRow(page, journey.code).getByRole("button", { name: "Enter Data" }).click();

    await expect(page).toHaveURL(/\/collection\/\d+(\?projectId=\d+)?$/, { timeout: 15_000 });
    const openedId = page.url().match(/\/collection\/(\d+)/)?.[1];
    expect(openedId).toBeTruthy();
    dataPointId = Number(openedId);

    await expect(page.getByText(journey.code, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Value").fill("451.2");
    await page.getByLabel("Unit").selectOption("MWH");
    await page.getByLabel("Methodology").selectOption("Utility bill reconciliation");
    await page.locator('input[type="file"]').setInputFiles({
      name: `journey-${suffix}.pdf`,
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 phase2 journey evidence"),
    });
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Run Gate Check" }).click();
    await expect(page.getByText("All checks passed. Ready to submit.")).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Submit Data Point" }).click();
    await expect(page.getByText("Data point submitted successfully")).toBeVisible();
  } finally {
    await collectorSession.context.close();
  }

  const reviewerRevisionSession = await openRolePage(browser, demoState.users.reviewer.email);
  try {
    const page = reviewerRevisionSession.page;
    await page.goto("/validation");
    await expect(reviewQueueItem(page, journey.code)).toBeVisible({ timeout: 15_000 });
    await reviewQueueItem(page, journey.code).click();
    await expect(page.getByRole("heading", { name: journey.name })).toBeVisible();
    await page.getByRole("button", { name: "Request Revision" }).click();
    await page.getByLabel("Review reason").selectOption("DATA_QUALITY_ISSUE");
    await page.getByLabel("Review action comment").fill(
      "Adjust the final reconciled value and resubmit with the corrected figure."
    );
    await page.getByRole("button", { name: "Send revision request" }).click();
    await expect(reviewQueueItem(page, journey.code)).toHaveCount(0);
  } finally {
    await reviewerRevisionSession.context.close();
  }

  const collectorRevisionSession = await openRolePage(browser, demoState.users.collector_energy.email);
  try {
    const page = collectorRevisionSession.page;
    await page.goto(`/collection/${dataPointId}`);
    await expect(page.getByText(journey.code, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByLabel("Value").fill("452.8");
    await page.getByLabel("Methodology").selectOption("Utility bill reconciliation");
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Run Gate Check" }).click();
    await expect(page.getByText("All checks passed. Ready to submit.")).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Submit Data Point" }).click();
    await expect(page.getByText("Data point submitted successfully")).toBeVisible();
  } finally {
    await collectorRevisionSession.context.close();
  }

  const reviewerApprovalSession = await openRolePage(browser, demoState.users.reviewer.email);
  try {
    const page = reviewerApprovalSession.page;
    await page.goto("/validation");
    await expect(reviewQueueItem(page, journey.code)).toBeVisible({ timeout: 15_000 });
    await reviewQueueItem(page, journey.code).click();
    await page.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(reviewQueueItem(page, journey.code)).toHaveCount(0);
  } finally {
    await reviewerApprovalSession.context.close();
  }

  const auditorAuth = await loginByApi(request, demoState.users.auditor.email, demoState.password);
  const auditEntries = await apiGet<AuditResponse>(
    request,
    `${demoState.api_url!.replace("localhost", "127.0.0.1")}/audit-log?page=1&page_size=20&entity_id=${dataPointId}`,
    auditorAuth.headers
  );

  expect(auditEntries.total).toBeGreaterThan(0);
  const dataPointAudit = auditEntries.items.find((entry) => entry.entity_id === dataPointId);
  expect(dataPointAudit).toBeTruthy();

  const auditorSession = await openRolePage(browser, demoState.users.auditor.email);
  try {
    const page = auditorSession.page;
    await page.goto("/audit");
    await page.getByLabel("Entity ID").fill(String(dataPointId));
    await page.getByLabel("Entity Type").fill(dataPointAudit!.entity_type);
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await expect(page.locator("tbody")).toContainText(String(dataPointId));
    await page.locator("tbody tr").first().click();
    await expect(page.getByText("Request ID")).toBeVisible();
    await expect(page.getByText("Changes", { exact: true })).toBeVisible();
  } finally {
    await auditorSession.context.close();
  }
});

test("manager moves a project through settings, readiness, export preview, and publish", async ({
  browser,
  request,
}) => {
  const suffix = `${Date.now()}`;
  const journey = await createManagerExportJourneyProject(request, suffix);

  const managerSession = await openRolePage(browser, demoState.users.esg_manager.email);
  try {
    const page = managerSession.page;
    await page.goto(`/projects/${journey.projectId}/settings`);
    await expect(page.getByRole("heading", { name: journey.projectName })).toBeVisible();

    await page.getByRole("tab", { name: "Standards" }).click();
    await page.getByRole("button", { name: "Add Standard" }).click();
    await page.getByLabel("Standard").selectOption(String(journey.standardId));
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByText(journey.standardCode, { exact: true })).toBeVisible();

    await page.getByRole("tab", { name: "Boundary" }).click();
    await page.getByLabel("Boundary").selectOption(String(demoState.boundaries!.sustainability.id));
    await expect(page.getByLabel("Boundary")).toHaveValue(String(demoState.boundaries!.sustainability.id));
    await page.getByRole("button", { name: "Save Snapshot" }).click();
    await expect(page.getByText("locked", { exact: true })).toBeVisible();

    await page.getByRole("tab", { name: "General" }).click();
    const activateResponse = page.waitForResponse(
      (response) =>
        response.url().includes(`/api/projects/${journey.projectId}/activate`) &&
        response.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Activate" }).click();
    expect((await activateResponse).ok()).toBeTruthy();
    await page.reload();
    await expect(page.getByRole("button", { name: "Start Review" })).toBeVisible({ timeout: 15_000 });
  } finally {
    await managerSession.context.close();
  }

  await makeProjectReadyForExport(
    request,
    journey.projectId,
    journey.itemId,
    journey.sharedElementId,
    journey.entityId,
  );

  const managerReviewSession = await openRolePage(browser, demoState.users.esg_manager.email);
  try {
    const page = managerReviewSession.page;
    await page.goto(`/projects/${journey.projectId}/settings`);
    const reviewResponse = page.waitForResponse(
      (response) =>
        response.url().includes(`/api/projects/${journey.projectId}/start-review`) &&
        response.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Start Review" }).click();
    const resolvedReviewResponse = await reviewResponse;
    const reviewBody = await resolvedReviewResponse.text();
    expect(resolvedReviewResponse.ok(), reviewBody).toBeTruthy();
    await page.reload();
    await expect(page.getByRole("button", { name: "Publish" })).toBeVisible({ timeout: 15_000 });
  } finally {
    await managerReviewSession.context.close();
  }

  const managerReportSession = await openRolePage(browser, demoState.users.esg_manager.email);
  try {
    const page = managerReportSession.page;
    await page.goto(`/report?projectId=${journey.projectId}`);
    await expect(page.getByRole("heading", { name: "Report & Export" })).toBeVisible();
    await expect(page.getByText("Readiness Summary")).toBeVisible();
    await expect(page.getByText("Ready to Publish")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Selected Boundary")).toBeVisible();
    await expect(page.getByText("FY2025 Sustainability Boundary")).toBeVisible();

    await page.getByRole("button", { name: "Queue Full Report PDF" }).click();
    await expect(page.getByText("project_report.pdf", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("queued", { exact: true }).first()).toBeVisible();

    const exportRun = await runExportJobs(request);
    expect(exportRun.completed).toBeGreaterThanOrEqual(1);

    await page.getByRole("button", { name: "Refresh readiness" }).click();
    await expect(page.getByRole("link", { name: "Preview latest" })).toBeEnabled({ timeout: 15_000 });

    await page.getByRole("link", { name: "Preview latest" }).click();
    await expect(page).toHaveURL(new RegExp(`/report/preview\\?projectId=${journey.projectId}.*jobId=`));
    await expect(page.getByRole("heading", { name: "Report Preview" })).toBeVisible();
    await expect(page.getByText("Artifact Preview")).toBeVisible();
    await expect(page.getByText("application/pdf")).toBeVisible();

    await page.getByRole("link", { name: "Back to report" }).click();
    await expect(page).toHaveURL(new RegExp(`/report\\?projectId=${journey.projectId}`));
    await page.getByRole("button", { name: "Publish Project" }).click();
    await page.getByRole("button", { name: "Confirm Publish" }).click();
    await page.goto(`/projects/${journey.projectId}/settings`);
    await expect(page.getByText("Project has been published")).toBeVisible({ timeout: 15_000 });
  } finally {
    await managerReportSession.context.close();
  }
});

test("admin rolls out a custom disclosure and collector sees the new collection task", async ({
  browser,
  request,
}) => {
  const suffix = `${Date.now()}`;
  const standardCode = `PH2-STD-${suffix}`;
  const disclosureCode = `PH2-DISC-${suffix}`;
  const itemCode = `PH2-ITEM-${suffix}`;
  const itemName = `Phase 2 Requirement ${suffix}`;
  const elementCode = `PH2-ELEM-${suffix}`;
  const elementName = `Phase 2 Shared Element ${suffix}`;
  const apiUrl = demoState.api_url!.replace("localhost", "127.0.0.1");
  const adminAuth = await loginByApi(request, demoState.users.admin.email, demoState.password);

  const standard = await apiPost<{ id: number }>(request, `${apiUrl}/standards`, adminAuth.headers, {
    code: standardCode,
    name: `Phase 2 Standard ${suffix}`,
    version: "2026",
  });
  const section = await apiPost<{ id: number }>(request, `${apiUrl}/standards/${standard.id}/sections`, adminAuth.headers, {
    code: `PH2-SEC-${suffix}`,
    title: `Phase 2 Section ${suffix}`,
  });
  const disclosure = await apiPost<{ id: number }>(request, `${apiUrl}/standards/${standard.id}/disclosures`, adminAuth.headers, {
    section_id: section.id,
    code: disclosureCode,
    title: `Phase 2 Disclosure ${suffix}`,
    requirement_type: "quantitative",
    mandatory_level: "mandatory",
  });
  const item = await apiPost<{ id: number }>(request, `${apiUrl}/disclosures/${disclosure.id}/items`, adminAuth.headers, {
    item_code: itemCode,
    name: itemName,
    item_type: "metric",
    value_type: "number",
    unit_code: "MWH",
    is_required: true,
  });
  const element = await apiPost<{ id: number }>(request, `${apiUrl}/shared-elements`, adminAuth.headers, {
    code: elementCode,
    name: elementName,
    description: "Phase 2 role journey element",
    concept_domain: "energy",
    default_value_type: "number",
    default_unit_code: "MWH",
  });
  await apiPost(request, `${apiUrl}/mappings`, adminAuth.headers, {
    requirement_item_id: item.id,
    shared_element_id: element.id,
    mapping_type: "full",
  });

  const adminSession = await openRolePage(browser, demoState.users.admin.email);
  try {
    const page = adminSession.page;

    await page.goto("/settings/shared-elements");
    await expect(page.getByRole("heading", { name: "Shared Elements & Mappings" })).toBeVisible();
    const elementRow = page.getByRole("row", { name: new RegExp(elementCode) }).first();
    await expect(elementRow).toBeVisible();
    await expect(elementRow).toContainText("1");

    await page.goto("/settings/assignments");
    await expect(page.getByRole("heading", { name: "Assignments" })).toBeVisible();
    await page.getByRole("button", { name: "Add Assignment" }).click();
    await page.getByLabel("Element Code").fill(elementCode);
    await page.getByLabel("Element Name").fill(elementName);
    await page.getByLabel("Entity").selectOption(String(demoState.entities!.generation.id));
    await page.getByLabel("Collector").selectOption(String(demoState.users.collector_energy.id));
    await page.getByLabel("Reviewer").selectOption(String(demoState.users.reviewer.id));
    await page.getByLabel("Deadline").fill("2026-12-31");
    await page.getByRole("button", { name: "Create Assignment" }).click();
    await expect(page.getByText(elementCode, { exact: true })).toBeVisible();
  } finally {
    await adminSession.context.close();
  }

  const collectorSession = await openRolePage(browser, demoState.users.collector_energy.email);
  try {
    const page = collectorSession.page;
    await page.goto("/collection");
    await page.getByPlaceholder("Search by code or name...").fill(elementCode);
    const row = collectionRow(page, elementCode);
    await expect(row).toBeVisible();
    await expect(row).toContainText(elementName);
    await expect(row.getByRole("button", { name: "Enter Data" })).toBeVisible();
  } finally {
    await collectorSession.context.close();
  }
});

test("platform admin manages a tenant and updates organization auth policy", async ({ browser }) => {
  const suffix = `${Date.now()}`;
  const tenantName = `Phase 2 Tenant ${suffix}`;
  const updatedTenantName = `${tenantName} Updated`;

  const adminSession = await openRolePage(browser, demoState.users.admin.email);
  try {
    const page = adminSession.page;

    await page.goto("/platform/tenants");
    await expect(page.getByRole("heading", { name: "Tenants" })).toBeVisible();
    await page.getByRole("link", { name: "Create Tenant" }).click();
    await expect(page.getByRole("heading", { name: "Create Tenant" })).toBeVisible();
    await page.getByLabel("Name").fill(tenantName);
    await page.getByLabel("Country").fill("United Kingdom");
    await page.getByLabel("Industry").fill("Infrastructure");
    await page.getByRole("button", { name: "Create Tenant" }).click();

    await expect(page).toHaveURL(/\/platform\/tenants\/\d+$/);
    await expect(page.getByRole("heading", { name: "Tenant Details" })).toBeVisible();
    await page.getByLabel("Name").fill(updatedTenantName);
    await page.getByLabel("Country").fill("Germany");
    await page.getByLabel("Industry").fill("Energy Services");
    await page.getByRole("button", { name: "Save Changes" }).click();
    await expect(page.getByText("Tenant settings saved.")).toBeVisible();

    await page.getByLabel("Lifecycle Status").selectOption("suspended");
    await page.getByRole("button", { name: "Apply Status" }).click();
    await expect(page.getByText("Tenant moved to suspended.")).toBeVisible();

    await page.getByLabel("Lifecycle Status").selectOption("active");
    await page.getByRole("button", { name: "Apply Status" }).click();
    await expect(page.getByText("Tenant moved to active.")).toBeVisible();

    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Organization Settings" })).toBeVisible();

    const allowSso = page.getByRole("switch", { name: "Allow SSO login" });
    const originalAllowSso = (await allowSso.getAttribute("aria-checked")) ?? "true";
    const toggledAllowSso = originalAllowSso === "true" ? "false" : "true";

    await allowSso.click();
    await page.getByRole("button", { name: "Save Auth Policy" }).click();
    await expect(page.getByText("Authentication policy saved.")).toBeVisible();
    await expect(allowSso).toHaveAttribute("aria-checked", toggledAllowSso);

    await allowSso.click();
    await page.getByRole("button", { name: "Save Auth Policy" }).click();
    await expect(page.getByText("Authentication policy saved.")).toBeVisible();
    await expect(allowSso).toHaveAttribute("aria-checked", originalAllowSso);
  } finally {
    await adminSession.context.close();
  }
});

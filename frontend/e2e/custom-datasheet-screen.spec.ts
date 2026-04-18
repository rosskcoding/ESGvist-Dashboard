import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import {
  apiPost,
  createJourneyAssignment,
  loadDemoState,
  loginByApi,
  loginThroughUi,
} from "./screen-helpers";

const demoState = loadDemoState();
const projectId = demoState.project.id;
const apiUrl = demoState.api_url!.replace("localhost", "127.0.0.1");

type CustomDatasheetResponse = {
  id: number;
  name: string;
  description?: string | null;
};

type CustomDatasheetItemResponse = {
  id: number;
  shared_element_id: number;
};

type EvidenceResponse = {
  id: number;
  title: string;
};

type DataPointResponse = {
  id: number;
};

type CreatedCustomDatasheetScenario = {
  datasheetId: number;
  datasheetName: string;
  metricCode: string;
  metricName: string;
};

type MixedDatasheetScenario = {
  datasheetId: number;
  datasheetName: string;
  frameworkMetricCode: string;
  frameworkMetricName: string;
  customPrimaryCode: string;
  customPrimaryName: string;
  customSecondaryCode: string;
  customSecondaryName: string;
  evidenceId: number;
  evidenceTitle: string;
};

function metricCard(page: Page, metricName: string) {
  return page
    .locator("div.rounded-2xl.border.border-slate-200.bg-white")
    .filter({ has: page.getByText(metricName, { exact: false }) })
    .first();
}

function selectedDatasheetHeader(page: Page, datasheetName: string) {
  return page
    .locator("div")
    .filter({ has: page.getByText(datasheetName, { exact: true }) })
    .filter({ has: page.getByRole("button", { name: "Add item" }) })
    .filter({ has: page.getByRole("button", { name: "Archive" }) })
    .first();
}

async function openCustomDatasheetSettings(page: Page) {
  await page.goto(`/projects/${projectId}/settings?tab=custom-datasheet`);
  const runtimeErrorHeading = page.getByRole("heading", { name: "This page couldn’t load" });
  if (await runtimeErrorHeading.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await page.reload();
  }
  await expect(page.getByRole("tab", { name: "Custom Datasheet" })).toBeVisible();
  await expect(page.getByText("Custom Datasheets")).toBeVisible();
}

async function expectSelectedDatasheetId(page: Page) {
  await expect
    .poll(() => new URL(page.url()).searchParams.get("datasheetId"), {
      message: "custom datasheet id should be present in the URL",
      timeout: 15_000,
    })
    .toBeTruthy();
  return Number(new URL(page.url()).searchParams.get("datasheetId"));
}

async function createCustomDatasheetWithCustomMetric(
  page: Page,
  suffix: number,
): Promise<CreatedCustomDatasheetScenario> {
  const datasheetName = `PW Custom Datasheet ${suffix}`;
  const metricCode = `CUST-PW-${suffix}`;
  const metricName = `Female representation on board ${suffix}`;

  await openCustomDatasheetSettings(page);

  await page.getByRole("button", { name: "Create", exact: true }).click();
  const createDialog = page.getByRole("dialog");
  await createDialog.getByLabel("Name").fill(datasheetName);
  await createDialog
    .getByLabel("Description")
    .fill("Playwright scenario for creating and using a custom datasheet.");
  await createDialog.getByRole("button", { name: "Create datasheet" }).click();

  await expect(createDialog).toHaveCount(0);
  const datasheetId = await expectSelectedDatasheetId(page);
  await page.goto(`/projects/${projectId}/settings?tab=custom-datasheet&datasheetId=${datasheetId}`);
  await expect(selectedDatasheetHeader(page, datasheetName)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Add item" })).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "Add item" }).click();
  const addDialog = page.getByRole("dialog");
  await addDialog.getByRole("button", { name: "Create new custom" }).click();
  await addDialog.getByLabel("Metric code").fill(metricCode);
  await addDialog.getByLabel("Metric name").fill(metricName);
  await addDialog.getByLabel("Concept domain").fill("governance");
  await addDialog.getByLabel("Category").selectOption("governance");
  await addDialog.getByLabel("Collection scope").selectOption("entity");
  await addDialog.getByLabel("Entity").selectOption(String(demoState.entities.generation.id));
  await addDialog.getByLabel("Default unit").fill("%");
  await addDialog.getByLabel("Display group").fill("Board composition");
  await addDialog.getByLabel("Collector help text").fill(
    "Capture the current board gender diversity percentage."
  );
  await addDialog.getByRole("button", { name: "Create and add" }).click();

  await expect(addDialog).toHaveCount(0);

  await page.goto(`/projects/${projectId}/settings?tab=custom-datasheet&datasheetId=${datasheetId}`);
  await expect(selectedDatasheetHeader(page, datasheetName)).toBeVisible({ timeout: 15_000 });
  await expect(metricCard(page, metricName)).toBeVisible({
    timeout: 15_000,
  });

  return {
    datasheetId,
    datasheetName,
    metricCode,
    metricName,
  };
}

async function provisionFrameworkEvidenceScenario(
  request: APIRequestContext,
  suffix: string,
) {
  const adminAuth = await loginByApi(request, demoState.users.admin.email, demoState.password);
  const managerAuth = await loginByApi(request, demoState.users.esg_manager.email, demoState.password);
  const collectorAuth = await loginByApi(
    request,
    demoState.users.collector_energy.email,
    demoState.password,
  );
  const journey = await createJourneyAssignment(request, suffix);

  await apiPost(
    request,
    `${apiUrl}/projects/${projectId}/standards`,
    adminAuth.headers,
    {
      standard_id: journey.standardId,
    },
  );

  const datasheet = await apiPost<CustomDatasheetResponse>(
    request,
    `${apiUrl}/projects/${projectId}/custom-datasheets`,
    managerAuth.headers,
    {
      name: `PW Framework Datasheet ${suffix}`,
      description: "Framework-backed evidence navigation scenario",
    },
  );

  await apiPost<CustomDatasheetItemResponse>(
    request,
    `${apiUrl}/projects/${projectId}/custom-datasheets/${datasheet.id}/items`,
    managerAuth.headers,
    {
      shared_element_id: journey.sharedElementId,
      source_type: "framework",
      category: "environmental",
      display_group: "Framework evidence",
      collection_scope: "entity",
      entity_id: journey.entityId,
      is_required: true,
      sort_order: 10,
    },
  );

  const dataPoint = await apiPost<DataPointResponse>(
    request,
    `${apiUrl}/projects/${projectId}/data-points`,
    collectorAuth.headers,
    {
      shared_element_id: journey.sharedElementId,
      entity_id: journey.entityId,
      numeric_value: 88.4,
      unit_code: "MWH",
    },
  );

  await apiPost(
    request,
    `${apiUrl}/projects/${projectId}/bindings`,
    collectorAuth.headers,
    {
      requirement_item_id: journey.itemId,
      data_point_id: dataPoint.id,
    },
  );

  const evidence = await apiPost<EvidenceResponse>(
    request,
    `${apiUrl}/evidences`,
    collectorAuth.headers,
    {
      type: "file",
      title: `PW Datasheet Evidence ${suffix}`,
      description: "Evidence linked from a framework-backed datasheet item",
      source_type: "manual",
      file_name: `pw-datasheet-evidence-${suffix}.pdf`,
      file_uri: `file:///demo/pw-datasheet-evidence-${suffix}.pdf`,
      mime_type: "application/pdf",
      file_size: 8_192,
    },
  );

  await apiPost(
    request,
    `${apiUrl}/data-points/${dataPoint.id}/evidences`,
    collectorAuth.headers,
    { evidence_id: evidence.id },
  );

  return {
    datasheetId: datasheet.id,
    datasheetName: datasheet.name,
    metricCode: journey.code,
    metricName: journey.name,
    entityName: journey.entityName,
    evidenceId: evidence.id,
    evidenceTitle: evidence.title,
  };
}

async function provisionMixedDatasheetScenario(
  request: APIRequestContext,
  suffix: string,
): Promise<MixedDatasheetScenario> {
  const adminAuth = await loginByApi(request, demoState.users.admin.email, demoState.password);
  const managerAuth = await loginByApi(request, demoState.users.esg_manager.email, demoState.password);
  const collectorAuth = await loginByApi(
    request,
    demoState.users.collector_energy.email,
    demoState.password,
  );
  const journey = await createJourneyAssignment(request, `mix-${suffix}`);

  await apiPost(
    request,
    `${apiUrl}/projects/${projectId}/standards`,
    adminAuth.headers,
    {
      standard_id: journey.standardId,
    },
  );

  const datasheet = await apiPost<CustomDatasheetResponse>(
    request,
    `${apiUrl}/projects/${projectId}/custom-datasheets`,
    managerAuth.headers,
    {
      name: `PW Mixed Datasheet ${suffix}`,
      description: "Mixed framework and custom datasheet scenario",
    },
  );

  await apiPost<CustomDatasheetItemResponse>(
    request,
    `${apiUrl}/projects/${projectId}/custom-datasheets/${datasheet.id}/items`,
    managerAuth.headers,
    {
      shared_element_id: journey.sharedElementId,
      source_type: "framework",
      category: "environmental",
      display_group: "Framework coverage",
      collection_scope: "entity",
      entity_id: journey.entityId,
      is_required: true,
      sort_order: 10,
    },
  );

  const customPrimaryCode = `CUST-MIX-GOV-${suffix}`;
  const customPrimaryName = `Board diversity narrative ${suffix}`;
  await apiPost<CustomDatasheetItemResponse>(
    request,
    `${apiUrl}/projects/${projectId}/custom-datasheets/${datasheet.id}/items/create-custom`,
    managerAuth.headers,
    {
      code: customPrimaryCode,
      name: customPrimaryName,
      concept_domain: "governance",
      default_value_type: "text",
      category: "governance",
      display_group: "Leadership",
      help_text: "Document the governance explanation provided by the client.",
      collection_scope: "entity",
      entity_id: demoState.entities.generation.id,
      is_required: true,
      sort_order: 20,
    },
  );

  const customSecondaryCode = `CUST-MIX-OPS-${suffix}`;
  const customSecondaryName = `Business travel follow-up ${suffix}`;
  await apiPost<CustomDatasheetItemResponse>(
    request,
    `${apiUrl}/projects/${projectId}/custom-datasheets/${datasheet.id}/items/create-custom`,
    managerAuth.headers,
    {
      code: customSecondaryCode,
      name: customSecondaryName,
      concept_domain: "operations",
      default_value_type: "number",
      default_unit_code: "tCO2e",
      category: "business_operations",
      display_group: "Operational notes",
      help_text: "Capture non-framework operational follow-up metrics.",
      collection_scope: "project",
      is_required: false,
      sort_order: 30,
    },
  );

  const dataPoint = await apiPost<DataPointResponse>(
    request,
    `${apiUrl}/projects/${projectId}/data-points`,
    collectorAuth.headers,
    {
      shared_element_id: journey.sharedElementId,
      entity_id: journey.entityId,
      numeric_value: 64.2,
      unit_code: "MWH",
    },
  );

  await apiPost(
    request,
    `${apiUrl}/projects/${projectId}/bindings`,
    collectorAuth.headers,
    {
      requirement_item_id: journey.itemId,
      data_point_id: dataPoint.id,
    },
  );

  const evidence = await apiPost<EvidenceResponse>(
    request,
    `${apiUrl}/evidences`,
    collectorAuth.headers,
    {
      type: "file",
      title: `PW Mixed Evidence ${suffix}`,
      description: "Evidence used to validate custom datasheet relinking",
      source_type: "manual",
      file_name: `pw-mixed-evidence-${suffix}.pdf`,
      file_uri: `file:///demo/pw-mixed-evidence-${suffix}.pdf`,
      mime_type: "application/pdf",
      file_size: 12_288,
    },
  );

  await apiPost(
    request,
    `${apiUrl}/data-points/${dataPoint.id}/evidences`,
    collectorAuth.headers,
    { evidence_id: evidence.id },
  );

  return {
    datasheetId: datasheet.id,
    datasheetName: datasheet.name,
    frameworkMetricCode: journey.code,
    frameworkMetricName: journey.name,
    customPrimaryCode,
    customPrimaryName,
    customSecondaryCode,
    customSecondaryName,
    evidenceId: evidence.id,
    evidenceTitle: evidence.title,
  };
}

test.describe("Screen 12A - Custom Datasheet", () => {
  test("scenario 1: ESG manager creates a custom datasheet, adds a custom metric, and continues in collection", async ({
    page,
  }) => {
    const suffix = Date.now();

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    const scenario = await createCustomDatasheetWithCustomMetric(page, suffix);

    const customMetricCard = metricCard(page, scenario.metricName);
    await expect(customMetricCard).toBeVisible();
    await customMetricCard
      .getByRole("button", { name: /Create in Collection|Open in Collection/ })
      .click();

    await expect(page).toHaveURL(new RegExp(`/collection/\\d+\\?projectId=${projectId}`), {
      timeout: 15_000,
    });
    await expect(page.getByRole("button", { name: "Back to Custom Datasheet" })).toBeVisible();
    await page.getByRole("button", { name: "Back to Custom Datasheet" }).click();

    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/settings\\?.*tab=custom-datasheet`), {
      timeout: 15_000,
    });
    await page.goto(`/projects/${projectId}/settings?tab=custom-datasheet&datasheetId=${scenario.datasheetId}`);
    await expect(page.getByText(scenario.datasheetName, { exact: true }).first()).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Create in Collection|Open in Collection/ }).first()
    ).toBeVisible();
  });

  test("scenario 2: ESG manager reviews linked evidence for a framework metric and jumps to the repository", async ({
    page,
    request,
  }) => {
    const suffix = `datasheet-evidence-${Date.now()}`;
    const scenario = await provisionFrameworkEvidenceScenario(request, suffix);

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto(
      `/projects/${projectId}/settings?tab=custom-datasheet&datasheetId=${scenario.datasheetId}`
    );

    await expect(page.getByText(scenario.datasheetName, { exact: true }).first()).toBeVisible();

    const frameworkMetricCard = metricCard(page, scenario.metricName);
    await expect(frameworkMetricCard).toBeVisible();
    await expect(frameworkMetricCard.getByText(scenario.metricCode, { exact: false })).toBeVisible();
    await expect(frameworkMetricCard.getByText("1 evidence item", { exact: true })).toBeVisible({
      timeout: 15_000,
    });

    await frameworkMetricCard.getByRole("button", { name: "View evidence" }).click();

    const evidenceDialog = page.getByRole("dialog");
    await expect(evidenceDialog.getByRole("heading", { name: "Linked Evidence" })).toBeVisible();
    await expect(evidenceDialog.getByText(scenario.evidenceTitle, { exact: true })).toBeVisible();
    await expect(evidenceDialog.getByText("Data point status:", { exact: false })).toBeVisible();
    await evidenceDialog.getByRole("button", { name: "Open in Repository" }).click();

    await expect(page).toHaveURL(new RegExp(`/evidence\\?.*evidenceId=${scenario.evidenceId}`), {
      timeout: 15_000,
    });
    await expect(page.getByRole("heading", { name: "Evidence Repository" })).toBeVisible();
    await expect(page.getByRole("heading", { name: scenario.evidenceTitle })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("Linked Metrics (Data Points)", { exact: true })).toBeVisible();
    await expect(page.getByText(scenario.metricCode, { exact: true })).toBeVisible();
  });

  test("scenario 3: ESG manager attaches evidence in collection and returns to the custom datasheet", async ({
    page,
  }) => {
    const suffix = Date.now();
    const evidenceFileName = `pw-custom-datasheet-evidence-${suffix}.json`;

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    const scenario = await createCustomDatasheetWithCustomMetric(page, suffix);

    const customMetricCard = metricCard(page, scenario.metricName);
    await expect(customMetricCard).toBeVisible();
    await customMetricCard
      .getByRole("button", { name: /Create in Collection|Open in Collection/ })
      .click();

    await expect(page).toHaveURL(new RegExp(`/collection/\\d+\\?projectId=${projectId}`), {
      timeout: 15_000,
    });
    await expect(page.getByRole("button", { name: "Back to Custom Datasheet" })).toBeVisible();

    await page.getByRole("button", { name: /^Next/ }).click();
    await expect(page.getByLabel("Value")).toBeVisible();
    await expect(page.getByLabel("Unit")).toBeVisible();

    await page.getByLabel("Value").fill("46");
    const firstAvailableUnit = await page
      .getByLabel("Unit")
      .locator("option")
      .evaluateAll((options) => {
        const first = options.find((option) => option.getAttribute("value"));
        return first?.getAttribute("value") ?? null;
      });
    expect(firstAvailableUnit).toBeTruthy();
    await page.getByLabel("Unit").selectOption(firstAvailableUnit!);
    const firstAvailableMethodology = await page
      .getByLabel("Methodology")
      .locator("option")
      .evaluateAll((options) => {
        const first = options.find((option) => option.getAttribute("value"));
        return first?.getAttribute("value") ?? null;
      });
    if (firstAvailableMethodology) {
      await page.getByLabel("Methodology").selectOption(firstAvailableMethodology);
    }
    await page.locator('input[type="file"]').setInputFiles({
      name: evidenceFileName,
      mimeType: "application/json",
      buffer: Buffer.from(
        JSON.stringify({
          source: "playwright",
          metric: scenario.metricCode,
          note: "Evidence uploaded from the custom datasheet collection flow.",
        })
      ),
    });
    await expect(page.getByText(evidenceFileName, { exact: true })).toBeVisible();

    await page.getByRole("button", { name: /^Next/ }).click();
    await expect(page.getByText("Preview & Gate Check", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Data Summary" })).toBeVisible();
    await expect(page.getByText("1 file(s) attached", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Run Gate Check" }).click();
    await expect(page.getByText("Gate Check Results", { exact: true })).toBeVisible({
      timeout: 20_000,
    });

    await page.getByRole("button", { name: "Back to Custom Datasheet" }).click();

    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/settings\\?.*tab=custom-datasheet`), {
      timeout: 15_000,
    });
    await page.goto(`/projects/${projectId}/settings?tab=custom-datasheet&datasheetId=${scenario.datasheetId}`);
    await expect(page.getByText(scenario.datasheetName, { exact: true }).first()).toBeVisible();

    const updatedMetricCard = metricCard(page, scenario.metricName);
    await expect(updatedMetricCard).toBeVisible();
    await expect(updatedMetricCard.getByText("1 evidence item", { exact: true })).toBeVisible({
      timeout: 15_000,
    });

    await updatedMetricCard.getByRole("button", { name: "View evidence" }).click();
    const evidenceDialog = page.getByRole("dialog");
    await expect(evidenceDialog.getByRole("heading", { name: "Linked Evidence" })).toBeVisible();
    await expect(evidenceDialog.getByText(evidenceFileName, { exact: true }).first()).toBeVisible();
    await expect(evidenceDialog.getByText("Data point status:", { exact: false })).toBeVisible();
  });

  test("scenario 4: ESG manager reviews a mixed datasheet with framework and multiple custom metrics", async ({
    page,
    request,
  }) => {
    const suffix = `mixed-${Date.now()}`;
    const scenario = await provisionMixedDatasheetScenario(request, suffix);

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto(
      `/projects/${projectId}/settings?tab=custom-datasheet&datasheetId=${scenario.datasheetId}`
    );

    await expect(page.getByText(scenario.datasheetName, { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Total items")).toBeVisible();
    await expect(page.getByText("3").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Environmental" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Governance" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Business / Operations" })).toBeVisible();

    const frameworkCard = metricCard(page, scenario.frameworkMetricName);
    await expect(frameworkCard).toBeVisible();
    await expect(frameworkCard.getByText("Framework metric", { exact: true })).toBeVisible();
    await expect(frameworkCard.getByText("1 evidence item", { exact: true })).toBeVisible();

    const primaryCustomCard = metricCard(page, scenario.customPrimaryName);
    await expect(primaryCustomCard).toBeVisible();
    await expect(primaryCustomCard.getByText("Custom metric", { exact: true })).toBeVisible();
    await expect(primaryCustomCard.getByRole("button", { name: /Create in Collection/ })).toBeVisible();

    const secondaryCustomCard = metricCard(page, scenario.customSecondaryName);
    await expect(secondaryCustomCard).toBeVisible();
    await expect(secondaryCustomCard.getByText("Custom metric", { exact: true })).toBeVisible();
    await expect(secondaryCustomCard.getByRole("button", { name: /Create in Collection/ })).toBeVisible();
  });

  test("scenario 5: ESG manager re-links evidence from a framework metric to a custom metric", async ({
    page,
    request,
  }) => {
    const suffix = `relink-${Date.now()}`;
    const scenario = await provisionMixedDatasheetScenario(request, suffix);

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto(
      `/projects/${projectId}/settings?tab=custom-datasheet&datasheetId=${scenario.datasheetId}`
    );

    const frameworkCard = metricCard(page, scenario.frameworkMetricName);
    await expect(frameworkCard).toBeVisible();
    await frameworkCard.getByRole("button", { name: "View evidence" }).click();

    const evidenceDialog = page.getByRole("dialog");
    await expect(evidenceDialog.getByRole("heading", { name: "Linked Evidence" })).toBeVisible();
    await evidenceDialog.getByRole("button", { name: "Open in Repository" }).click();

    await expect(page).toHaveURL(new RegExp(`/evidence\\?.*evidenceId=${scenario.evidenceId}`), {
      timeout: 15_000,
    });
    await expect(page.getByRole("heading", { name: scenario.evidenceTitle })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(scenario.frameworkMetricCode, { exact: false })).toBeVisible();

    await page.getByRole("button", { name: "Unlink" }).first().click();
    await expect(
      page.getByText("This evidence is uploaded, but it is not linked to any metric or data point yet.")
    ).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Link this evidence" }).click();
    await page.getByLabel("Search metric or data point").fill(scenario.customPrimaryCode);
    await expect(page.getByText(scenario.customPrimaryName, { exact: false })).toBeVisible({
      timeout: 15_000,
    });
    await page
      .getByRole("button", {
        name: new RegExp(
          `${scenario.customPrimaryName}.*${scenario.customPrimaryCode}.*${demoState.entities.generation.name}`,
        ),
      })
      .click();

    await expect(page.getByText("1 linked data point contexts", { exact: true })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(scenario.customPrimaryCode, { exact: false })).toBeVisible();

    await page.goto(
      `/projects/${projectId}/settings?tab=custom-datasheet&datasheetId=${scenario.datasheetId}`
    );

    const updatedFrameworkCard = metricCard(page, scenario.frameworkMetricName);
    await expect(updatedFrameworkCard).toBeVisible();
    await expect(updatedFrameworkCard.getByText("No evidence yet", { exact: true })).toBeVisible({
      timeout: 15_000,
    });

    const updatedCustomCard = metricCard(page, scenario.customPrimaryName);
    await expect(updatedCustomCard).toBeVisible();
    await expect(updatedCustomCard.getByText("1 evidence item", { exact: true })).toBeVisible({
      timeout: 15_000,
    });
  });
});

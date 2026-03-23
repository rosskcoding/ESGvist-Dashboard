import fs from "node:fs";
import path from "node:path";

import { expect, test, type APIRequestContext } from "@playwright/test";

type DemoState = {
  api_url: string;
  password: string;
  organization: { id: number; name: string };
  project: { id: number; name: string; reporting_year: number };
  users: Record<string, { id: number; email: string; full_name: string; role: string }>;
  entities: Record<string, { id: number; name: string }>;
  shared_elements: Record<string, { id: number; code: string }>;
  standards: {
    gri: { disclosures: { gri_302_1: { items: { energy_total_mwh: number } }; gri_305_1: { items: { scope1_tco2e: number } } } };
    ifrs_s1: { disclosures: { gov_1: { items: { governance_narrative: number } } } };
    ifrs_s2: { disclosures: { met_4: { items: { scope1_tco2e: number; scope2_tco2e: number } } } };
    esrs: { disclosures: { e1_6: { items: { scope1_tco2e: number; scope2_tco2e: number } } } };
  };
};

type RuntimeState = {
  customStandardId?: number;
  customDisclosureId?: number;
  customItemId?: number;
  customSharedElementId?: number;
  customAssignmentId?: number;
  energyDataPointId?: number;
  scope1DataPointId?: number;
  scope2DataPointId?: number;
  governanceDataPointId?: number;
  customDataPointId?: number;
};

const rootDir = path.resolve(__dirname, "..", "..");
const artifactsDir = path.join(rootDir, "artifacts", "demo");
const statePath = path.join(artifactsDir, "demo-state.json");
const runtimePath = path.join(artifactsDir, "runtime-state.json");
const apiArtifactsDir = path.join(artifactsDir, "api-artifacts");

function ensureArtifacts() {
  fs.mkdirSync(artifactsDir, { recursive: true });
  fs.mkdirSync(apiArtifactsDir, { recursive: true });
}

function loadState(): DemoState {
  const state = JSON.parse(fs.readFileSync(statePath, "utf-8")) as DemoState;
  state.api_url = state.api_url.replace("localhost", "127.0.0.1");
  return state;
}

function saveRuntime(runtime: RuntimeState) {
  fs.writeFileSync(runtimePath, JSON.stringify(runtime, null, 2));
}

function saveArtifact(name: string, data: unknown) {
  fs.writeFileSync(path.join(apiArtifactsDir, name), JSON.stringify(data, null, 2));
}

async function assertOk(response: Awaited<ReturnType<APIRequestContext["get"]>>) {
  const bodyText = await response.text();
  expect(response.ok(), bodyText).toBeTruthy();
  return bodyText ? JSON.parse(bodyText) : null;
}

async function loginByApi(request: APIRequestContext, state: DemoState, userKey: keyof DemoState["users"]) {
  const user = state.users[userKey];
  const response = await request.post(`${state.api_url}/auth/login`, {
    data: { email: user.email, password: state.password },
  });
  const body = await assertOk(response);
  return {
    user,
    headers: {
      Authorization: `Bearer ${body.access_token}`,
      "X-Organization-Id": String(state.organization.id),
    },
  };
}

async function apiPost(
  request: APIRequestContext,
  url: string,
  headers: Record<string, string>,
  data?: unknown,
) {
  return assertOk(await request.post(url, { headers, data }));
}

async function apiGet(
  request: APIRequestContext,
  url: string,
  headers: Record<string, string>,
) {
  return assertOk(await request.get(url, { headers }));
}

test.describe.configure({ mode: "serial" });

const runtime: RuntimeState = {};

test("admin provisions custom disclosure and assignment", async ({ request }) => {
  ensureArtifacts();
  const state = loadState();

  const admin = await loginByApi(request, state, "admin");
  const customStandard = await apiPost(request, `${state.api_url}/standards`, admin.headers, {
    code: "NW-CUSTOM",
    name: "Northwind Custom Reporting Standard",
    version: "2025.1",
    jurisdiction: "UK",
  });
  runtime.customStandardId = customStandard.id;

  const section = await apiPost(
    request,
    `${state.api_url}/standards/${customStandard.id}/sections`,
    admin.headers,
    {
      code: "BIO",
      title: "Biodiversity and Water Stress",
      sort_order: 10,
    },
  );
  const disclosure = await apiPost(
    request,
    `${state.api_url}/standards/${customStandard.id}/disclosures`,
    admin.headers,
    {
      section_id: section.id,
      code: "NW-BIO-01",
      title: "Sites in high water stress areas",
      description: "Custom Northwind biodiversity pilot disclosure",
      requirement_type: "quantitative",
      mandatory_level: "mandatory",
      sort_order: 10,
    },
  );
  runtime.customDisclosureId = disclosure.id;

  const item = await apiPost(
    request,
    `${state.api_url}/disclosures/${disclosure.id}/items`,
    admin.headers,
    {
      item_code: "WATER_STRESS_SITES_COUNT",
      name: "Sites in water stress areas",
      description: "Count of operational sites located in high water stress basins",
      item_type: "metric",
      value_type: "number",
      unit_code: "COUNT",
      is_required: true,
      requires_evidence: true,
      sort_order: 10,
    },
  );
  runtime.customItemId = item.id;

  const element = await apiPost(request, `${state.api_url}/shared-elements`, admin.headers, {
    code: "WATER_STRESS_SITES_COUNT",
    name: "Sites in Water Stress Areas",
    description: "Operational sites located in high water stress areas",
    concept_domain: "water",
    default_value_type: "number",
    default_unit_code: "COUNT",
  });
  runtime.customSharedElementId = element.id;

  const mapping = await apiPost(request, `${state.api_url}/mappings`, admin.headers, {
    requirement_item_id: item.id,
    shared_element_id: element.id,
    mapping_type: "full",
  });

  const assignment = await apiPost(
    request,
    `${state.api_url}/projects/${state.project.id}/assignments`,
    admin.headers,
    {
      shared_element_id: element.id,
      entity_id: state.entities.hamburg.id,
      collector_id: state.users.collector_climate.id,
      reviewer_id: state.users.reviewer.id,
      backup_collector_id: state.users.esg_manager.id,
      deadline: "2026-04-18",
      escalation_after_days: 3,
    },
  );
  runtime.customAssignmentId = assignment.id;
  saveRuntime(runtime);
  saveArtifact("01-admin-provisioning.json", {
    customStandard,
    section,
    disclosure,
    item,
    element,
    mapping,
    assignment,
  });
});

test("collectors and manager submit GRI, IFRS and ESRS data", async ({ request }) => {
  const state = loadState();
  Object.assign(runtime, JSON.parse(fs.readFileSync(runtimePath, "utf-8")) as RuntimeState);

  const collectorEnergy = await loginByApi(request, state, "collector_energy");
  const energyEvidence = await apiPost(request, `${state.api_url}/evidences`, collectorEnergy.headers, {
    type: "file",
    title: "FY2025 Energy Ledger Extract",
    description: "Consolidated utility ledger export for UK generation entity",
    source_type: "manual",
    file_name: "energy-ledger-fy2025.pdf",
    file_uri: "file:///demo/energy-ledger-fy2025.pdf",
    mime_type: "application/pdf",
    file_size: 1024 * 1024,
  });
  const energyPoint = await apiPost(
    request,
    `${state.api_url}/projects/${state.project.id}/data-points`,
    collectorEnergy.headers,
    {
      shared_element_id: state.shared_elements.energy_total_mwh.id,
      entity_id: state.entities.generation.id,
      numeric_value: 128450.4,
      unit_code: "MWH",
    },
  );
  runtime.energyDataPointId = energyPoint.id;
  await apiPost(
    request,
    `${state.api_url}/projects/${state.project.id}/bindings`,
    collectorEnergy.headers,
    {
      requirement_item_id: state.standards.gri.disclosures.gri_302_1.items.energy_total_mwh,
      data_point_id: energyPoint.id,
    },
  );
  await apiPost(
    request,
    `${state.api_url}/data-points/${energyPoint.id}/evidences`,
    collectorEnergy.headers,
    { evidence_id: energyEvidence.id },
  );
  const energyGate = await apiPost(
    request,
    `${state.api_url}/gate-check`,
    collectorEnergy.headers,
    { action: "submit_data_point", data_point_id: energyPoint.id },
  );
  expect(energyGate.allowed).toBeTruthy();
  const energySubmit = await apiPost(
    request,
    `${state.api_url}/data-points/${energyPoint.id}/submit`,
    collectorEnergy.headers,
  );

  const collectorClimate = await loginByApi(request, state, "collector_climate");
  const climateEvidence = await apiPost(request, `${state.api_url}/evidences`, collectorClimate.headers, {
    type: "file",
    title: "Hamburg Wind Farm emissions workbook",
    description: "Metered combustion and purchased electricity workbook",
    source_type: "manual",
    file_name: "hamburg-emissions-fy2025.xlsx",
    file_uri: "file:///demo/hamburg-emissions-fy2025.xlsx",
    mime_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    file_size: 512 * 1024,
  });
  const scope1Point = await apiPost(
    request,
    `${state.api_url}/projects/${state.project.id}/data-points`,
    collectorClimate.headers,
    {
      shared_element_id: state.shared_elements.scope1_tco2e.id,
      entity_id: state.entities.grid.id,
      facility_id: state.entities.hamburg.id,
      numeric_value: 5421.7,
      unit_code: "TCO2E",
    },
  );
  runtime.scope1DataPointId = scope1Point.id;
  for (const requirementItemId of [
    state.standards.gri.disclosures.gri_305_1.items.scope1_tco2e,
    state.standards.ifrs_s2.disclosures.met_4.items.scope1_tco2e,
    state.standards.esrs.disclosures.e1_6.items.scope1_tco2e,
  ]) {
    await apiPost(
      request,
      `${state.api_url}/projects/${state.project.id}/bindings`,
      collectorClimate.headers,
      { requirement_item_id: requirementItemId, data_point_id: scope1Point.id },
    );
  }
  await apiPost(
    request,
    `${state.api_url}/data-points/${scope1Point.id}/evidences`,
    collectorClimate.headers,
    { evidence_id: climateEvidence.id },
  );
  const scope1Submit = await apiPost(
    request,
    `${state.api_url}/data-points/${scope1Point.id}/submit`,
    collectorClimate.headers,
  );

  const scope2Point = await apiPost(
    request,
    `${state.api_url}/projects/${state.project.id}/data-points`,
    collectorClimate.headers,
    {
      shared_element_id: state.shared_elements.scope2_tco2e.id,
      entity_id: state.entities.grid.id,
      numeric_value: 3180.2,
      unit_code: "TCO2E",
    },
  );
  runtime.scope2DataPointId = scope2Point.id;
  for (const requirementItemId of [
    state.standards.ifrs_s2.disclosures.met_4.items.scope2_tco2e,
    state.standards.esrs.disclosures.e1_6.items.scope2_tco2e,
  ]) {
    await apiPost(
      request,
      `${state.api_url}/projects/${state.project.id}/bindings`,
      collectorClimate.headers,
      { requirement_item_id: requirementItemId, data_point_id: scope2Point.id },
    );
  }
  await apiPost(
    request,
    `${state.api_url}/data-points/${scope2Point.id}/evidences`,
    collectorClimate.headers,
    { evidence_id: climateEvidence.id },
  );
  const scope2Submit = await apiPost(
    request,
    `${state.api_url}/data-points/${scope2Point.id}/submit`,
    collectorClimate.headers,
  );

  const customEvidence = await apiPost(request, `${state.api_url}/evidences`, collectorClimate.headers, {
    type: "file",
    title: "Water stress site screening memo",
    description: "Manual site screening memo for biodiversity pilot",
    source_type: "manual",
    file_name: "water-stress-screening.pdf",
    file_uri: "file:///demo/water-stress-screening.pdf",
    mime_type: "application/pdf",
    file_size: 256 * 1024,
  });
  const customPoint = await apiPost(
    request,
    `${state.api_url}/projects/${state.project.id}/data-points`,
    collectorClimate.headers,
    {
      shared_element_id: runtime.customSharedElementId,
      entity_id: state.entities.hamburg.id,
      numeric_value: 1,
      unit_code: "COUNT",
    },
  );
  runtime.customDataPointId = customPoint.id;
  await apiPost(
    request,
    `${state.api_url}/projects/${state.project.id}/bindings`,
    collectorClimate.headers,
    { requirement_item_id: runtime.customItemId, data_point_id: customPoint.id },
  );
  await apiPost(
    request,
    `${state.api_url}/data-points/${customPoint.id}/evidences`,
    collectorClimate.headers,
    { evidence_id: customEvidence.id },
  );
  const customSubmit = await apiPost(
    request,
    `${state.api_url}/data-points/${customPoint.id}/submit`,
    collectorClimate.headers,
  );

  const esgManager = await loginByApi(request, state, "esg_manager");
  const governancePoint = await apiPost(
    request,
    `${state.api_url}/projects/${state.project.id}/data-points`,
    esgManager.headers,
    {
      shared_element_id: state.shared_elements.governance_narrative.id,
      text_value:
        "The board sustainability committee reviews climate and broader ESG risks quarterly, while management runs a monthly operating review.",
    },
  );
  runtime.governanceDataPointId = governancePoint.id;
  await apiPost(
    request,
    `${state.api_url}/projects/${state.project.id}/bindings`,
    esgManager.headers,
    {
      requirement_item_id: state.standards.ifrs_s1.disclosures.gov_1.items.governance_narrative,
      data_point_id: governancePoint.id,
    },
  );
  const governanceSubmit = await apiPost(
    request,
    `${state.api_url}/data-points/${governancePoint.id}/submit`,
    esgManager.headers,
  );

  saveRuntime(runtime);
  saveArtifact("02-collector-manager-submissions.json", {
    energyEvidence,
    energyPoint,
    energyGate,
    energySubmit,
    climateEvidence,
    scope1Point,
    scope1Submit,
    scope2Point,
    scope2Submit,
    customEvidence,
    customPoint,
    customSubmit,
    governancePoint,
    governanceSubmit,
  });
});

test("reviewer closes quantitative items and requests revision on narrative", async ({ request }) => {
  const state = loadState();
  Object.assign(runtime, JSON.parse(fs.readFileSync(runtimePath, "utf-8")) as RuntimeState);

  const reviewer = await loginByApi(request, state, "reviewer");
  const approvals = [];
  for (const dataPointId of [
    runtime.energyDataPointId,
    runtime.scope1DataPointId,
    runtime.scope2DataPointId,
    runtime.customDataPointId,
  ]) {
    approvals.push(
      await apiPost(
        request,
        `${state.api_url}/data-points/${dataPointId}/approve`,
        reviewer.headers,
        { comment: "Reviewed and approved for demo run." },
      ),
    );
  }
  const revision = await apiPost(
    request,
    `${state.api_url}/data-points/${runtime.governanceDataPointId}/request-revision`,
    reviewer.headers,
    { comment: "Please add explicit mention of management-level KPI escalation cadence." },
  );
  saveArtifact("03-review-outcomes.json", { approvals, revision });
});

test("auditor verifies completeness and audit trail", async ({ request }) => {
  const state = loadState();
  Object.assign(runtime, JSON.parse(fs.readFileSync(runtimePath, "utf-8")) as RuntimeState);

  const auditor = await loginByApi(request, state, "auditor");
  const completeness = await apiGet(
    request,
    `${state.api_url}/projects/${state.project.id}/completeness?boundaryContext=true`,
    auditor.headers,
  );
  expect(completeness.project_id).toBe(state.project.id);
  expect(completeness.overall_percent).toBeGreaterThan(0);

  const auditLog = await apiGet(
    request,
    `${state.api_url}/audit-log?page=1&page_size=100`,
    auditor.headers,
  );
  const actions = new Set((auditLog.items as Array<{ action: string }>).map((entry) => entry.action));
  expect(actions.has("data_point_submitted")).toBeTruthy();
  expect(actions.has("data_point_approved")).toBeTruthy();
  expect(actions.has("data_point_revision_requested")).toBeTruthy();

  const summary = {
    project_id: state.project.id,
    completeness,
    audit_action_sample: Array.from(actions).sort(),
    runtime,
  };
  saveArtifact("04-auditor-summary.json", summary);
  fs.writeFileSync(path.join(artifactsDir, "final-summary.json"), JSON.stringify(summary, null, 2));
});

import fs from "node:fs";
import path from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

type DemoState = {
  password: string;
  api_url?: string;
  organization: {
    id: number;
    name: string;
  };
  project: {
    id: number;
    name: string;
  };
  shared_elements?: Record<
    string,
    {
      id: number;
      code: string;
    }
  >;
  entities?: Record<
    string,
    {
      id: number;
      name: string;
    }
  >;
  users: Record<
    string,
    {
      id?: number;
      email: string;
      full_name?: string;
      role: string;
    }
  >;
};

const demoStatePath = path.resolve(__dirname, "..", "..", "artifacts", "demo", "demo-state.json");

export function loadDemoState(): DemoState {
  return JSON.parse(fs.readFileSync(demoStatePath, "utf-8")) as DemoState;
}

export async function loginThroughUi(page: Page, email: string, password: string) {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 15_000 });
}

async function assertApiOk(response: Awaited<ReturnType<APIRequestContext["get"]>>) {
  const text = await response.text();
  expect(response.ok(), text).toBeTruthy();
  return text ? JSON.parse(text) : null;
}

export async function loginByApi(
  request: APIRequestContext,
  email: string,
  password: string,
  organizationId = loadDemoState().organization.id,
) {
  const state = loadDemoState();
  const response = await request.post(`${state.api_url!.replace("localhost", "127.0.0.1")}/auth/login`, {
    data: { email, password },
  });
  const body = await assertApiOk(response);
  return {
    headers: {
      Authorization: `Bearer ${body.access_token}`,
      "X-Organization-Id": String(organizationId),
    },
  };
}

export async function apiPost<T>(
  request: APIRequestContext,
  url: string,
  headers: Record<string, string>,
  data?: unknown,
) {
  return assertApiOk(await request.post(url, { headers, data })) as Promise<T>;
}

export async function apiGet<T>(
  request: APIRequestContext,
  url: string,
  headers: Record<string, string>,
) {
  return assertApiOk(await request.get(url, { headers })) as Promise<T>;
}

export async function createJourneyAssignment(
  request: APIRequestContext,
  suffix: string,
  collectorKey: "collector_energy" | "collector_climate" = "collector_energy",
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const adminAuth = await loginByApi(request, state.users.admin.email, state.password);
  const collector = state.users[collectorKey];

  const standard = await apiPost<{ id: number; code: string }>(
    request,
    `${apiUrl}/standards`,
    adminAuth.headers,
    {
      code: `JOURNEY_${suffix}`,
      name: `Journey Validation Standard ${suffix}`,
      version: "2026.1",
      jurisdiction: "UK",
    }
  );

  const section = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/standards/${standard.id}/sections`,
    adminAuth.headers,
    {
      code: `FLOW_${suffix}`,
      title: `Workflow Journey ${suffix}`,
      sort_order: 10,
    }
  );

  const disclosure = await apiPost<{ id: number; code: string }>(
    request,
    `${apiUrl}/standards/${standard.id}/disclosures`,
    adminAuth.headers,
    {
      section_id: section.id,
      code: `JOURNEY_DISC_${suffix}`,
      title: `Journey Disclosure ${suffix}`,
      description: "Scenario-owned disclosure for role journey testing",
      requirement_type: "quantitative",
      mandatory_level: "mandatory",
      sort_order: 10,
    }
  );

  const item = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/disclosures/${disclosure.id}/items`,
    adminAuth.headers,
    {
      item_code: `JOURNEY_ITEM_${suffix}`,
      name: `Journey Review Metric ${suffix}`,
      description: "Scenario-owned metric for reviewer journey testing",
      item_type: "metric",
      value_type: "number",
      unit_code: "MWH",
      is_required: true,
      requires_evidence: true,
      sort_order: 10,
    }
  );

  const sharedElement = await apiPost<{ id: number; code: string; name: string }>(
    request,
    `${apiUrl}/shared-elements`,
    adminAuth.headers,
    {
      code: `JOURNEY_METRIC_${suffix}`,
      name: `Journey Metric ${suffix}`,
      description: "Scenario-owned shared element for screen journey testing",
      concept_domain: "energy",
      default_value_type: "number",
      default_unit_code: "MWH",
    }
  );

  await apiPost(
    request,
    `${apiUrl}/mappings`,
    adminAuth.headers,
    {
      requirement_item_id: item.id,
      shared_element_id: sharedElement.id,
      mapping_type: "full",
    }
  );

  const assignment = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/projects/${state.project.id}/assignments`,
    adminAuth.headers,
    {
      shared_element_id: sharedElement.id,
      entity_id: state.entities!.generation.id,
      collector_id: collector.id,
      reviewer_id: state.users.reviewer.id,
      deadline: "2026-04-30",
      escalation_after_days: 2,
    }
  );

  return {
    standardId: standard.id,
    disclosureId: disclosure.id,
    itemId: item.id,
    sharedElementId: sharedElement.id,
    assignmentId: assignment.id,
    code: sharedElement.code,
    name: sharedElement.name,
    entityId: state.entities!.generation.id,
    entityName: state.entities!.generation.name,
  };
}

export async function createManagerExportJourneyProject(
  request: APIRequestContext,
  suffix: string,
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const adminAuth = await loginByApi(request, state.users.admin.email, state.password);
  const managerAuth = await loginByApi(request, state.users.esg_manager.email, state.password);

  const standard = await apiPost<{ id: number; code: string; name: string }>(
    request,
    `${apiUrl}/standards`,
    adminAuth.headers,
    {
      code: `PMJ_${suffix}`,
      name: `Phase 2 Manager Journey ${suffix}`,
      version: "2026.1",
      jurisdiction: "UK",
    }
  );

  const section = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/standards/${standard.id}/sections`,
    adminAuth.headers,
    {
      code: `PMJSEC_${suffix}`,
      title: `Manager Journey Section ${suffix}`,
      sort_order: 10,
    }
  );

  const disclosure = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/standards/${standard.id}/disclosures`,
    adminAuth.headers,
    {
      section_id: section.id,
      code: `PMJDISC_${suffix}`,
      title: `Manager Journey Disclosure ${suffix}`,
      description: "Scenario-owned disclosure for manager readiness/export journey",
      requirement_type: "quantitative",
      mandatory_level: "mandatory",
      sort_order: 10,
    }
  );

  const item = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/disclosures/${disclosure.id}/items`,
    adminAuth.headers,
    {
      item_code: `PMJITEM_${suffix}`,
      name: `Manager Journey Metric ${suffix}`,
      description: "Scenario-owned metric for manager readiness/export flow",
      item_type: "metric",
      value_type: "number",
      unit_code: "MWH",
      is_required: true,
      requires_evidence: false,
      sort_order: 10,
    }
  );

  const sharedElement = await apiPost<{ id: number; code: string; name: string }>(
    request,
    `${apiUrl}/shared-elements`,
    adminAuth.headers,
    {
      code: `PMJ_METRIC_${suffix}`,
      name: `Manager Report Metric ${suffix}`,
      description: "Scenario-owned shared element for manager readiness/export flow",
      concept_domain: "energy",
      default_value_type: "number",
      default_unit_code: "MWH",
    }
  );

  await apiPost(
    request,
    `${apiUrl}/mappings`,
    adminAuth.headers,
    {
      requirement_item_id: item.id,
      shared_element_id: sharedElement.id,
      mapping_type: "full",
    }
  );

  const project = await apiPost<{ id: number; name: string; status: string }>(
    request,
    `${apiUrl}/projects`,
    managerAuth.headers,
    {
      name: `Manager Report Journey ${suffix}`,
      reporting_year: 2025,
    }
  );

  await apiPost(
    request,
    `${apiUrl}/projects/${project.id}/assignments`,
    managerAuth.headers,
    {
      shared_element_id: sharedElement.id,
      entity_id: state.entities!.generation.id,
      collector_id: state.users.esg_manager.id,
      reviewer_id: state.users.reviewer.id,
      deadline: "2026-04-30",
    }
  );

  return {
    projectId: project.id,
    projectName: project.name,
    standardId: standard.id,
    standardCode: standard.code,
    itemId: item.id,
    sharedElementId: sharedElement.id,
    sharedElementCode: sharedElement.code,
    entityId: state.entities!.generation.id,
    entityName: state.entities!.generation.name,
  };
}

export async function makeProjectReadyForExport(
  request: APIRequestContext,
  projectId: number,
  requirementItemId: number,
  sharedElementId: number,
  entityId: number,
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const managerAuth = await loginByApi(request, state.users.esg_manager.email, state.password);
  const reviewerAuth = await loginByApi(request, state.users.reviewer.email, state.password);

  const dataPoint = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/projects/${projectId}/data-points`,
    managerAuth.headers,
    {
      shared_element_id: sharedElementId,
      entity_id: entityId,
      numeric_value: 884.4,
      unit_code: "MWH",
    }
  );

  await apiPost(
    request,
    `${apiUrl}/projects/${projectId}/bindings`,
    managerAuth.headers,
    {
      requirement_item_id: requirementItemId,
      data_point_id: dataPoint.id,
    }
  );

  await apiPost(
    request,
    `${apiUrl}/data-points/${dataPoint.id}/submit`,
    managerAuth.headers
  );

  await apiPost(
    request,
    `${apiUrl}/data-points/${dataPoint.id}/approve`,
    reviewerAuth.headers,
    {
      comment: "Approved for manager export journey.",
    }
  );

  return {
    dataPointId: dataPoint.id,
  };
}

export async function runExportJobs(request: APIRequestContext) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const adminAuth = await loginByApi(request, state.users.admin.email, state.password);
  return apiPost<Record<string, number>>(
    request,
    `${apiUrl}/platform/jobs/exports`,
    adminAuth.headers
  );
}

export async function createReviewReadyItem(
  request: APIRequestContext,
  suffix: string,
  collectorKey: "collector_energy" | "collector_climate" = "collector_energy",
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const adminAuth = await loginByApi(request, state.users.admin.email, state.password);
  const collector = state.users[collectorKey];
  const collectorAuth = await loginByApi(request, collector.email, state.password);
  const code = `RV-${suffix}`;
  const name = `Review Screen Metric ${suffix}`;

  const assignment = await apiPost<{ id: number; shared_element_id: number }>(
    request,
    `${apiUrl}/projects/${state.project.id}/assignments`,
    adminAuth.headers,
    {
      shared_element_code: code,
      shared_element_name: name,
      entity_id: state.entities!.generation.id,
      collector_id: collector.id,
      reviewer_id: state.users.reviewer.id,
    }
  );

  const dataPoint = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/projects/${state.project.id}/data-points`,
    collectorAuth.headers,
    {
      shared_element_id: assignment.shared_element_id,
      entity_id: state.entities!.generation.id,
      numeric_value: 123.45,
      unit_code: "MWH",
    }
  );

  const submitted = await apiPost<{ id: number; status: string }>(
    request,
    `${apiUrl}/data-points/${dataPoint.id}/submit`,
    collectorAuth.headers
  );

  expect(submitted.status).toBe("in_review");

  return {
    id: dataPoint.id,
    code,
    name,
  };
}

import fs from "node:fs";
import path from "node:path";
import { expect, type APIRequestContext, type APIResponse, type Page } from "@playwright/test";

type DemoState = {
  base_url?: string;
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
  boundaries: Record<
    string,
    {
      id: number;
      name: string;
    }
  >;
  shared_elements: Record<
    string,
    {
      id: number;
      code: string;
    }
  >;
  entities: Record<
    string,
    {
      id: number;
      name: string;
    }
  >;
  standards: Record<
    string,
    {
      id: number;
      code: string;
      disclosures?: Record<
        string,
        {
          id: number;
          items?: Record<string, number>;
        }
      >;
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

type OrganizationUsersResponse = {
  users: Array<{
    id: number;
    email: string;
    role: string;
  }>;
};

type RegisteredUserResponse = {
  id: number;
  email: string;
  full_name: string;
};

const demoStatePath = path.resolve(__dirname, "..", "..", "artifacts", "demo", "demo-state.json");

export function loadDemoState(): DemoState {
  return JSON.parse(fs.readFileSync(demoStatePath, "utf-8")) as DemoState;
}

export async function loginThroughUi(
  page: Page,
  email: string,
  password: string,
  expectedUrl: RegExp = /dashboard/,
) {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(expectedUrl, { timeout: 15_000 });
}

type SessionListResponse = {
  items: Array<{
    id: number;
    is_current: boolean;
  }>;
  total: number;
};

type BrowserAuthHeaderOptions = {
  includeCsrf?: boolean;
  includeOrigin?: boolean;
  includeRefresh?: boolean;
};

async function assertApiOk(response: APIResponse) {
  const text = await response.text();
  expect(response.ok(), text).toBeTruthy();
  return text ? JSON.parse(text) : null;
}

async function getRequiredBrowserCookie(page: Page, name: string) {
  const cookies = await page.context().cookies();
  const cookie = cookies.find((entry) => entry.name === name);
  expect(cookie, `${name} cookie must exist`).toBeTruthy();
  return cookie!;
}

export async function browserCookieAuthHeaders(
  page: Page,
  options: BrowserAuthHeaderOptions = {},
) {
  const {
    includeCsrf = true,
    includeOrigin = false,
    includeRefresh = false,
  } = options;
  const accessCookie = await getRequiredBrowserCookie(page, "access_token");
  const cookieParts = [`${accessCookie.name}=${accessCookie.value}`];

  if (includeRefresh) {
    const refreshCookie = await getRequiredBrowserCookie(page, "refresh_token");
    cookieParts.push(`${refreshCookie.name}=${refreshCookie.value}`);
  }

  if (includeCsrf) {
    const csrfCookie = await getRequiredBrowserCookie(page, "csrf_token");
    cookieParts.push(`${csrfCookie.name}=${csrfCookie.value}`);
  }

  const headers: Record<string, string> = {
    Cookie: cookieParts.join("; "),
  };

  if (includeCsrf) {
    const csrfCookie = await getRequiredBrowserCookie(page, "csrf_token");
    headers["X-CSRF-Token"] = csrfCookie.value;
  }

  if (includeOrigin) {
    headers.Origin = new URL(page.url()).origin;
  }

  return headers;
}

export async function listBrowserSessions(
  page: Page,
  request: APIRequestContext,
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  return (await assertApiOk(
    await request.get(`${apiUrl}/auth/sessions`, {
      headers: await browserCookieAuthHeaders(page, { includeRefresh: true }),
    }),
  )) as SessionListResponse;
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

export async function revokeCurrentBrowserSession(
  page: Page,
  request: APIRequestContext,
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const sessions = await listBrowserSessions(page, request);

  const currentSession = sessions.items.find((item) => item.is_current);
  expect(currentSession, "current auth session must be listed").toBeTruthy();
  await assertApiOk(
    await request.delete(`${apiUrl}/auth/sessions/${currentSession!.id}`, {
      headers: await browserCookieAuthHeaders(page, {
        includeCsrf: true,
        includeOrigin: true,
        includeRefresh: true,
      }),
    }),
  );
}

async function loadOrganizationUsers(request: APIRequestContext) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const adminAuth = await loginByApi(request, state.users.admin.email, state.password);
  const response = await apiGet<OrganizationUsersResponse>(
    request,
    `${apiUrl}/auth/organization/users`,
    adminAuth.headers,
  );
  return new Map(response.users.map((user) => [user.email, user]));
}

async function registerScenarioUser(
  request: APIRequestContext,
  {
    email,
    fullName,
  }: {
    email: string;
    fullName: string;
  },
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const registered = await apiPost<RegisteredUserResponse>(
    request,
    `${apiUrl}/auth/register`,
    {},
    {
      email,
      password: state.password,
      full_name: fullName,
    },
  );
  return {
    id: registered.id,
    email,
    password: state.password,
    fullName,
  };
}

export async function createFrameworkAdminUser(
  request: APIRequestContext,
  suffix: string,
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const platformAuth = await loginByApi(request, state.users.admin.email, state.password);
  const user = await registerScenarioUser(request, {
    email: `framework.${suffix}@example.com`,
    fullName: `Framework ${suffix}`,
  });

  await apiPost(
    request,
    `${apiUrl}/users/${user.id}/roles`,
    platformAuth.headers,
    {
      role: "framework_admin",
      scope_type: "platform",
      scope_id: null,
    },
  );

  return user;
}

export async function createTenantAdminUser(
  request: APIRequestContext,
  suffix: string,
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const platformAuth = await loginByApi(request, state.users.admin.email, state.password);
  const user = await registerScenarioUser(request, {
    email: `tenant.admin.${suffix}@example.com`,
    fullName: `Tenant Admin ${suffix}`,
  });

  await apiPost(
    request,
    `${apiUrl}/platform/tenants/${state.organization.id}/admins`,
    platformAuth.headers,
    {
      user_id: user.id,
    },
  );

  return user;
}

export async function apiPut<T>(
  request: APIRequestContext,
  url: string,
  headers: Record<string, string>,
  data?: unknown,
) {
  return assertApiOk(await request.put(url, { headers, data })) as Promise<T>;
}

type GuidedCollectionConfigField = {
  shared_element_id: number;
  requirement_item_id?: number | null;
  assignment_id?: number | null;
  entity_id?: number | null;
  facility_id?: number | null;
  visible?: boolean;
  required?: boolean;
  help_text?: string | null;
  tooltip?: string | null;
  order?: number;
};

export async function createGuidedCollectionConfig(
  request: APIRequestContext,
  suffix: string,
  fields: GuidedCollectionConfigField[],
  options?: {
    projectId?: number | null;
    name?: string;
    description?: string;
    stepTitle?: string;
  },
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const adminAuth = await loginByApi(request, state.users.admin.email, state.password);
  const hasProjectId = options && Object.prototype.hasOwnProperty.call(options, "projectId");
  const projectId = hasProjectId ? (options?.projectId ?? null) : state.project.id;

  return apiPost<{
    id: number;
    project_id: number | null;
    name: string;
    description: string | null;
    config: { steps: Array<{ id: string; title: string; fields: GuidedCollectionConfigField[] }> };
  }>(
    request,
    `${apiUrl}/form-configs`,
    adminAuth.headers,
    {
      project_id: projectId,
      name: options?.name ?? `PW Guided Config ${suffix}`,
      description: options?.description ?? `Playwright guided collection config ${suffix}`,
      config: {
        steps: [
          {
            id: `pw-guided-${suffix}`,
            title: options?.stepTitle ?? "Guided Entry",
            fields: fields.map((field, index) => ({
              visible: true,
              required: true,
              order: index + 1,
              ...field,
            })),
          },
        ],
      },
      is_active: true,
    },
  );
}

export function captureMatchingPageProblems(page: Page, matchers: RegExp[]) {
  const problems: string[] = [];
  const collect = (text: string) => {
    if (matchers.some((matcher) => matcher.test(text))) {
      problems.push(text);
    }
  };

  page.on("console", (message) => {
    if (message.type() === "error") {
      collect(message.text());
    }
  });
  page.on("pageerror", (error) => collect(error.message));

  return problems;
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
  const orgUsers = await loadOrganizationUsers(request);
  const collectorId = orgUsers.get(collector.email)?.id ?? collector.id;
  const reviewerId = orgUsers.get(state.users.reviewer.email)?.id ?? state.users.reviewer.id;

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
      entity_id: state.entities.generation.id,
      collector_id: collectorId,
      reviewer_id: reviewerId,
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
    entityId: state.entities.generation.id,
    entityName: state.entities.generation.name,
  };
}

export async function createFormConfigResyncScenario(
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
      code: `FCR_${suffix}`,
      name: `Form Config Resync ${suffix}`,
      version: "2026.1",
      jurisdiction: "UK",
    }
  );

  const section = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/standards/${standard.id}/sections`,
    adminAuth.headers,
    {
      code: `FCRSEC_${suffix}`,
      title: `Form Config Resync Section ${suffix}`,
      sort_order: 10,
    }
  );

  const disclosure = await apiPost<{ id: number; code: string }>(
    request,
    `${apiUrl}/standards/${standard.id}/disclosures`,
    adminAuth.headers,
    {
      section_id: section.id,
      code: `FCRDISC_${suffix}`,
      title: `Form Config Resync Disclosure ${suffix}`,
      description: "Scenario-owned disclosure for stale/resync regression coverage",
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
      item_code: `FCRITEM_${suffix}`,
      name: `Form Config Resync Metric ${suffix}`,
      description: "Scenario-owned metric for guided config stale/resync coverage",
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
      code: `FCR_METRIC_${suffix}`,
      name: `Form Config Resync Element ${suffix}`,
      description: "Scenario-owned shared element for stale/resync coverage",
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

  const project = await apiPost<{ id: number; name: string }>(
    request,
    `${apiUrl}/projects`,
    managerAuth.headers,
    {
      name: `Form Config Resync Project ${suffix}`,
      reporting_year: 2026,
    }
  );

  await apiPost(
    request,
    `${apiUrl}/projects/${project.id}/standards`,
    managerAuth.headers,
    {
      standard_id: standard.id,
      is_base_standard: true,
    }
  );

  const firstEntity = await apiPost<{ id: number; name: string }>(
    request,
    `${apiUrl}/entities`,
    managerAuth.headers,
    {
      name: `Form Config Facility North ${suffix}`,
      entity_type: "facility",
      country: "GB",
    }
  );

  const secondEntity = await apiPost<{ id: number; name: string }>(
    request,
    `${apiUrl}/entities`,
    managerAuth.headers,
    {
      name: `Form Config Facility South ${suffix}`,
      entity_type: "facility",
      country: "GB",
    }
  );

  const firstAssignment = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/projects/${project.id}/assignments`,
    managerAuth.headers,
    {
      shared_element_id: sharedElement.id,
      entity_id: firstEntity.id,
    }
  );

  const generatedConfig = await apiPost<{
    id: number;
    name: string;
    health: { is_stale: boolean };
  }>(
    request,
    `${apiUrl}/form-configs/projects/${project.id}/generate`,
    managerAuth.headers
  );
  expect(generatedConfig.health.is_stale).toBe(false);

  const secondAssignment = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/projects/${project.id}/assignments`,
    managerAuth.headers,
    {
      shared_element_id: sharedElement.id,
      entity_id: secondEntity.id,
    }
  );

  const activeConfig = await apiGet<{
    id: number;
    name: string;
    health: {
      is_stale: boolean;
      status: string;
      issue_count: number;
      issues: Array<{ code: string; message: string; affected_fields: number }>;
    };
  }>(
    request,
    `${apiUrl}/form-configs/projects/${project.id}/active`,
    managerAuth.headers
  );

  expect(activeConfig.health.is_stale).toBe(true);
  expect(activeConfig.health.status).toBe("stale");
  expect(activeConfig.health.issues).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        code: "UNCONFIGURED_ASSIGNMENT",
        message: "Some live assignments are not covered by the current row-aware config.",
      }),
    ])
  );

  return {
    projectId: project.id,
    projectName: project.name,
    standardId: standard.id,
    disclosureId: disclosure.id,
    itemId: item.id,
    sharedElementId: sharedElement.id,
    sharedElementCode: sharedElement.code,
    generatedConfigId: generatedConfig.id,
    generatedConfigName: generatedConfig.name,
    resyncedConfigName: `Auto-synced config for project #${project.id}`,
    staleIssueCode: "UNCONFIGURED_ASSIGNMENT",
    staleIssueMessage: "Some live assignments are not covered by the current row-aware config.",
    firstAssignmentId: firstAssignment.id,
    secondAssignmentId: secondAssignment.id,
    firstEntityName: firstEntity.name,
    secondEntityName: secondEntity.name,
    activeConfigId: activeConfig.id,
  };
}

export async function createNotificationsSupportModeScenario(
  request: APIRequestContext,
  suffix: string,
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const adminAuth = await loginByApi(request, state.users.admin.email, state.password);
  const managerAuth = await loginByApi(request, state.users.esg_manager.email, state.password);

  const adminAssignmentResponse = await request.post(
    `${apiUrl}/platform/tenants/${state.organization.id}/admins`,
    {
      headers: adminAuth.headers,
      data: { user_id: state.users.admin.id ?? 1 },
    }
  );
  const adminAssignmentText = await adminAssignmentResponse.text();
  expect(
    adminAssignmentResponse.ok() || adminAssignmentResponse.status() === 409,
    adminAssignmentText
  ).toBeTruthy();

  const project = await apiPost<{ id: number; name: string }>(
    request,
    `${apiUrl}/projects`,
    managerAuth.headers,
    {
      name: `Notifications Support Mode ${suffix}`,
      reporting_year: 2026,
    }
  );

  await apiPut(
    request,
    `${apiUrl}/projects/${project.id}/boundary?boundary_id=${state.boundaries.sustainability.id}`,
    adminAuth.headers
  );

  await apiPut(
    request,
    `${apiUrl}/projects/${project.id}/boundary?boundary_id=${state.boundaries.default.id}`,
    managerAuth.headers
  );

  const managerNotifications = await apiGet<{
    items: Array<{ type: string; message: string; is_read: boolean }>;
  }>(
    request,
    `${apiUrl}/notifications?page_size=100&is_read=false`,
    managerAuth.headers
  );
  const adminNotifications = await apiGet<{
    items: Array<{ type: string; message: string; is_read: boolean }>;
  }>(
    request,
    `${apiUrl}/notifications?page_size=100&is_read=false`,
    adminAuth.headers
  );

  const managerMessage = `Boundary #${state.boundaries.sustainability.id} was applied to project #${project.id}.`;
  const adminMessage = `Boundary #${state.boundaries.default.id} was applied to project #${project.id}.`;

  expect(
    managerNotifications.items.some(
      (item) => item.type === "boundary_changed" && item.message === managerMessage && item.is_read === false
    )
  ).toBeTruthy();
  expect(
    adminNotifications.items.some(
      (item) => item.type === "boundary_changed" && item.message === adminMessage && item.is_read === false
    )
  ).toBeTruthy();

  return {
    projectId: project.id,
    projectName: project.name,
    managerMessage,
    adminMessage,
    notificationTitle: "Boundary updated",
    notificationType: "boundary_changed",
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
  const orgUsers = await loadOrganizationUsers(request);
  const managerId = orgUsers.get(state.users.esg_manager.email)?.id ?? state.users.esg_manager.id;
  const reviewerId = orgUsers.get(state.users.reviewer.email)?.id ?? state.users.reviewer.id;

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
      entity_id: state.entities.generation.id,
      collector_id: managerId,
      reviewer_id: reviewerId,
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
    entityId: state.entities.generation.id,
    entityName: state.entities.generation.name,
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

export async function createPendingExportPreviewScenario(
  request: APIRequestContext,
  suffix: string,
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const managerAuth = await loginByApi(request, state.users.esg_manager.email, state.password);
  const journey = await createManagerExportJourneyProject(request, suffix);

  await apiPost(
    request,
    `${apiUrl}/projects/${journey.projectId}/standards`,
    managerAuth.headers,
    { standard_id: journey.standardId }
  );

  await apiPut(
    request,
    `${apiUrl}/projects/${journey.projectId}/boundary?boundary_id=${state.boundaries.sustainability.id}`,
    managerAuth.headers
  );

  await apiPost(
    request,
    `${apiUrl}/projects/${journey.projectId}/boundary/snapshot`,
    managerAuth.headers
  );

  await apiPost(
    request,
    `${apiUrl}/projects/${journey.projectId}/activate`,
    managerAuth.headers
  );

  await makeProjectReadyForExport(
    request,
    journey.projectId,
    journey.itemId,
    journey.sharedElementId,
    journey.entityId,
  );

  await apiPost(
    request,
    `${apiUrl}/projects/${journey.projectId}/start-review`,
    managerAuth.headers
  );

  const exportJob = await apiPost<{ id: number; status: string; report_type: string; export_format: string }>(
    request,
    `${apiUrl}/projects/${journey.projectId}/export/report?export_format=pdf`,
    managerAuth.headers
  );

  return {
    ...journey,
    jobId: exportJob.id,
    jobStatus: exportJob.status,
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
  const orgUsers = await loadOrganizationUsers(request);
  const collectorId = orgUsers.get(collector.email)?.id ?? collector.id;
  const reviewerId = orgUsers.get(state.users.reviewer.email)?.id ?? state.users.reviewer.id;
  const code = `RV-${suffix}`;
  const name = `Review Screen Metric ${suffix}`;

  const assignment = await apiPost<{ id: number; shared_element_id: number }>(
    request,
    `${apiUrl}/projects/${state.project.id}/assignments`,
    adminAuth.headers,
    {
      shared_element_code: code,
      shared_element_name: name,
      entity_id: state.entities.generation.id,
      collector_id: collectorId,
      reviewer_id: reviewerId,
    }
  );

  const dataPoint = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/projects/${state.project.id}/data-points`,
    collectorAuth.headers,
    {
      shared_element_id: assignment.shared_element_id,
      entity_id: state.entities.generation.id,
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

export async function createAssignedDraftCollectionItem(
  request: APIRequestContext,
  suffix: string,
  collectorKey: "collector_energy" | "collector_climate" = "collector_energy",
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const collector = state.users[collectorKey];
  const collectorAuth = await loginByApi(request, collector.email, state.password);
  const journey = await createJourneyAssignment(request, suffix, collectorKey);

  const dataPoint = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/projects/${state.project.id}/data-points`,
    collectorAuth.headers,
    {
      shared_element_id: journey.sharedElementId,
      entity_id: journey.entityId,
      numeric_value: 120000.5,
      unit_code: "MWH",
    }
  );

  return {
    ...journey,
    id: dataPoint.id,
    collectorEmail: collector.email,
  };
}

export async function createApprovedCollectionItem(
  request: APIRequestContext,
  suffix: string,
  collectorKey: "collector_energy" | "collector_climate" = "collector_energy",
) {
  const state = loadDemoState();
  const apiUrl = state.api_url!.replace("localhost", "127.0.0.1");
  const collector = state.users[collectorKey];
  const collectorAuth = await loginByApi(request, collector.email, state.password);
  const reviewerAuth = await loginByApi(request, state.users.reviewer.email, state.password);
  const draft = await createAssignedDraftCollectionItem(request, suffix, collectorKey);

  const evidence = await apiPost<{ id: number }>(
    request,
    `${apiUrl}/evidences`,
    collectorAuth.headers,
    {
      type: "file",
      title: `Scenario Evidence ${suffix}`,
      description: "Scenario-owned evidence for collection read-only testing",
      file_name: `scenario-${suffix}.pdf`,
      file_uri: `file:///scenario-${suffix}.pdf`,
      file_size: 1024,
      mime_type: "application/pdf",
    }
  );

  await apiPost(
    request,
    `${apiUrl}/data-points/${draft.id}/evidences`,
    collectorAuth.headers,
    { evidence_id: evidence.id }
  );

  const submitted = await apiPost<{ status: string }>(
    request,
    `${apiUrl}/data-points/${draft.id}/submit`,
    collectorAuth.headers
  );
  expect(["submitted", "in_review"]).toContain(submitted.status);

  await apiPost(
    request,
    `${apiUrl}/data-points/${draft.id}/approve`,
    reviewerAuth.headers,
    { comment: "Approved for read-only collection wizard test." }
  );

  return draft;
}

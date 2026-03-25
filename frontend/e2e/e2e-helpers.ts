/**
 * Self-contained E2E helpers that create their own test data.
 * No dependency on demo-state.json or pre-seeded databases.
 */
import type { APIRequestContext } from "@playwright/test";

const API = process.env.E2E_API_URL || "http://localhost:8001/api";

export { API };

/** Register a user, login, setup org, return headers with org context. */
export async function setupTestUser(
  request: APIRequestContext,
  suffix = Date.now().toString(),
): Promise<{
  headers: Record<string, string>;
  orgId: number;
  userId: number;
  email: string;
  password: string;
}> {
  const email = `e2e_${suffix}@test.com`;
  const password = "Test1234!";

  // Register
  await request.post(`${API}/auth/register`, {
    data: { email, password, full_name: `E2E ${suffix}` },
  });

  // Login
  const loginResp = await request.post(`${API}/auth/login`, {
    data: { email, password },
  });
  const loginBody = await loginResp.json();
  const token = loginBody.access_token;

  // Get user ID
  const meResp = await request.get(`${API}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const me = await meResp.json();

  // Setup org
  const orgResp = await request.post(`${API}/organizations/setup`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `TestOrg_${suffix}` },
  });
  const org = await orgResp.json();
  const orgId = org.organization_id || org.id;

  return {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Organization-Id": String(orgId),
    },
    orgId,
    userId: me.id,
    email,
    password,
  };
}

/** Create a shared element + data point in a project. */
export async function createTestDataPoint(
  request: APIRequestContext,
  headers: Record<string, string>,
  projectId: number,
  suffix = Date.now().toString(),
): Promise<{ dataPointId: number; sharedElementId: number }> {
  const seResp = await request.post(`${API}/shared-elements`, {
    headers,
    data: { code: `SE_${suffix}`, name: `SE ${suffix}` },
  });
  const se = await seResp.json();

  const dpResp = await request.post(`${API}/projects/${projectId}/data-points`, {
    headers,
    data: { shared_element_id: se.id, numeric_value: 42 },
  });
  const dp = await dpResp.json();

  return { dataPointId: dp.id, sharedElementId: se.id };
}

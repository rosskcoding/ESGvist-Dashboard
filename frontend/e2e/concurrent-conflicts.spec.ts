import { test, expect } from "@playwright/test";
import { API, setupTestUser, createTestDataPoint } from "./e2e-helpers";

test.describe("Concurrent Conflicts", () => {
  let h: Record<string, string>;
  let projectId: number;

  test.beforeAll(async ({ request }) => {
    const u = await setupTestUser(request, `conc_${Date.now()}`);
    h = u.headers;
    const p = await request.post(`${API}/projects`, { headers: h, data: { name: "Concurrency" } });
    projectId = (await p.json()).id;
  });

  test("concurrent DP updates — at least one succeeds", async ({ request }) => {
    const { dataPointId } = await createTestDataPoint(request, h, projectId, `cc1_${Date.now()}`);

    const [r1, r2] = await Promise.all([
      request.patch(`${API}/data-points/${dataPointId}`, { headers: h, data: { numeric_value: 111 } }),
      request.patch(`${API}/data-points/${dataPointId}`, { headers: h, data: { numeric_value: 222 } }),
    ]);
    const ok = [r1, r2].filter((r) => r.ok()).length;
    expect(ok).toBeGreaterThanOrEqual(1);
  });

  test("concurrent project creation both succeed", async ({ request }) => {
    const [r1, r2] = await Promise.all([
      request.post(`${API}/projects`, { headers: h, data: { name: `Dup ${Date.now()} A` } }),
      request.post(`${API}/projects`, { headers: h, data: { name: `Dup ${Date.now()} B` } }),
    ]);
    expect(r1.ok()).toBeTruthy();
    expect(r2.ok()).toBeTruthy();
  });
});

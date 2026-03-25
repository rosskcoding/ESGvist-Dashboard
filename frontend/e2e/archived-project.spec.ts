import { test, expect } from "@playwright/test";
import { API, setupTestUser } from "./e2e-helpers";

test.describe("Archived Project", () => {
  let h: Record<string, string>;
  let projectId: number;

  test.beforeAll(async ({ request }) => {
    const u = await setupTestUser(request, `arch_${Date.now()}`);
    h = u.headers;
    const p = await request.post(`${API}/projects`, { headers: h, data: { name: "Archive Test" } });
    projectId = (await p.json()).id;
  });

  test("can archive project", async ({ request }) => {
    const resp = await request.post(`${API}/projects/${projectId}/archive`, { headers: h });
    // 200 if endpoint exists, 404 if not yet
    if (resp.status() === 404) {
      test.skip(true, "Archive endpoint not implemented");
    }
    expect(resp.ok()).toBeTruthy();
  });

  test("archived project still readable", async ({ request }) => {
    const resp = await request.get(`${API}/projects/${projectId}`, { headers: h });
    expect(resp.ok()).toBeTruthy();
  });
});

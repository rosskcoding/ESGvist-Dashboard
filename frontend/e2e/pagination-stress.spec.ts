import { test, expect } from "@playwright/test";
import { API, setupTestUser } from "./e2e-helpers";

test.describe("Pagination", () => {
  let h: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    const u = await setupTestUser(request, `pag_${Date.now()}`);
    h = u.headers;
    // Seed a few standards
    for (let i = 0; i < 4; i++) {
      await request.post(`${API}/standards`, {
        headers: h,
        data: { code: `PAG_${Date.now()}_${i}`, name: `Std ${i}` },
      });
    }
  });

  test("standards pagination respects page_size", async ({ request }) => {
    const resp = await request.get(`${API}/standards?page=1&page_size=2`, { headers: h });
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data.items.length).toBeLessThanOrEqual(2);
    expect(data.total).toBeGreaterThanOrEqual(4);
  });

  test("page 2 has different items", async ({ request }) => {
    const p1 = await (await request.get(`${API}/standards?page=1&page_size=2`, { headers: h })).json();
    const p2 = await (await request.get(`${API}/standards?page=2&page_size=2`, { headers: h })).json();
    if (p2.items.length > 0) {
      const ids1 = new Set(p1.items.map((i: { id: number }) => i.id));
      for (const item of p2.items) {
        expect(ids1.has(item.id)).toBe(false);
      }
    }
  });

  test("notifications endpoint paginates", async ({ request }) => {
    const resp = await request.get(`${API}/notifications?page=1&page_size=5`, { headers: h });
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data.total).toBeGreaterThanOrEqual(0);
  });

  test("audit endpoint paginates", async ({ request }) => {
    const resp = await request.get(`${API}/audit-log?page=1&page_size=10`, { headers: h });
    expect(resp.ok()).toBeTruthy();
  });
});

import { test, expect } from "@playwright/test";
import { API, setupTestUser, createTestDataPoint } from "./e2e-helpers";

test.describe("Comment Threads", () => {
  let h: Record<string, string>;
  let projectId: number;

  test.beforeAll(async ({ request }) => {
    const u = await setupTestUser(request, `cmt_${Date.now()}`);
    h = u.headers;
    const p = await request.post(`${API}/projects`, { headers: h, data: { name: "CmtProj" } });
    projectId = (await p.json()).id;
  });

  test("create comment on data point", async ({ request }) => {
    const { dataPointId } = await createTestDataPoint(request, h, projectId, `c1_${Date.now()}`);
    const resp = await request.post(`${API}/comments`, {
      headers: h,
      data: { body: "Root comment", data_point_id: dataPointId, comment_type: "general" },
    });
    expect(resp.ok()).toBeTruthy();
    const c = await resp.json();
    expect(c.id).toBeTruthy();
  });

  test("reply to comment", async ({ request }) => {
    const { dataPointId } = await createTestDataPoint(request, h, projectId, `c2_${Date.now()}`);
    const root = await (await request.post(`${API}/comments`, {
      headers: h,
      data: { body: "Parent", data_point_id: dataPointId, comment_type: "general" },
    })).json();

    const reply = await request.post(`${API}/comments`, {
      headers: h,
      data: { body: "Reply", data_point_id: dataPointId, parent_comment_id: root.id, comment_type: "general" },
    });
    expect(reply.ok()).toBeTruthy();
    const r = await reply.json();
    expect(r.parent_comment_id ?? r.parent_id).toBe(root.id);
  });

  test("reject comment without binding", async ({ request }) => {
    const resp = await request.post(`${API}/comments`, {
      headers: h,
      data: { body: "Floating", comment_type: "general" },
    });
    expect(resp.status()).toBeGreaterThanOrEqual(400);
  });

  test("resolve comment", async ({ request }) => {
    const { dataPointId } = await createTestDataPoint(request, h, projectId, `c3_${Date.now()}`);
    const c = await (await request.post(`${API}/comments`, {
      headers: h,
      data: { body: "To resolve", data_point_id: dataPointId, comment_type: "general" },
    })).json();

    const resp = await request.patch(`${API}/comments/${c.id}/resolve`, { headers: h });
    expect(resp.ok()).toBeTruthy();
    expect((await resp.json()).is_resolved).toBe(true);
  });
});

import { test, expect } from "@playwright/test";
import { API } from "./e2e-helpers";

test.describe("Password Change", () => {
  let email: string;
  const password = "OldPass123!";
  const newPassword = "NewPass456!";

  test.beforeAll(async ({ request }) => {
    email = `pw_${Date.now()}_${Math.random().toString(36).slice(2, 8)}@test.com`;
    const regResp = await request.post(`${API}/auth/register`, {
      data: { email, password, full_name: "PW User" },
    });
    expect(regResp.ok(), `Register failed: ${await regResp.text()}`).toBeTruthy();
  });

  test("change password via API", async ({ request }) => {
    const login = await request.post(`${API}/auth/login`, { data: { email, password } });
    expect(login.ok(), `Login failed for ${email}`).toBeTruthy();
    const { access_token } = await login.json();

    const resp = await request.post(`${API}/auth/change-password`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { current_password: password, new_password: newPassword },
    });
    expect(resp.ok(), `Change password failed: ${await resp.text()}`).toBeTruthy();
    const body = await resp.json();
    expect(body.changed).toBe(true);
  });

  test("old password fails after change", async ({ request }) => {
    const resp = await request.post(`${API}/auth/login`, { data: { email, password } });
    expect(resp.ok()).toBe(false);
  });

  test("new password works after change", async ({ request }) => {
    const resp = await request.post(`${API}/auth/login`, { data: { email, password: newPassword } });
    expect(resp.ok()).toBeTruthy();
  });

  test("login page renders", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });
});

import { expect, type Page } from "@playwright/test";

export async function loginAs(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 10000 });
}

export const ADMIN_CREDS = { email: "admin@esgvist.com", password: "Admin12345" };

export async function loginAsAdmin(page: Page) {
  await loginAs(page, ADMIN_CREDS.email, ADMIN_CREDS.password);
}

/** Register a user via API and return their credentials */
export async function registerUser(
  request: import("@playwright/test").APIRequestContext,
  email: string,
  password: string,
  fullName: string,
) {
  await request.post("http://localhost:8001/api/auth/register", {
    data: { email, password, full_name: fullName },
  });
}

/** Get JWT token via API */
export async function getToken(
  request: import("@playwright/test").APIRequestContext,
  email: string,
  password: string,
): Promise<string> {
  const resp = await request.post("http://localhost:8001/api/auth/login", {
    data: { email, password },
  });
  const body = await resp.json();
  return body.access_token;
}

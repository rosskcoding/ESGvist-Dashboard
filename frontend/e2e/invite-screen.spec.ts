import { expect, test, type APIRequestContext } from "@playwright/test";

import { loadDemoState } from "./screen-helpers";

const demoState = loadDemoState();
const apiUrl = (demoState.api_url || "http://localhost:8002/api").replace("localhost", "127.0.0.1");

function uniqueInviteEmail(prefix: string) {
  return `${prefix}.${Date.now()}@invites.example.com`;
}

async function assertJsonOk(response: Awaited<ReturnType<APIRequestContext["post"]>>) {
  const text = await response.text();
  expect(response.ok(), text).toBeTruthy();
  return text ? JSON.parse(text) : null;
}

async function createInvite(request: APIRequestContext, email: string, role = "collector") {
  const loginResponse = await request.post(`${apiUrl}/auth/login`, {
    data: {
      email: demoState.users.admin.email,
      password: demoState.password,
    },
  });
  const loginBody = await assertJsonOk(loginResponse);

  const inviteResponse = await request.post(`${apiUrl}/invitations`, {
    headers: {
      Authorization: `Bearer ${loginBody.access_token}`,
      "X-Organization-Id": String(demoState.organization.id),
    },
    data: {
      email,
      role,
    },
  });

  return assertJsonOk(inviteResponse);
}

test.describe("Screen 3 - Invite Acceptance", () => {
  test("shows invalid invitation state for unknown token", async ({ page }) => {
    await page.goto("/invite/not-a-real-token");

    await expect(page.getByText("Invalid Invitation")).toBeVisible();
    await expect(page.getByText("Invalid or already used invitation token")).toBeVisible();
    await expect(page.getByRole("button", { name: "Go to Login" })).toBeVisible();
  });

  test("renders invite details for a valid token", async ({ page, request }) => {
    const invitedEmail = uniqueInviteEmail("invite-render");
    const invitation = await createInvite(request, invitedEmail, "collector");

    await page.goto(`/invite/${invitation.token}`);

    await expect(page.getByText("You've been invited")).toBeVisible();
    await expect(page.getByText("Northwind Renewables Group")).toBeVisible();
    await expect(page.locator('input[value="' + invitedEmail + '"]')).toBeVisible();
    await expect(page.getByLabel("Full Name")).toBeVisible();
    await expect(page.getByRole("button", { name: "Accept Invitation" })).toBeEnabled();
  });

  test("accepts an invitation by creating an account and redirects to dashboard", async ({ page, request }) => {
    const invitedEmail = uniqueInviteEmail("invite-accept");
    const invitation = await createInvite(request, invitedEmail, "collector");

    await page.goto(`/invite/${invitation.token}`);
    await page.getByLabel("Full Name").fill("Invited Facility User");
    await page.getByLabel("Password", { exact: true }).fill("Test1234");
    await page.getByLabel("Confirm Password").fill("Test1234");
    await page.getByRole("button", { name: "Accept Invitation" }).click();

    await expect(page).toHaveURL(/dashboard/, { timeout: 20_000 });

    const storage = await page.evaluate(() => ({
      accessToken: localStorage.getItem("access_token"),
      refreshToken: localStorage.getItem("refresh_token"),
      organizationId: localStorage.getItem("organization_id"),
    }));

    expect(storage.accessToken).toBeTruthy();
    expect(storage.refreshToken).toBeTruthy();
    expect(storage.organizationId).toBe(String(demoState.organization.id));
  });

  test("declines a valid invitation and returns to login", async ({ page, request }) => {
    const invitedEmail = uniqueInviteEmail("invite-decline");
    const invitation = await createInvite(request, invitedEmail, "collector");

    await page.goto(`/invite/${invitation.token}`);
    await page.getByRole("button", { name: "Decline" }).click();

    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });
});

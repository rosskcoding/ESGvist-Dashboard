import { expect, test, type Page } from "@playwright/test";

import {
  createNotificationsSupportModeScenario,
  loadDemoState,
  loginThroughUi,
} from "./screen-helpers";

const demoState = loadDemoState();
const apiUrl = demoState.api_url!.replace("localhost", "127.0.0.1");

async function loginAsPlatformAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(demoState.users.admin.email);
  await page.getByLabel("Password").fill(demoState.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/(dashboard|platform\/tenants)(\/.*)?$/, {
    timeout: 15_000,
  });
}

async function startSupportMode(page: Page, reason: string) {
  await loginAsPlatformAdmin(page);
  await page.goto(`/platform/tenants/${demoState.organization.id}`);

  await expect(page.getByRole("heading", { name: "Tenant Details" })).toBeVisible();
  await page.getByRole("button", { name: "Start Support Session" }).click();

  const dialog = page.locator("dialog[open]");
  await expect(dialog.getByText("Start Support Session")).toBeVisible();
  await dialog.getByLabel("Reason").fill(reason);
  await dialog.getByRole("button", { name: "Start Session" }).click();

  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });
  await expect(page.getByText("Support mode active")).toBeVisible();
  await expect(page.getByText(`Tenant context: ${demoState.organization.name}`)).toBeVisible();
}

test.afterEach(async ({ page, request }) => {
  const cookies = await page.context().cookies();
  const accessCookie = cookies.find((cookie) => cookie.name === "access_token");
  const csrfCookie = cookies.find((cookie) => cookie.name === "csrf_token");

  if (!accessCookie || !csrfCookie) {
    return;
  }

  const uiOrigin = new URL(page.url()).origin;
  await request.delete(`${apiUrl}/platform/support-session/current`, {
    headers: {
      Cookie: `${accessCookie.name}=${accessCookie.value}`,
      Origin: uiOrigin,
      "X-CSRF-Token": csrfCookie.value,
    },
  });
});

test.describe("Notifications support-mode regressions", () => {
  test("manager can read tenant notifications and update digest preferences", async ({
    page,
    request,
  }) => {
    const scenario = await createNotificationsSupportModeScenario(
      request,
      `manager-${Date.now()}`
    );

    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Notifications" }).click();

    await expect(page).toHaveURL(/\/notifications$/);
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    await expect(page.getByText(scenario.notificationTitle, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(scenario.managerMessage)).toBeVisible();
    await expect(page.getByText(scenario.notificationType, { exact: true })).toBeVisible();

    const notificationCard = page
      .locator("div.rounded-lg", { has: page.getByText(scenario.managerMessage) })
      .first();
    await notificationCard.getByRole("button", { name: "Mark as read" }).click();
    await expect(page.getByText(scenario.managerMessage)).toHaveCount(0);

    await page.getByLabel("Read Status").selectOption("read");
    await expect(page.getByText(scenario.managerMessage)).toBeVisible();

    await page.getByLabel("Email digest").selectOption("weekly");
    await expect(page.getByLabel("Email digest")).toHaveValue("weekly");
  });

  test("platform admin sees tenant notifications only inside support mode", async ({
    page,
    request,
  }) => {
    const scenario = await createNotificationsSupportModeScenario(
      request,
      `support-${Date.now()}`
    );

    await startSupportMode(page, `Notifications support mode ${scenario.projectId}`);
    await page.goto("/notifications");

    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    await expect(page.getByText("Support mode active")).toBeVisible();
    await expect(page.getByText(scenario.adminMessage)).toBeVisible();

    const notificationCard = page
      .locator("div.rounded-lg", { has: page.getByText(scenario.adminMessage) })
      .first();
    await notificationCard.getByRole("button", { name: "Mark as read" }).click();
    await expect(page.getByText(scenario.adminMessage)).toHaveCount(0);

    await page.getByLabel("Read Status").selectOption("read");
    await expect(page.getByText(scenario.adminMessage)).toBeVisible();

    await page.getByLabel("Email digest").selectOption("daily");
    await expect(page.getByLabel("Email digest")).toHaveValue("daily");

    await page.getByRole("button", { name: "Exit Support Mode" }).click();
    await expect(page).toHaveURL(/\/platform\/tenants$/, { timeout: 15_000 });
    await expect(page.getByText("Support mode active")).toHaveCount(0);
  });
});

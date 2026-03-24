import { expect, test, type Page } from "@playwright/test";

import {
  apiPost,
  createJourneyAssignment,
  loadDemoState,
  loginByApi,
  loginThroughUi,
  revokeCurrentBrowserSession,
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

test.describe("Platform and setup regressions", () => {
  test("onboarding creates an organization and lands on the post-setup dashboard", async ({
    page,
  }) => {
    const uniqueId = Date.now();
    const organizationName = `Playwright Onboarding ${uniqueId}`;
    const email = `playwright.onboarding.${uniqueId}@example.com`;

    await page.goto("/register");
    await page.getByLabel("Full Name").fill("Playwright Onboarding");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill("Test1234");
    await page.getByLabel("Confirm Password", { exact: true }).fill("Test1234");
    await page.getByLabel(/I agree to the/i).click();
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page).toHaveURL(/\/onboarding$/, { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Organization Setup" })).toBeVisible();

    await page.getByLabel("Organization name").fill(organizationName);
    await page.getByLabel("Country").selectOption("GB");
    await page.getByLabel("Industry").selectOption("utilities");

    const nextButton = page.getByRole("button", { name: "Next", exact: true });
    for (let step = 0; step < 4; step += 1) {
      await nextButton.click();
    }

    await expect(page.getByText(organizationName)).toBeVisible();
    await page.getByRole("button", { name: "Create Organization" }).click();

    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });
    await expect(page.getByText(`Welcome to ESGvist, ${organizationName}!`)).toBeVisible();
    await expect(page.getByRole("link", { name: "Create your first ESG report" })).toBeVisible();
  });

  test("platform admin can start and end support mode from tenant detail", async ({ page }) => {
    await startSupportMode(page, "Playwright support mode regression");

    await page.getByRole("button", { name: "Exit Support Mode" }).click();
    await expect(page).toHaveURL(/\/platform\/tenants$/, { timeout: 15_000 });
    await expect(page.getByText("Support mode active")).toHaveCount(0);
  });

  test("expired session redirects to login and returns user to the original page", async ({
    page,
    request,
  }) => {
    await loginThroughUi(page, demoState.users.esg_manager.email, demoState.password);
    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();

    await revokeCurrentBrowserSession(page, request);
    await page.reload();

    await expect(page).toHaveURL(/\/login\?reason=session-expired.*next=%2Fprojects/, {
      timeout: 15_000,
    });
    await expect(
      page.getByText("Your session expired. Sign in again to continue."),
    ).toBeVisible();

    await page.getByLabel("Email").fill(demoState.users.esg_manager.email);
    await page.getByLabel("Password").fill(demoState.password);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/projects$/, { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  });

  test("mapping history shows version timeline and field diff inside support mode", async ({
    page,
    request,
  }) => {
    const suffix = `mapping-${Date.now()}`;
    const journey = await createJourneyAssignment(request, suffix);
    const adminAuth = await loginByApi(request, demoState.users.admin.email, demoState.password);

    await apiPost(
      request,
      `${apiUrl}/mappings`,
      adminAuth.headers,
      {
        requirement_item_id: journey.itemId,
        shared_element_id: journey.sharedElementId,
        mapping_type: "partial",
      }
    );

    await startSupportMode(page, `Inspect mapping history ${suffix}`);
    await page.goto(
      `/settings/mappings?standardId=${journey.standardId}&disclosureId=${journey.disclosureId}&itemId=${journey.itemId}&elementId=${journey.sharedElementId}`
    );

    await expect(page.getByRole("heading", { name: "Mapping History" })).toBeVisible();
    await expect(page.getByText("Current Mappings For Selected Item")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(journey.code, { exact: true })).toBeVisible();

    const historyTable = page.locator("table", {
      has: page.getByRole("columnheader", { name: "Status" }),
    });
    await expect(historyTable.getByText("v2")).toBeVisible();
    await expect(historyTable.getByText("Current")).toBeVisible();
    await expect(historyTable.getByText("Archived")).toBeVisible();

    await page.getByLabel("Compare From").selectOption("1");
    await page.getByLabel("Compare To").selectOption("2");

    const diffTable = page.locator("table", {
      has: page.getByRole("columnheader", { name: "Old Value" }),
    });
    await expect(diffTable.getByText("mapping_type")).toBeVisible();
    await expect(diffTable.getByText("full")).toBeVisible();
    await expect(diffTable.getByText("partial")).toBeVisible();

    await page.getByRole("button", { name: "Exit Support Mode" }).click();
    await expect(page).toHaveURL(/\/platform\/tenants$/, { timeout: 15_000 });
  });
});

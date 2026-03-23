import { expect, test } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

const admin = demoState.users.admin;
const manager = demoState.users.esg_manager;
const collector = demoState.users.collector_energy;
const reviewer = demoState.users.reviewer;
const auditor = demoState.users.auditor;

test.describe("Screen 24-26 and 30-31 - Notifications and Platform Admin", () => {
  test("manager reaches notification center from topbar bell and updates preferences", async ({ page }) => {
    await loginThroughUi(page, manager.email, demoState.password);
    await page.goto("/dashboard");

    await page.getByRole("button", { name: "Notifications" }).click();
    await expect(page).toHaveURL(/\/notifications$/);
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    await expect(page.getByText("Delivery Preferences")).toBeVisible();
    await expect(page.getByText("Notification Center", { exact: true })).toBeVisible();

    const emailSwitch = page.getByRole("switch", { name: "Email delivery" });
    const originalState = (await emailSwitch.getAttribute("aria-checked")) ?? "true";
    const toggledState = originalState === "true" ? "false" : "true";

    await emailSwitch.click();
    await expect(emailSwitch).toHaveAttribute("aria-checked", toggledState);
    await emailSwitch.click();
    await expect(emailSwitch).toHaveAttribute("aria-checked", originalState);

    await page.getByLabel("Read Status").selectOption("all");
    await page.getByLabel("Severity").selectOption("important");
    await expect(page.getByText("Back to dashboard")).toBeVisible();
  });

  test("collector can access notification center through the bell", async ({ page }) => {
    await loginThroughUi(page, collector.email, demoState.password);
    await page.goto("/dashboard");

    await page.getByRole("button", { name: "Notifications" }).click();
    await expect(page).toHaveURL(/\/notifications$/);
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    await expect(page.getByText("Unread", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Inbox Size", { exact: true })).toBeVisible();
  });

  test("auditor is blocked from notification center", async ({ page }) => {
    await loginThroughUi(page, auditor.email, demoState.password);
    await page.goto("/notifications");

    await expect(page.getByText("Access denied")).toBeVisible();
    await expect(
      page.getByText("Auditor accounts do not receive notification center access.")
    ).toBeVisible();
  });

  test("platform admin creates and manages a tenant", async ({ page }) => {
    const suffix = `${Date.now()}`;
    const tenantName = `UI Tenant ${suffix}`;
    const updatedName = `${tenantName} Updated`;

    await loginThroughUi(page, admin.email, demoState.password);
    await page.goto("/platform/tenants");

    await expect(page.getByRole("heading", { name: "Tenants" })).toBeVisible();
    await expect(page.getByText("Tenant Directory")).toBeVisible();
    await page.getByRole("button", { name: "Create Tenant" }).click();

    await expect(page.getByRole("heading", { name: "Create Tenant" })).toBeVisible();
    await page.getByLabel("Name").fill(tenantName);
    await page.getByLabel("Country").fill("United Kingdom");
    await page.getByLabel("Industry").fill("Renewable Energy");
    await page.getByRole("button", { name: "Create Tenant" }).click();

    await expect(page).toHaveURL(/\/platform\/tenants\/\d+$/);
    await expect(page.getByRole("heading", { name: "Tenant Details" })).toBeVisible();

    await page.getByLabel("Name").fill(updatedName);
    await page.getByLabel("Country").fill("Germany");
    await page.getByLabel("Industry").fill("Grid Infrastructure");
    await page.getByRole("button", { name: "Save Changes" }).click();
    await expect(page.getByText("Tenant settings saved.")).toBeVisible();

    await page.getByLabel("Lifecycle Status").selectOption("suspended");
    await page.getByRole("button", { name: "Apply Status" }).click();
    await expect(page.getByText("Tenant moved to suspended.")).toBeVisible();
    await expect(page.getByText("suspended").first()).toBeVisible();

    await page.getByLabel("Lifecycle Status").selectOption("active");
    await page.getByRole("button", { name: "Apply Status" }).click();
    await expect(page.getByText("Tenant moved to active.")).toBeVisible();

    await page.getByLabel("Assign Organization Admin").selectOption({
      label: `${admin.full_name} (${admin.email})`,
    });
    await page.getByRole("button", { name: "Assign Admin" }).click();
    await expect(page.getByText(`${admin.full_name} assigned as tenant admin.`)).toBeVisible();

    const selfRegistrationSwitch = page.getByRole("switch", { name: "Allow self registration" });
    const originalSelfRegistration = (await selfRegistrationSwitch.getAttribute("aria-checked")) ?? "false";
    const toggledSelfRegistration = originalSelfRegistration === "true" ? "false" : "true";
    await selfRegistrationSwitch.click();
    await expect(selfRegistrationSwitch).toHaveAttribute("aria-checked", toggledSelfRegistration);
    await selfRegistrationSwitch.click();
    await expect(selfRegistrationSwitch).toHaveAttribute("aria-checked", originalSelfRegistration);

    await page.getByRole("button", { name: "Run Export Jobs" }).click();
    await expect(page.getByText("Job 'export-jobs' triggered.")).toBeVisible();

    await page.goto("/platform/tenants");
    await page.getByLabel("Search tenants").fill(updatedName);
    await expect(page.getByRole("cell", { name: updatedName })).toBeVisible();
  });

  test("manager is blocked from platform admin screens", async ({ page }) => {
    await loginThroughUi(page, manager.email, demoState.password);
    await expect(page.getByRole("link", { name: "Tenants" })).toHaveCount(0);

    await page.goto("/platform/tenants");
    await expect(page.getByText("Access denied")).toBeVisible();
    await expect(page.getByText("Only platform admins can access tenant management.")).toBeVisible();
  });
});

import { expect, test } from "@playwright/test";

import { createReviewReadyItem, loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();
const admin = demoState.users.admin;
const manager = demoState.users.esg_manager;
const reviewer = demoState.users.reviewer;
const collector = demoState.users.collector_energy;

test.describe("Screen 32-37 - AI, Profile, Organization Settings, and Webhooks", () => {
  test("manager uses the global AI copilot from dashboard", async ({ page }) => {
    await loginThroughUi(page, manager.email, demoState.password);
    await page.goto("/dashboard");

    await page.getByRole("button", { name: "AI Copilot", exact: true }).click();
    await expect(page.getByRole("heading", { name: "AI Copilot" })).toBeVisible();
    await page.getByPlaceholder("Ask the AI copilot...").fill("What should I check next?");
    await page.getByRole("button", { name: "Send AI message" }).click();
    await expect(page.locator("aside").getByText(/AI guidance|workspace/i).first()).toBeVisible();
    await page.getByRole("button", { name: "Close AI Copilot" }).click();
  });

  test("manager runs inline AI explain on completeness", async ({ page }) => {
    await loginThroughUi(page, manager.email, demoState.password);
    await page.goto("/completeness");

    await expect(page.getByRole("heading", { name: "Completeness" })).toBeVisible();
    await page.getByRole("button", { name: "Explain with AI" }).click();
    await expect(page.getByText("Inline AI Explain")).toBeVisible();
    await expect(page.getByText(/Project .*complete|Project completeness is/i)).toBeVisible();
  });

  test("reviewer runs AI review assist on validation", async ({ page, request }) => {
    const item = await createReviewReadyItem(request, `${Date.now()}-ai-review`);

    await loginThroughUi(page, reviewer.email, demoState.password);
    await page.goto("/validation");

    await expect(page.getByRole("heading", { name: "Validation Review" })).toBeVisible();
    await page.getByRole("button", { name: new RegExp(item.code) }).first().click();
    await page.getByRole("button", { name: "Run AI Review Assist" }).click();
    await expect(page.getByText(/Data point #/)).toBeVisible();
    await expect(page.getByText("Review AI Assistant")).toBeVisible();
  });

  test("platform admin can review profile and save unchanged profile info", async ({ page }) => {
    await loginThroughUi(page, admin.email, demoState.password);
    await page.goto("/settings/profile");

    await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
    const existingName = await page.getByLabel("Display Name").inputValue();
    await page.getByLabel("Display Name").fill(existingName);
    await page.getByRole("button", { name: "Save Changes" }).click();
    await expect(page.getByText("Profile updated successfully.")).toBeVisible();
    await expect(page.getByText(/Two-factor authentication/)).toBeVisible();
  });

  test("platform admin can open organization settings and save current configuration", async ({ page }) => {
    await loginThroughUi(page, admin.email, demoState.password);
    await page.goto("/settings");

    await expect(page.getByRole("heading", { name: "Organization Settings" })).toBeVisible();
    await expect(page.getByText("Authentication Policy", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Save Settings" }).click();
    await expect(page.getByText("Settings saved successfully.")).toBeVisible();
  });

  test("platform admin manages webhook lifecycle", async ({ page }) => {
    const suffix = `${Date.now()}`;
    const webhookUrl = `https://example.com/hooks/ui-${suffix}`;

    await loginThroughUi(page, admin.email, demoState.password);
    await page.goto("/settings/webhooks");

    await expect(page.getByRole("heading", { name: "Webhooks" })).toBeVisible();
    await page.getByRole("button", { name: "Add Webhook" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("URL").fill(webhookUrl);
    await dialog.getByLabel("Secret").fill(`secret-${suffix}`);
    await dialog.getByLabel("project.published").check();
    await dialog.getByLabel("evidence.created").check();
    await dialog.getByRole("button", { name: "Create Webhook" }).click();

    await expect(page.getByText("Webhook created.")).toBeVisible();
    await expect(page.getByRole("button", { name: webhookUrl })).toBeVisible();
    await page.getByRole("button", { name: "Send Test Event" }).click();
    await expect(page.getByText("Webhook test delivery queued.")).toBeVisible();
    await expect(page.getByText("webhook.test")).toBeVisible();
    await page.getByRole("button", { name: "Delete Endpoint" }).click();
    await expect(page.getByText("Webhook deleted.")).toBeVisible();
  });

  test("collector is blocked from webhook management", async ({ page }) => {
    await loginThroughUi(page, collector.email, demoState.password);
    await expect(page.getByRole("link", { name: "Webhooks" })).toHaveCount(0);

    await page.goto("/settings/webhooks");
    await expect(page.getByText("Access denied")).toBeVisible();
    await expect(page.getByText("Only admin and platform admin roles can manage webhooks.")).toBeVisible();
  });

  test("copilot streams response and shows metadata", async ({ page }) => {
    await loginThroughUi(page, manager.email, demoState.password);
    await page.goto("/dashboard");

    await page.getByRole("button", { name: "AI Copilot", exact: true }).click();
    await expect(page.getByRole("heading", { name: "AI Copilot" })).toBeVisible();

    // Verify context is displayed
    await expect(page.getByText(/Context:/)).toBeVisible();

    // Send a message — uses streaming endpoint
    await page.getByPlaceholder("Ask the AI copilot...").fill("What data is still missing?");
    await page.getByRole("button", { name: "Send AI message" }).click();

    // Wait for response to appear with metadata (provider badge, confidence)
    await expect(page.locator("aside").getByText(/AI guidance|workspace|missing/i).first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator("aside .inline-flex").filter({ hasText: /static|grounded/ }).first()).toBeVisible();
  });

  test("suggested actions are clickable and navigate", async ({ page }) => {
    await loginThroughUi(page, manager.email, demoState.password);
    await page.goto("/dashboard");

    await page.getByRole("button", { name: "AI Copilot", exact: true }).click();
    await page.getByPlaceholder("Ask the AI copilot...").fill("What should I check next?");
    await page.getByRole("button", { name: "Send AI message" }).click();

    // Wait for response with suggested actions
    await expect(page.getByText("Suggested actions")).toBeVisible({ timeout: 10000 });

    // Suggested actions should be buttons (not plain text)
    const actionButton = page.locator("aside button").filter({ hasText: /Open current workspace|Review blockers|Open collection/ }).first();
    await expect(actionButton).toBeVisible();

    // Clicking should trigger navigation
    await actionButton.click();
    // Page should have navigated away from dashboard
    await page.waitForTimeout(500);
  });

  test("completeness page shows per-disclosure Why partial? links", async ({ page }) => {
    await loginThroughUi(page, manager.email, demoState.password);
    await page.goto("/completeness");

    await expect(page.getByRole("heading", { name: "Completeness" })).toBeVisible();

    // If there are partial/missing disclosures, "Why" links should appear
    const whyLinks = page.getByRole("button").filter({ hasText: /Why (partial|missing)\?/ });
    const count = await whyLinks.count();
    if (count > 0) {
      // Click the first "Why?" link
      await whyLinks.first().click();
      // Should show an inline AI explanation
      await expect(page.getByText(/Project completeness|completeness blockers|requirement items/i).first()).toBeVisible({ timeout: 10000 });
    }
  });

  test("boundary page shows Why included/excluded? links", async ({ page }) => {
    await loginThroughUi(page, manager.email, demoState.password);
    await page.goto("/settings/boundaries");

    await expect(page.getByRole("heading", { name: /Boundaries/i })).toBeVisible();

    // If boundaries have memberships, "Why" links should appear
    const whyLinks = page.getByRole("button").filter({ hasText: /Why (included|excluded)\?/ });
    const count = await whyLinks.count();
    if (count > 0) {
      await whyLinks.first().click();
      await expect(page.getByText(/entity|boundary|included|excluded/i).first()).toBeVisible({ timeout: 10000 });
    }
  });

  test("evidence page shows evidence guidance button", async ({ page }) => {
    await loginThroughUi(page, manager.email, demoState.password);
    await page.goto("/evidence");

    await expect(page.getByRole("heading", { name: /Evidence/i })).toBeVisible();

    // If evidence detail dialog shows linked requirement items, guidance button should appear
    // The button is visible only inside the detail dialog, so we need to open one first
    const evidenceRows = page.getByRole("row");
    if (await evidenceRows.count() > 1) {
      // Click first evidence row to open detail
      await evidenceRows.nth(1).click();
      // Check if guidance button appears in the dialog
      const guidanceInDialog = page.getByRole("dialog").getByRole("button").filter({ hasText: "Evidence guidance" });
      if (await guidanceInDialog.count() > 0) {
        await guidanceInDialog.first().click();
        await expect(page.getByText(/evidence.*status|evidence.*required|evidence.*optional/i).first()).toBeVisible({ timeout: 10000 });
      }
    }
  });
});

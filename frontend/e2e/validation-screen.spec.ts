import { expect, test, type Page } from "@playwright/test";

import { createReviewReadyItem, loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();

test.describe("Screen 16-17 - Review & Validation", () => {
  function reviewQueueItem(page: Page, code: string) {
    return page.getByRole("button", { name: new RegExp(code) }).first();
  }

  test("reviewer sees validation queue, item detail, and can add a comment", async ({ page, request }) => {
    const item = await createReviewReadyItem(request, `${Date.now()}-comment`);

    await loginThroughUi(page, demoState.users.reviewer.email, demoState.password);
    await page.goto("/validation");

    await expect(page.getByRole("heading", { name: "Validation Review" })).toBeVisible();
    await expect(reviewQueueItem(page, item.code)).toBeVisible();

    await reviewQueueItem(page, item.code).click();
    await expect(page.getByRole("heading", { name: item.name })).toBeVisible();
    await expect(page.getByText("Boundary Context")).toBeVisible();
    await expect(page.getByText("Evidence (0)")).toBeVisible();

    await page.getByLabel("Review comment").fill("Please confirm methodology used for this metric.");
    await page.getByRole("button", { name: /send comment/i }).click();

    await expect(page.getByText("Please confirm methodology used for this metric.")).toBeVisible();
    await expect(page.getByText("question").last()).toBeVisible();
  });

  test("reviewer approves a single in-review item", async ({ page, request }) => {
    const item = await createReviewReadyItem(request, `${Date.now()}-approve`);

    await loginThroughUi(page, demoState.users.reviewer.email, demoState.password);
    await page.goto("/validation");

    await reviewQueueItem(page, item.code).click();
    await page.getByRole("button", { name: "Approve", exact: true }).click();

    await expect(reviewQueueItem(page, item.code)).toHaveCount(0);
  });

  test("reviewer can batch request revision for multiple items", async ({ page, request }) => {
    const first = await createReviewReadyItem(request, `${Date.now()}-batch-a`);
    const second = await createReviewReadyItem(request, `${Date.now()}-batch-b`, "collector_climate");

    await loginThroughUi(page, demoState.users.reviewer.email, demoState.password);
    await page.goto("/validation");

    await page.getByLabel(`Select review item ${first.code}`).check();
    await page.getByLabel(`Select review item ${second.code}`).check();
    await page.getByRole("button", { name: "Request Revision Selected" }).click();

    await page.getByLabel("Batch reason").selectOption("DATA_QUALITY_ISSUE");
    await page.getByLabel("Batch comment").fill("Please restate methodology and attach supporting source detail.");
    await page.getByRole("button", { name: "Confirm batch action" }).click();

    await expect(page.getByText(first.name)).toHaveCount(0);
    await expect(page.getByText(second.name)).toHaveCount(0);
  });

  test("auditor gets read-only validation access", async ({ page, request }) => {
    const item = await createReviewReadyItem(request, `${Date.now()}-audit`);

    await loginThroughUi(page, demoState.users.auditor.email, demoState.password);
    await page.goto("/validation");

    await expect(page.getByText("Auditor access is read-only.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Validation" })).toBeVisible();
    await expect(reviewQueueItem(page, item.code)).toBeVisible();

    await reviewQueueItem(page, item.code).click();
    await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
    await expect(page.getByLabel("Review comment")).toBeDisabled();
  });

  for (const user of [demoState.users.collector_energy, demoState.users.esg_manager]) {
    test(`blocks validation for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Validation" })).toHaveCount(0);
      await page.goto("/validation");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(page.getByText("Only reviewers and auditors can access validation.")).toBeVisible();
    });
  }
});

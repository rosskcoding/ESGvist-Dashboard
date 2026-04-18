import { expect, test, type APIRequestContext } from "@playwright/test";

import { loadDemoState, loginByApi, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();
const apiUrl = demoState.api_url!.replace("localhost", "127.0.0.1");

type MergeResponse = {
  standards: Array<{ standard_id: number; code: string; name: string; coverage_pct: number }>;
  elements: Array<{
    element_id: number;
    code: string;
    name: string;
    domain: string;
    cells: Array<{ standard_id: number; status: string }>;
    boundary_scope?: { entities: Array<{ name: string; included: boolean }> } | null;
  }>;
  summary: {
    common_elements: number;
    unique_elements: number;
    delta_count: number;
  };
};

async function getMergeDataset(request: APIRequestContext) {
  const managerAuth = await loginByApi(request, demoState.users.admin.email, demoState.password);
  const response = await request.get(`${apiUrl}/projects/${demoState.project.id}/merge`, {
    headers: managerAuth.headers,
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as MergeResponse;
}

test.describe("Screen 18 - Coverage Matrix", () => {
  test("admin sees merge matrix, filters it, and opens cell details", async ({ page, request }) => {
    const merge = await getMergeDataset(request);
    const targetElement = merge.elements[0];
    const targetStandard = merge.standards.find((standard) =>
      targetElement.cells.some((cell) => cell.standard_id === standard.standard_id)
    );

    expect(targetElement).toBeTruthy();
    expect(targetStandard).toBeTruthy();

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/merge");

    await expect(page.getByRole("heading", { name: "Coverage Matrix" })).toBeVisible();
    await expect(page.getByText("Project Coverage Matrix", { exact: true })).toBeVisible();
    await expect(page.getByText(targetElement.code, { exact: true })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: targetStandard!.code })).toBeVisible();

    await page.getByLabel("Domain").selectOption(targetElement.domain);
    await expect(page.getByText(targetElement.code, { exact: true })).toBeVisible();

    await page.getByLabel("Search").fill(targetElement.code);
    await expect(page.getByText(targetElement.name, { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Expand" }).first().click();
    await expect(page.getByText("Boundary Scope")).toBeVisible();

    await page
      .getByRole("button", {
        name: `Open ${targetElement.code} coverage for ${targetStandard!.code}`,
      })
      .first()
      .click();

    await expect(
      page.getByRole("heading", { name: new RegExp(`${targetElement.code} .* ${targetStandard!.code}`) })
    ).toBeVisible();
    await expect(page.getByText("Requirement Details")).toBeVisible();
    await expect(page.getByText("Evidence Status")).toBeVisible();
  });

  test("auditor gets read-only merge access", async ({ page }) => {
    await loginThroughUi(page, demoState.users.auditor.email, demoState.password);
    await page.goto("/merge");

    await expect(page.getByText("Auditor access is read-only.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Coverage Matrix" })).toBeVisible();
    await expect(page.getByText("Project Coverage Matrix", { exact: true })).toBeVisible();
  });

  for (const user of [
    demoState.users.esg_manager,
    demoState.users.collector_energy,
    demoState.users.reviewer,
  ]) {
    test(`blocks merge screen for ${user.role} (${user.email})`, async ({ page }) => {
      await loginThroughUi(page, user.email, demoState.password);

      await expect(page.getByRole("link", { name: "Coverage Matrix" })).toHaveCount(0);
      await page.goto("/merge");
      await expect(page.getByText("Access denied")).toBeVisible();
      await expect(
        page.getByText("Coverage analysis is reserved for admin diagnostics and auditor review.")
      ).toBeVisible();
    });
  }

  test("platform admin with org admin binding can access coverage analysis", async ({ page }) => {
    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/merge");

    await expect(page.getByRole("heading", { name: "Coverage Matrix" })).toBeVisible();
    await expect(page.getByText("Project Coverage Matrix", { exact: true })).toBeVisible();
  });
});

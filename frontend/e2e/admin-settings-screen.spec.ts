import { expect, test, type APIRequestContext } from "@playwright/test";

import { loadDemoState, loginByApi, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();
const apiUrl = demoState.api_url!.replace("localhost", "127.0.0.1");

type Standard = { id: number; code: string; name: string };
type Section = { id: number; code: string | null; title: string };
type Disclosure = { id: number; code: string; title: string };
type RequirementItem = { id: number; item_code: string | null; name: string };

async function adminHeaders(request: APIRequestContext) {
  return loginByApi(request, demoState.users.admin.email, demoState.password);
}

async function apiPost<T>(request: APIRequestContext, url: string, headers: Record<string, string>, data: unknown) {
  const response = await request.post(url, { headers, data });
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as T;
}

async function createStandardStack(request: APIRequestContext, suffix: string) {
  const adminAuth = await adminHeaders(request);
  const standard = await apiPost<Standard>(request, `${apiUrl}/standards`, adminAuth.headers, {
    code: `UISTD-${suffix}`,
    name: `UI Standard ${suffix}`,
    version: "2026",
  });
  const section = await apiPost<Section>(request, `${apiUrl}/standards/${standard.id}/sections`, adminAuth.headers, {
    code: `SEC-${suffix}`,
    title: `Section ${suffix}`,
  });
  const disclosure = await apiPost<Disclosure>(request, `${apiUrl}/standards/${standard.id}/disclosures`, adminAuth.headers, {
    section_id: section.id,
    code: `DISC-${suffix}`,
    title: `Disclosure ${suffix}`,
    requirement_type: "quantitative",
    mandatory_level: "mandatory",
  });
  return { standard, section, disclosure, adminAuth };
}

async function createRequirementItem(request: APIRequestContext, disclosureId: number, suffix: string) {
  const adminAuth = await adminHeaders(request);
  return apiPost<RequirementItem>(request, `${apiUrl}/disclosures/${disclosureId}/items`, adminAuth.headers, {
    item_code: `ITEM-${suffix}`,
    name: `Requirement Item ${suffix}`,
    item_type: "metric",
    value_type: "number",
    unit_code: "tCO2e",
  });
}

test.describe("Screen 21-23 - Admin Settings", () => {
  test("platform admin creates a standard, section, and disclosure from standards screen", async ({ page }) => {
    const suffix = `${Date.now()}`;
    const standardCode = `UISTD-${suffix}`;
    const standardName = `UI Standard ${suffix}`;
    const sectionCode = `SEC-${suffix}`;
    const disclosureCode = `DISC-${suffix}`;

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings/standards");

    await expect(page.getByRole("heading", { name: "Standards Management" })).toBeVisible();
    await page.getByRole("button", { name: "Add Standard" }).click();
    let dialog = page.getByRole("dialog");
    await dialog.getByLabel("Code").fill(standardCode);
    await dialog.getByLabel("Name").fill(standardName);
    await dialog.getByLabel("Version").fill("2026");
    await dialog.getByRole("button", { name: "Create Standard" }).click();

    await expect(page.getByRole("button", { name: new RegExp(standardCode) })).toBeVisible();
    await expect(page.getByText(standardName).last()).toBeVisible();

    await page.getByRole("button", { name: "Add Section" }).click();
    dialog = page.getByRole("dialog");
    await dialog.getByLabel("Code").fill(sectionCode);
    await dialog.getByLabel("Title").fill(`Section ${suffix}`);
    await dialog.getByRole("button", { name: "Create Section" }).click();
    await expect(page.getByRole("cell", { name: sectionCode })).toBeVisible();

    await page.getByRole("button", { name: "Add Disclosure" }).click();
    dialog = page.getByRole("dialog");
    await dialog.getByLabel("Section").selectOption({
      label: `${sectionCode} - Section ${suffix}`,
    });
    await dialog.getByLabel("Code").fill(disclosureCode);
    await dialog.getByLabel("Title").fill(`Disclosure ${suffix}`);
    await dialog.getByRole("button", { name: "Create Disclosure" }).click();

    await expect(page.getByText(disclosureCode)).toBeVisible();
    await expect(page.getByRole("link", { name: "Manage Items" }).first()).toBeVisible();
  });

  test("platform admin manages requirement items for a disclosure", async ({ page, request }) => {
    const suffix = `${Date.now()}`;
    const { standard, disclosure } = await createStandardStack(request, suffix);

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto(`/settings/standards/${standard.id}/requirements?disclosureId=${disclosure.id}`);

    await expect(page.getByRole("heading", { name: "Requirement Items" })).toBeVisible();
    await expect(page.getByRole("button", { name: new RegExp(disclosure.code) }).first()).toBeVisible();

    await page.getByRole("button", { name: "Add Item" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Item Code").fill(`ITEM-${suffix}`);
    await dialog.getByLabel("Name").fill(`Requirement Item ${suffix}`);
    await dialog.getByRole("button", { name: "Create Item" }).click();

    await expect(page.getByText(`ITEM-${suffix}`)).toBeVisible();
    await expect(page.getByText(`Requirement Item ${suffix}`)).toBeVisible();
  });

  test("platform admin creates a shared element and links it to a requirement item", async ({ page, request }) => {
    const suffix = `${Date.now()}`;
    const { standard, disclosure } = await createStandardStack(request, suffix);
    const item = await createRequirementItem(request, disclosure.id, suffix);
    const elementCode = `SE-${suffix}`;
    const elementName = `Shared Element ${suffix}`;

    await loginThroughUi(page, demoState.users.admin.email, demoState.password);
    await page.goto("/settings/shared-elements");

    await expect(page.getByRole("heading", { name: "Shared Elements & Mappings" })).toBeVisible();
    await page.getByRole("button", { name: "Add Element" }).click();
    let dialog = page.getByRole("dialog");
    await dialog.getByLabel("Code").fill(elementCode);
    await dialog.getByLabel("Name").fill(elementName);
    await dialog.getByLabel("Default Unit").fill("tCO2e");
    await dialog.getByRole("button", { name: "Create Element" }).click();

    const elementRow = page.locator("tr", { has: page.getByText(elementCode, { exact: true }) }).first();
    await expect(elementRow).toBeVisible();
    await elementRow.getByRole("button", { name: "Link Mapping" }).click();
    dialog = page.getByRole("dialog");
    await dialog.getByLabel("Requirement Item").selectOption({
      label: `${standard.code} / ${disclosure.code} / ${item.item_code ?? item.id} - ${item.name}`,
    });
    await dialog.getByRole("button", { name: "Link Mapping" }).click();

    const coverageRow = page.locator("tr", { has: page.getByText(elementCode, { exact: true }) }).last();
    await expect(coverageRow).toBeVisible();
    await expect(coverageRow).toContainText("1");
    expect(item.id).toBeGreaterThan(0);
  });

  test("collector is blocked from admin settings screens", async ({ page }) => {
    await loginThroughUi(page, demoState.users.collector_energy.email, demoState.password);

    await expect(page.getByRole("link", { name: "Standards" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Shared Elements" })).toHaveCount(0);

    await page.goto("/settings/standards");
    await expect(page.getByText("Access denied")).toBeVisible();
    await page.goto("/settings/shared-elements");
    await expect(page.getByText("Access denied")).toBeVisible();
  });
});

import { expect, test } from "@playwright/test";

import {
  createTenantAdminUser,
  loadDemoState,
  loginThroughUi,
} from "./screen-helpers";

const demoState = loadDemoState();

test.describe("Framework catalog role journeys", () => {
  test("framework admin manages standards, data characteristics, and shared-element mappings", async ({
    page,
  }) => {
    const suffix = `framework-${Date.now()}`;
    const standardCode = `PW-FR-${suffix}`.toUpperCase();
    const standardName = `Playwright Framework Standard ${suffix}`;
    const editedStandardName = `${standardName} Updated`;
    const sectionCode = `SEC-${suffix}`.toUpperCase();
    const sectionTitle = `Climate section ${suffix}`;
    const disclosureCode = `DISC-${suffix}`.toUpperCase();
    const disclosureTitle = `Climate disclosure ${suffix}`;
    const itemCode = `ITEM-${suffix}`.toUpperCase();
    const itemName = `Gross emissions ${suffix}`;
    const sharedElementCode = `SE-${suffix}`.toUpperCase();
    const sharedElementName = `Shared emissions element ${suffix}`;
    const mappingLabel = `${standardCode} / ${disclosureCode} / ${itemCode} - ${itemName}`;

    await loginThroughUi(
      page,
      demoState.users.framework_admin.email,
      demoState.password,
      /\/platform\/framework$/,
    );

    await expect(page.getByRole("heading", { name: "Framework Catalog" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Framework Catalog" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Tenants" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Dashboard" })).toHaveCount(0);

    await page.getByRole("link", { name: "Open standards" }).click();
    await expect(page).toHaveURL(/\/platform\/framework\/standards$/, { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Standards Management" })).toBeVisible();

    await page.getByRole("button", { name: "Add Standard" }).click();
    const standardDialog = page.getByRole("dialog");
    await standardDialog.getByLabel("Code").fill(standardCode);
    await standardDialog.getByLabel("Name").fill(standardName);
    await standardDialog.getByLabel("Version").fill("2026.1");
    await standardDialog.getByRole("button", { name: "Create Standard" }).click();

    await expect(page.getByText(standardCode, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(standardName, { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Version 2026.1").first()).toBeVisible();

    await page.getByRole("button", { name: "Edit Standard" }).click();
    const editDialog = page.getByRole("dialog");
    await editDialog.getByLabel("Name").fill(editedStandardName);
    await editDialog.getByLabel("Version").fill("2026.2");
    await editDialog.getByRole("button", { name: "Save Standard" }).click();

    await expect(page.getByText(editedStandardName, { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Version 2026.2").first()).toBeVisible();

    await page.getByRole("button", { name: "Add Section" }).click();
    const sectionDialog = page.getByRole("dialog");
    await sectionDialog.getByLabel("Code").fill(sectionCode);
    await sectionDialog.getByLabel("Title").fill(sectionTitle);
    await sectionDialog.getByRole("button", { name: "Create Section" }).click();

    await expect(page.getByText(sectionCode, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(sectionTitle, { exact: true }).first()).toBeVisible();

    await page.getByRole("button", { name: "Add Disclosure" }).click();
    const disclosureDialog = page.getByRole("dialog");
    await disclosureDialog.getByLabel("Section").selectOption({ label: `${sectionCode} - ${sectionTitle}` });
    await disclosureDialog.getByLabel("Code").fill(disclosureCode);
    await disclosureDialog.getByLabel("Title").fill(disclosureTitle);
    await disclosureDialog
      .getByLabel("Description")
      .fill("Quantitative disclosure that feeds framework-wide reporting.");
    await disclosureDialog.getByLabel("Requirement Type").selectOption("quantitative");
    await disclosureDialog.getByLabel("Mandatory Level").selectOption("mandatory");
    await disclosureDialog.getByRole("button", { name: "Create Disclosure" }).click();

    const disclosureRow = page
      .locator("tr")
      .filter({ has: page.getByText(disclosureCode, { exact: true }) })
      .first();
    await expect(disclosureRow.getByText(disclosureTitle, { exact: true })).toBeVisible();
    await disclosureRow.getByRole("link", { name: "Manage Items" }).click();

    await expect(page).toHaveURL(/\/platform\/framework\/standards\/\d+\/requirements\?disclosureId=\d+$/);
    await expect(page.getByRole("heading", { name: "Requirement Items" })).toBeVisible();
    await expect(page.getByText(disclosureCode, { exact: true }).first()).toBeVisible();

    await page.getByRole("button", { name: "Add Item" }).click();
    const itemDialog = page.getByRole("dialog");
    await itemDialog.getByLabel("Item Code").fill(itemCode);
    await itemDialog.getByLabel("Name").fill(itemName);
    await itemDialog
      .getByLabel("Description")
      .fill("Numeric item with evidence requirement and a unit for mapped collection.");
    await itemDialog.getByLabel("Item Type").selectOption("metric");
    await itemDialog.getByLabel("Value Type").selectOption("number");
    await itemDialog.getByLabel("Unit Code").fill("tCO2e");
    await itemDialog.getByRole("checkbox", { name: "Evidence required" }).click();
    await itemDialog.getByRole("button", { name: "Create Item" }).click();

    const itemRow = page
      .locator("tr")
      .filter({ has: page.getByText(itemCode, { exact: true }) })
      .first();
    await expect(itemRow.getByText(itemName, { exact: true })).toBeVisible();
    await expect(itemRow.getByText("number", { exact: true })).toBeVisible();
    await expect(itemRow.getByText("Required", { exact: true })).toBeVisible();

    const mappingHistoryHref =
      (await itemRow.getByRole("link", { name: "Mapping History" }).getAttribute("href")) ?? "";
    expect(mappingHistoryHref).toContain("/platform/framework/mappings?");

    const requirementsUrl = page.url();
    await page.goto("/platform/framework/shared-elements");
    await expect(
      page.getByRole("heading", { name: "Shared Elements & Mappings" }),
    ).toBeVisible();

    await page.getByRole("button", { name: "Add Element" }).click();
    const elementDialog = page.getByRole("dialog");
    await elementDialog.getByLabel("Code").fill(sharedElementCode);
    await elementDialog.getByLabel("Name").fill(sharedElementName);
    await elementDialog.getByLabel("Concept Domain").selectOption("emissions");
    await elementDialog.getByLabel("Default Value Type").selectOption("number");
    await elementDialog.getByLabel("Default Unit").fill("tCO2e");
    await elementDialog.getByRole("button", { name: "Create Element" }).click();

    const sharedElementRow = page
      .locator("tr")
      .filter({ has: page.getByText(sharedElementCode, { exact: true }) })
      .first();
    await expect(sharedElementRow.getByText(sharedElementName, { exact: true })).toBeVisible();
    await expect(sharedElementRow.getByText("emissions", { exact: true })).toBeVisible();
    await expect(sharedElementRow.getByText("number", { exact: true })).toBeVisible();
    await expect(sharedElementRow.getByText("tCO2e", { exact: true })).toBeVisible();
    await expect(sharedElementRow.getByText("No", { exact: true })).toBeVisible();

    await sharedElementRow.getByRole("button", { name: "Add Dimension" }).click();
    const dimensionDialog = page.getByRole("dialog");
    await dimensionDialog.getByLabel("Dimension Type").selectOption("geography");
    await dimensionDialog.getByRole("switch", { name: "Required for data entry" }).click();
    await dimensionDialog.getByRole("button", { name: "Save Dimension" }).click();

    await expect(sharedElementRow.getByText("Geography required", { exact: true })).toBeVisible();

    await sharedElementRow.getByRole("button", { name: "Link Mapping" }).click();
    const mappingDialog = page.getByRole("dialog");
    await expect(mappingDialog.getByText("Loading requirement items...")).toHaveCount(0);
    await mappingDialog.getByLabel("Requirement Item").selectOption({ label: mappingLabel });
    await mappingDialog.getByLabel("Mapping Type").selectOption("full");
    await mappingDialog.getByRole("button", { name: "Link Mapping" }).click();

    await expect(sharedElementRow.getByText("Yes", { exact: true })).toBeVisible();
    const coverageRow = page
      .locator("tr")
      .filter({ has: page.getByText(sharedElementCode, { exact: true }) })
      .last();
    await expect(coverageRow.getByText(standardCode, { exact: true })).toBeVisible();
    await expect(coverageRow.getByText("1", { exact: true })).toBeVisible();

    await page.goto(requirementsUrl);
    const mappedItemRow = page
      .locator("tr")
      .filter({ has: page.getByText(itemCode, { exact: true }) })
      .first();
    await mappedItemRow.getByRole("link", { name: "Mapping History" }).click();

    await expect(page).toHaveURL(new RegExp(`${mappingHistoryHref.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));
    await expect(page.getByRole("heading", { name: "Mapping History" })).toBeVisible();
    await expect(page.getByText(itemName, { exact: true })).toBeVisible();
    await expect(page.getByText(sharedElementCode, { exact: true }).first()).toBeVisible();
    await expect(page.getByText("full", { exact: true }).first()).toBeVisible();

    await page.goto("/platform/framework/standards");
    await page
      .locator("button")
      .filter({ has: page.getByText(editedStandardName, { exact: true }) })
      .first()
      .click();
    await page.getByRole("button", { name: "Deactivate Standard" }).click();

    await expect(page.getByText("inactive", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Standard Inactive" })).toBeDisabled();

    await page.goto("/platform/framework");
    await expect(page.getByRole("heading", { name: "Framework Catalog" })).toBeVisible();
  });

  test("tenant admin cannot access framework catalog screens", async ({ page, request }) => {
    const suffix = `tenant-${Date.now()}`;
    const tenantAdmin = await createTenantAdminUser(request, suffix);

    await loginThroughUi(page, tenantAdmin.email, tenantAdmin.password, /\/dashboard$/);

    await expect(page.getByRole("link", { name: "Framework Catalog" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Tenants" })).toHaveCount(0);

    await page.goto("/settings/standards");
    await expect(page.getByRole("heading", { name: "Standards Management" })).toBeVisible();
    await expect(page.getByText("Access denied")).toBeVisible();
    await expect(
      page.getByText("Only framework admin and platform admin roles can manage standards."),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Standard" })).toHaveCount(0);

    await page.goto("/platform/framework");
    await expect(page.getByRole("heading", { name: "Framework Catalog" })).toBeVisible();
    await expect(page.getByText("Access denied")).toBeVisible();
    await expect(
      page.getByText(
        "Only framework admin and platform admin roles can open the framework catalog.",
      ),
    ).toBeVisible();
  });

  test("platform admin retains framework catalog access", async ({ page }) => {
    await loginThroughUi(
      page,
      demoState.users.admin.email,
      demoState.password,
      /\/(dashboard|platform\/tenants)(\/.*)?(\?.*)?$/,
    );

    await page.goto("/platform/framework");
    await expect(page.getByRole("heading", { name: "Framework Catalog" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Tenants" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open standards" })).toBeVisible();
  });
});

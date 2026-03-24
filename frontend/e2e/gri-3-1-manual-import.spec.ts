import { expect, test, type Browser, type Locator, type Page } from "@playwright/test";

import { loadDemoState, loginThroughUi } from "./screen-helpers";

const demoState = loadDemoState();
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3002";

const DISCLOSURE_TITLE = "Process to determine material topics";
const DISCLOSURE_CODE = "3-1";
const STANDARD_NAME = "GRI 3: Material Topics 2021";
const SECTION_TITLE = "Determining material topics";

type ScenarioItem = {
  itemCode: string;
  itemName: string;
  itemDescription: string;
  elementCode: string;
  elementName: string;
  assignee: "collector_energy" | "collector_climate";
  response: string;
};

function timestampSuffix() {
  return `${Date.now()}`.slice(-8);
}

async function openRolePage(browser: Browser, email: string) {
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  await loginThroughUi(page, email, demoState.password);
  return { context, page };
}

async function selectOptionContaining(locator: Locator, fragment: string) {
  let value = "";
  await expect
    .poll(
      async () => {
        value = await locator.evaluate(
          (node, expected) => {
            const option = Array.from((node as HTMLSelectElement).options).find(
              (candidate) =>
                candidate.value &&
                candidate.textContent?.includes(expected as string)
            );
            return option?.value ?? "";
          },
          fragment
        );
        return value;
      },
      { timeout: 20_000 }
    )
    .not.toBe("");

  await locator.selectOption(value);
}

async function selectFirstRealOption(locator: Locator) {
  let value = "";
  await expect
    .poll(
      async () => {
        value = await locator.evaluate((node) => {
          const option = Array.from((node as HTMLSelectElement).options).find(
            (candidate) => candidate.value
          );
          return option?.value ?? "";
        });
        return value;
      },
      { timeout: 10_000 }
    )
    .not.toBe("");

  await locator.selectOption(value);
}

function tableRowByText(page: Page, text: string) {
  return page.locator("tbody tr", { hasText: text }).first();
}

async function addRequirementItem(
  page: Page,
  item: Pick<ScenarioItem, "itemCode" | "itemName" | "itemDescription">
) {
  await page.getByRole("button", { name: "Add Item" }).click();
  const dialog = page.getByRole("dialog").last();
  await dialog.getByLabel("Item Code").fill(item.itemCode);
  await dialog.getByLabel("Name").fill(item.itemName);
  await dialog.getByLabel("Description").fill(item.itemDescription);
  await dialog.getByLabel("Item Type").selectOption("narrative");
  await dialog.getByLabel("Value Type").selectOption("text");
  await dialog.getByRole("button", { name: "Create Item" }).click();
  await expect(tableRowByText(page, item.itemCode)).toBeVisible({ timeout: 15_000 });
}

async function addAssignment(
  page: Page,
  projectId: number,
  item: Pick<ScenarioItem, "elementCode" | "elementName" | "assignee">
) {
  await page.goto(`/settings/assignments?projectId=${projectId}`);
  await expect(page.getByRole("heading", { name: "Assignments Matrix" })).toBeVisible();
  await page.getByRole("button", { name: "Add Assignment" }).click();
  const dialog = page.getByRole("dialog").last();
  await dialog.getByLabel("Element Code").fill(item.elementCode);
  await dialog.getByLabel("Element Name").fill(item.elementName);
  await selectOptionContaining(
    dialog.getByLabel("Entity"),
    demoState.entities.root.name
  );
  await dialog.getByLabel("Collector").selectOption({
    label: demoState.users[item.assignee].full_name!,
  });
  await dialog.getByLabel("Reviewer").selectOption({
    label: demoState.users.reviewer.full_name!,
  });
  await dialog.getByLabel("Deadline").fill("2026-05-31");
  await dialog.getByRole("button", { name: "Create Assignment" }).click();
  await expect(tableRowByText(page, item.elementCode)).toBeVisible({ timeout: 15_000 });
}

async function submitNarrativeDataPoint(
  page: Page,
  projectId: number,
  item: Pick<ScenarioItem, "elementCode" | "elementName" | "response">
) {
  await page.goto(`/collection?projectId=${projectId}`);
  await expect(page.getByRole("heading", { name: "Data Collection" })).toBeVisible();
  await page.getByPlaceholder("Search by code or name...").fill(item.elementCode);
  const row = tableRowByText(page, item.elementCode);
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByRole("button", { name: "Enter Data" }).click();

  await expect(page).toHaveURL(new RegExp(`/collection/\\d+\\?projectId=${projectId}$`), {
    timeout: 15_000,
  });
  const openedId = page.url().match(/\/collection\/(\d+)/)?.[1];
  expect(openedId).toBeTruthy();

  await expect(page.getByText(item.elementCode, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByLabel("Value").fill(item.response);
  await selectFirstRealOption(page.getByLabel("Methodology"));
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByRole("button", { name: "Run Gate Check" }).click();
  await expect(page.getByText("All checks passed. Ready to submit.")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByRole("button", { name: "Submit Data Point" }).click();
  await expect(page.getByText("Data point submitted successfully")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "Back to Collection" }).last().click();
  await expect(page).toHaveURL(new RegExp(`/collection\\?projectId=${projectId}$`), {
    timeout: 15_000,
  });

  return Number(openedId);
}

test.describe.configure({ mode: "serial" });

test("admin manually loads real GRI 3-1 and roles complete the UI flow", async ({
  browser,
}) => {
  const suffix = timestampSuffix();
  const standardCode = `GRI3-MT-${suffix}`;
  const sectionCode = `MT-${suffix}`;
  const projectName = `GRI 3-1 Manual Import ${suffix}`;

  const items: ScenarioItem[] = [
    {
      itemCode: "3-1.a",
      itemName: "Process followed to determine material topics",
      itemDescription:
        "Describe the process followed to determine material topics, including how actual and potential impacts were identified and how the significance threshold for reporting was defined.",
      elementCode: `GRI31_PROC_${suffix}`,
      elementName: `GRI 3-1 Process Overview ${suffix}`,
      assignee: "collector_energy",
      response:
        "Northwind ran a quarterly materiality cycle in 2025 covering owned operations, key suppliers, and joint ventures. The process combined internal impact assessments, grievance trends, external NGO reports, and board-level risk inputs before defining the reporting threshold.",
    },
    {
      itemCode: "3-1.a.i",
      itemName: "Identification of actual and potential impacts",
      itemDescription:
        "Explain how actual and potential, negative and positive impacts on the economy, environment, and people, including human rights, were identified across activities and business relationships.",
      elementCode: `GRI31_IDENT_${suffix}`,
      elementName: `GRI 3-1 Impact Identification ${suffix}`,
      assignee: "collector_energy",
      response:
        "The company identified impacts through environmental assessments, worker grievance channels, supplier due-diligence reviews, incident investigations, and public-source horizon scanning. The scope covered short- and long-term impacts across operations and priority business relationships.",
    },
    {
      itemCode: "3-1.a.ii",
      itemName: "Prioritization of impacts for reporting",
      itemDescription:
        "Explain how impacts were prioritized for reporting based on significance, including assumptions, thresholds, and any qualitative judgment applied in the prioritization process.",
      elementCode: `GRI31_PRIOR_${suffix}`,
      elementName: `GRI 3-1 Impact Prioritization ${suffix}`,
      assignee: "collector_climate",
      response:
        "Northwind prioritized impacts using severity, scale, scope, irremediability, and likelihood. Human-rights impacts were elevated where severity outweighed likelihood, and management tested the draft ranking with potential information users before final approval by governance bodies.",
    },
    {
      itemCode: "3-1.b",
      itemName: "Stakeholders and experts informing the process",
      itemDescription:
        "Specify the stakeholders and experts whose views informed the determination of material topics and how their input shaped the final list of reported topics.",
      elementCode: `GRI31_STAKE_${suffix}`,
      elementName: `GRI 3-1 Stakeholder Inputs ${suffix}`,
      assignee: "collector_climate",
      response:
        "The process incorporated interviews with investors, workforce representatives, community liaisons, customers, regulators, and external human-rights advisers. Conflicting priorities were resolved through documented scoring workshops chaired by the sustainability steering group.",
    },
  ];

  let projectId = 0;
  const createdDataPointIds: number[] = [];

  const adminSession = await openRolePage(browser, demoState.users.admin.email);
  try {
    const page = adminSession.page;

    await page.goto("/settings/standards");
    await expect(page.getByRole("heading", { name: "Standards Management" })).toBeVisible();
    await page.getByRole("button", { name: "Add Standard" }).click();
    let dialog = page.getByRole("dialog").last();
    await dialog.getByLabel("Code").fill(standardCode);
    await dialog.getByLabel("Name").fill(STANDARD_NAME);
    await dialog.getByLabel("Version").fill("2021");
    await dialog.getByRole("button", { name: "Create Standard" }).click();
    await expect(dialog).toBeHidden({ timeout: 15_000 });
    await page.reload();
    const standardTile = page
      .locator("button", { hasText: standardCode })
      .first();
    await expect(standardTile).toBeVisible({ timeout: 15_000 });
    await standardTile.click();
    await expect(page.getByRole("button", { name: "Add Section" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("button", { name: "Add Disclosure" })).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("button", { name: "Add Section" }).click();
    dialog = page.getByRole("dialog").last();
    await dialog.getByLabel("Code").fill(sectionCode);
    await dialog.getByLabel("Title").fill(SECTION_TITLE);
    await dialog.getByRole("button", { name: "Create Section" }).click();
    await expect(tableRowByText(page, sectionCode)).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Add Disclosure" }).click();
    dialog = page.getByRole("dialog").last();
    await selectOptionContaining(dialog.getByLabel("Section"), sectionCode);
    await dialog.getByLabel("Code").fill(DISCLOSURE_CODE);
    await dialog.getByLabel("Title").fill(DISCLOSURE_TITLE);
    await dialog.getByLabel("Description").fill(
      "The organization shall describe the process it has followed to determine its material topics, including how impacts were identified and prioritized for reporting, and specify the stakeholders and experts whose views informed the process."
    );
    await dialog.getByLabel("Requirement Type").selectOption("qualitative");
    await dialog.getByRole("button", { name: "Create Disclosure" }).click();
    const disclosureRow = tableRowByText(page, DISCLOSURE_CODE);
    await expect(disclosureRow).toBeVisible({ timeout: 15_000 });
    await expect(disclosureRow).toContainText(DISCLOSURE_TITLE);
    await disclosureRow.getByRole("link", { name: "Manage Items" }).click();

    await expect(page.getByRole("heading", { name: "Requirement Items" })).toBeVisible();
    for (const item of items) {
      await addRequirementItem(page, item);
    }

    await page.goto("/settings/shared-elements");
    await expect(
      page.getByRole("heading", { name: "Shared Elements & Mappings" })
    ).toBeVisible();

    for (const item of items) {
      await page.getByRole("button", { name: "Add Element" }).click();
      dialog = page.getByRole("dialog").last();
      await dialog.getByLabel("Code").fill(item.elementCode);
      await dialog.getByLabel("Name").fill(item.elementName);
      await dialog.getByLabel("Concept Domain").selectOption("governance");
      await dialog.getByLabel("Default Value Type").selectOption("text");
      await dialog.getByRole("button", { name: "Create Element" }).click();
      await expect(dialog).toBeHidden({ timeout: 15_000 });
      await page.reload();
      await expect(
        page.getByRole("heading", { name: "Shared Elements & Mappings" })
      ).toBeVisible();

      const elementRow = tableRowByText(page, item.elementCode);
      await expect(elementRow).toBeVisible({ timeout: 15_000 });
      await elementRow.getByRole("button", { name: "Link Mapping" }).click();

      const mappingLabel = `${standardCode} / ${DISCLOSURE_CODE} / ${item.itemCode} - ${item.itemName}`;
      dialog = page.getByRole("dialog").last();
      await selectOptionContaining(dialog.getByLabel("Requirement Item"), mappingLabel);
      await dialog.getByRole("button", { name: "Link Mapping" }).click();
      await expect(elementRow).toBeVisible({ timeout: 15_000 });
    }
  } finally {
    await adminSession.context.close();
  }

  const managerSession = await openRolePage(browser, demoState.users.esg_manager.email);
  try {
    const page = managerSession.page;

    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
    await page.getByRole("button", { name: "Create Project" }).click();
    await page.getByLabel("Project Name").fill(projectName);
    const createProjectResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/projects") &&
        response.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Create", exact: true }).click();
    const projectPayload = (await (await createProjectResponse).json()) as {
      id: number;
      name: string;
    };
    projectId = projectPayload.id;
    expect(projectId).toBeGreaterThan(0);
    await page.goto(`/projects/${projectId}/settings`);
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/settings$`), {
      timeout: 15_000,
    });

    await page.getByRole("tab", { name: "Standards" }).click();
    await page.getByRole("button", { name: "Add Standard" }).click();
    const dialog = page.getByRole("dialog").last();
    await selectOptionContaining(dialog.getByLabel("Standard"), standardCode);
    await dialog.getByRole("button", { name: "Add", exact: true }).click();
    await expect(dialog).toBeHidden({ timeout: 15_000 });
    await page.reload();
    await page.getByRole("tab", { name: "Standards" }).click();
    await expect(page.getByText(standardCode, { exact: true })).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("tab", { name: "Boundary" }).click();
    await selectOptionContaining(
      page.getByLabel("Boundary"),
      demoState.boundaries.sustainability.name
    );
    await page.getByRole("button", { name: "Save Snapshot" }).click();
    await expect(page.getByText("locked", { exact: true })).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("tab", { name: "General" }).click();
    await page.getByRole("button", { name: "Activate" }).click();
    await expect(page.getByRole("button", { name: "Start Review" })).toBeVisible({
      timeout: 15_000,
    });

    for (const item of items) {
      await addAssignment(page, projectId, item);
    }

    await expect(page.getByText("Total assignments:")).toBeVisible();
  } finally {
    await managerSession.context.close();
  }

  const collectorEnergySession = await openRolePage(
    browser,
    demoState.users.collector_energy.email
  );
  try {
    const page = collectorEnergySession.page;
    for (const item of items.filter((entry) => entry.assignee === "collector_energy")) {
      createdDataPointIds.push(await submitNarrativeDataPoint(page, projectId, item));
    }
  } finally {
    await collectorEnergySession.context.close();
  }

  const collectorClimateSession = await openRolePage(
    browser,
    demoState.users.collector_climate.email
  );
  try {
    const page = collectorClimateSession.page;
    for (const item of items.filter((entry) => entry.assignee === "collector_climate")) {
      createdDataPointIds.push(await submitNarrativeDataPoint(page, projectId, item));
    }
  } finally {
    await collectorClimateSession.context.close();
  }

  const reviewerSession = await openRolePage(browser, demoState.users.reviewer.email);
  try {
    const page = reviewerSession.page;
    await page.goto("/validation");
    await expect(page.getByRole("heading", { name: "Validation Review" })).toBeVisible();

    for (const item of items) {
      const reviewItem = page.getByRole("button", {
        name: new RegExp(item.elementCode),
      }).first();
      await expect(reviewItem).toBeVisible({ timeout: 20_000 });
      await reviewItem.click();
      await expect(page.getByRole("heading", { name: item.elementName })).toBeVisible();
      await page.getByRole("button", { name: "Approve", exact: true }).click();
      await expect(
        page.getByRole("button", { name: new RegExp(item.elementCode) })
      ).toHaveCount(0, { timeout: 20_000 });
    }
  } finally {
    await reviewerSession.context.close();
  }

  const auditorSession = await openRolePage(browser, demoState.users.auditor.email);
  try {
    const page = auditorSession.page;
    await page.goto("/audit");
    await expect(page.getByRole("heading", { name: "Audit Log" })).toBeVisible();
    await page.getByLabel("Entity Type").fill("DataPoint");
    await page.getByLabel("Entity ID").fill(String(createdDataPointIds[0]));
    await expect(page.locator("tbody tr").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("tbody")).toContainText(String(createdDataPointIds[0]));
    await expect(page.locator("tbody")).toContainText("data_point_approved");
    await page.locator("tbody tr").first().click();
    await expect(page.getByText("Request ID")).toBeVisible();
    await expect(page.getByText("Changes", { exact: true })).toBeVisible();
  } finally {
    await auditorSession.context.close();
  }
});

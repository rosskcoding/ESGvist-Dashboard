import { expect, test } from "@playwright/test";

function uniqueEmail(prefix: string) {
  return `${prefix}.${Date.now()}@users.example.com`;
}

test.describe("Screen 2 - Registration", () => {
  test("renders registration form and footer link", async ({ page }) => {
    await page.goto("/register");

    await expect(page.getByText("Create Account")).toBeVisible();
    await expect(page.getByText("Get started with ESGvist")).toBeVisible();
    await expect(page.getByLabel("Full Name")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Confirm Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Create account" })).toBeEnabled();
    await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
  });

  test("blocks submit when passwords do not match", async ({ page }) => {
    await page.goto("/register");

    await page.getByLabel("Full Name").fill("Mismatch User");
    await page.getByLabel("Email").fill(uniqueEmail("mismatch"));
    await page.getByLabel("Password", { exact: true }).fill("Test1234");
    await page.getByLabel("Confirm Password").fill("Different1234");
    await page.getByRole("checkbox").click();
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page.getByText("Passwords do not match")).toBeVisible();
    await expect(page).toHaveURL(/register/);
  });

  test("blocks submit when terms are not accepted", async ({ page }) => {
    await page.goto("/register");

    await page.getByLabel("Full Name").fill("Terms User");
    await page.getByLabel("Email").fill(uniqueEmail("terms"));
    await page.getByLabel("Password", { exact: true }).fill("Test1234");
    await page.getByLabel("Confirm Password").fill("Test1234");
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page.getByText("You must accept the terms and conditions")).toBeVisible();
    await expect(page).toHaveURL(/register/);
  });

  test("registers a new user and redirects to onboarding", async ({ page }) => {
    const email = uniqueEmail("register");

    await page.goto("/register");
    await page.getByLabel("Full Name").fill("Registered User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill("Test1234");
    await page.getByLabel("Confirm Password").fill("Test1234");
    await page.getByRole("checkbox").click();
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page).toHaveURL(/onboarding/, { timeout: 15_000 });

    const storage = await page.evaluate(() => ({
      accessToken: localStorage.getItem("access_token"),
      refreshToken: localStorage.getItem("refresh_token"),
    }));
    const accessCookie = (await page.context().cookies()).find(
      (cookie) => cookie.name === "access_token",
    );
    const refreshCookie = (await page.context().cookies()).find(
      (cookie) => cookie.name === "refresh_token",
    );

    expect(storage.accessToken).toBeNull();
    expect(storage.refreshToken).toBeNull();
    expect(accessCookie?.httpOnly).toBeTruthy();
    expect(refreshCookie?.httpOnly).toBeTruthy();
  });

  test("navigates back to login from footer link", async ({ page }) => {
    await page.goto("/register");
    await page.getByRole("link", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });
});

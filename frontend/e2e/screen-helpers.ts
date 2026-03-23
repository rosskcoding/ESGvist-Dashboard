import fs from "node:fs";
import path from "node:path";
import { expect, type Page } from "@playwright/test";

type DemoState = {
  password: string;
  api_url?: string;
  organization: {
    id: number;
    name: string;
  };
  users: Record<
    string,
    {
      email: string;
      role: string;
    }
  >;
};

const demoStatePath = path.resolve(__dirname, "..", "..", "artifacts", "demo", "demo-state.json");

export function loadDemoState(): DemoState {
  return JSON.parse(fs.readFileSync(demoStatePath, "utf-8")) as DemoState;
}

export async function loginThroughUi(page: Page, email: string, password: string) {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 15_000 });
}

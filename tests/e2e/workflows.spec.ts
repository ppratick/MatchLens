import { expect, test } from "@playwright/test";

test("synthetic review, corrections, undo/redo, pinned report, and restart", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore a synthetic demo" }).click();
  await expect(page.locator(".mini-stats strong").first()).toHaveText("14", { timeout: 60_000 });
  await expect(page.getByText("SYNTHETIC DEMO", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Play video", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause video", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Pause video", exact: true }).click();
  await page.getByRole("button", { name: "Goal Blue XI" }).click();
  await page.getByLabel("Review status").selectOption("rejected");
  await page.getByRole("button", { name: "Save moment" }).click();
  await expect(page.locator(".score-number")).toHaveText("0:0");
  await page.getByRole("button", { name: "Undo review edit" }).click();
  await expect(page.locator(".score-number")).toHaveText("0:1");
  await page.getByRole("button", { name: "Redo review edit" }).click();
  await expect(page.locator(".score-number")).toHaveText("0:0");
  await page.getByRole("button", { name: "Highlights & reports", exact: true }).click();
  await page.getByRole("button", { name: "Generate report" }).click();
  await expect(page.locator(".export-row")).toHaveCount(1, { timeout: 30_000 });
  const href = await page.getByRole("link", { name: "JSON", exact: true }).getAttribute("href");
  const report = await (await page.request.get(href!)).json();
  expect(report.statistics.score.away).toBe(0);
  expect(report.match.revision).toBe(report.statistics.revision);
  await page.reload();
  await page.getByRole("button", { name: /Recording preview SYNTHETIC DEMO/ }).click();
  await expect(page.locator(".score-number")).toHaveText("0:0");
  await page.getByRole("button", { name: "Players", exact: true }).click();
  await expect(page.getByRole("button", { name: "Edit identity" })).toHaveCount(14);
});

test("setup and match creation retain local capability boundaries", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Local setup", exact: true }).click();
  await expect(page.getByText("Not required", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Match library/ }).click();
  await page.getByRole("button", { name: "New match", exact: true }).click();
  await page.getByLabel("Match title").fill("Screen review fixture");
  await page.getByRole("button", { name: "Create match" }).click();
  await expect(page.getByRole("heading", { name: "Screen review fixture" })).toBeVisible();
  await page.getByRole("button", { name: "Capture", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

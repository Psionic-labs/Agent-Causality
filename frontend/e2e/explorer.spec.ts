import { expect, test } from "@playwright/test";

/* One browser-level acceptance path over the bundled demo trace:
 * load -> graph -> select a node -> timeline -> analysis tab -> screenshot.
 * API status failures and browser console errors are collected as evidence. */
test("explorer loads the demo and supports graph, timeline, and tabs", async ({
  page,
}, testInfo) => {
  const browserErrors: string[] = [];
  const apiFailures: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("response", (response) => {
    if (response.url().includes("/api/") && !response.ok()) {
      apiFailures.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto("/");

  await expect(page).toHaveTitle("Agent-Causality DAG Explorer");
  await expect(page.getByRole("heading", { name: "DAG Explorer" })).toBeVisible();
  await expect(page.locator("#dataset-line")).toContainText("demo:failed_test_retry");
  await expect(page.locator("#dataset-line")).toContainText("10 events");
  await expect(page.locator("#failure-banner")).toHaveText("Resolved");

  const nodes = page.locator("#viewport > g");
  expect(await nodes.count()).toBeGreaterThan(0);
  await expect(page.locator("#dag")).toBeVisible();

  // The default selection is the failure target, so the inspector must resolve
  // an event without any user click.
  await expect(page.locator("#event-detail")).toContainText("Event ID");

  // Selecting another node updates the shared selection status and inspector.
  await nodes.first().click();
  await expect(page.getByRole("status")).toContainText("Selected event");

  await page.getByRole("button", { name: "Timeline" }).click();
  await expect(page.locator("#timeline")).toBeVisible();
  await expect(page.locator("#timeline .clip").first()).toBeVisible();

  await page.locator('[data-tab="metrics"]').click();
  await expect(page.locator("#tab-metrics")).toBeVisible();
  await expect(page.locator("#tab-metrics")).toContainText("Dataset events");

  await page.locator('[data-tab="evidence"]').click();
  await expect(page.locator("#tab-evidence")).toBeVisible();
  await expect(page.locator("#tab-evidence")).toContainText("Backend evidence summary");

  await page.getByRole("button", { name: "Graph" }).click();
  await expect(page.locator("#dag")).toBeVisible();

  const screenshot = testInfo.outputPath("explorer.png");
  await page.screenshot({ path: screenshot, fullPage: true });
  console.log(`screenshot: ${screenshot}`);

  expect(apiFailures, "API requests returned errors").toEqual([]);
  expect(browserErrors, "browser console errors").toEqual([]);
});

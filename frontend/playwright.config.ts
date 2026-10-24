import { defineConfig, devices } from "@playwright/test";

/* Browser smoke test for the exported Explorer. The Python server serves the
 * committed static bundle, so this exercises the same artifact users install.
 * tools/verify/verify.py starts that server and passes EXPLORER_URL; running
 * `npm run test:e2e` directly starts a server on the default port instead. */
const externalBaseURL = process.env.EXPLORER_URL;

export default defineConfig({
  testDir: "./e2e",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR ?? "../tools/verify/artifacts/playwright",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: externalBaseURL ?? "http://127.0.0.1:8767",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: externalBaseURL
    ? undefined
    : {
        command: "uv run python -m explorer.server --port 8767",
        cwd: "..",
        url: "http://127.0.0.1:8767/api/overview",
        reuseExistingServer: true,
        timeout: 30_000,
      },
});

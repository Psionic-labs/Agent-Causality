import { defineConfig, devices } from "@playwright/test";

/* Browser smoke test for the exported Explorer. The Python server serves the
 * committed static bundle, so this exercises the same artifact users install.
 * tools/verify/verify.py starts that server on a free port and passes
 * EXPLORER_URL. To run it by hand, start `uv run python -m explorer.server
 * --port 0`, then set EXPLORER_URL to the printed address. */
const externalBaseURL = process.env.EXPLORER_URL;

if (!externalBaseURL) {
  throw new Error(
    "EXPLORER_URL is required: run `uv run python -m explorer.server --port 0` and pass the printed address.",
  );
}

export default defineConfig({
  testDir: "./e2e",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR ?? "../tools/verify/artifacts/playwright",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: externalBaseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
});

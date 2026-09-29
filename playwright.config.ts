import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90_000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8877",
    browserName: "chromium",
    channel: "chrome",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "PYTHONPATH=src .venv/bin/python scripts/test_server.py",
    url: "http://127.0.0.1:8877/api/session",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});

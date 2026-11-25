import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  retries: 0,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:8127",
    channel: process.env.OMNIS_CHROME_CHANNEL || undefined,
    headless: true,
    viewport: { width: 1440, height: 960 },
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      '"' +
      (process.env.OMNIS_PYTHON || "python") +
      '" ../scripts/test_server.py',
    url: "http://127.0.0.1:8127/api/config",
    timeout: 90000,
    reuseExistingServer: false,
  },
});

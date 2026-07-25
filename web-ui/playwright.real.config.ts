import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./real-e2e",
  outputDir: "./test-results-real",
  reporter: "list",
  fullyParallel: false,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.REAL_BASE_URL ?? "http://host.docker.internal:8080",
    ...(process.env.P3_BROWSER_CHANNEL === "chrome" ? { channel: "chrome" as const } : {}),
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    colorScheme: "light"
  },
  projects: [
    { name: "real-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "real-mobile", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true } }
  ]
});

import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright smoke config. Runs the e2e/ specs against a locally-started dev
 * server. Not part of the required CI job (it needs a browser binary +
 * `npx playwright install chromium` and a Clerk publishable key), so it runs on
 * demand via `npm run test:e2e`.
 */
const PORT = 3000;

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      // A test-format Clerk key so ClerkProvider initializes without a real instance.
      VITE_CLERK_PUBLISHABLE_KEY:
        process.env.VITE_CLERK_PUBLISHABLE_KEY ?? 'pk_test_ci_placeholder',
      VITE_API_URL: process.env.VITE_API_URL ?? 'http://127.0.0.1:8000',
    },
  },
});

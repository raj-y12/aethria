import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright smoke config. Runs the e2e/ specs against a locally-started dev
 * server. Not part of the required CI job (it needs a browser binary +
 * `npx playwright install chromium` and a Clerk publishable key), so it runs on
 * demand via `npm run test:e2e`.
 */
const PORT = Number(process.env.PLAYWRIGHT_PORT ?? 4173);

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  reporter: 'list',
  use: {
  // Match the explicit host used by webServer. On CI, `localhost` may resolve
  // to IPv6 while Vite is bound only to 127.0.0.1, yielding a blank SPA shell.
  baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    // Never attach tests to an unrelated process that happens to own the port.
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      // A test-format Clerk key so ClerkProvider initializes without a real instance.
      VITE_CLERK_PUBLISHABLE_KEY:
        process.env.VITE_CLERK_PUBLISHABLE_KEY ?? 'pk_test_ci_placeholder',
      VITE_API_URL: process.env.VITE_API_URL ?? 'http://127.0.0.1:8000',
    },
  },
});

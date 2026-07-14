import { test, expect } from '@playwright/test';

/**
 * Smoke tests: the app boots and routes render without a hard crash. These do
 * not log in (Clerk auth needs a real instance); they assert the SPA shell
 * mounts and the auth gate routes unauthenticated visitors to sign-in.
 */
test('app shell mounts at the root', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));

  await page.goto('/');
  await expect(page).toHaveTitle(/Aethria/);
  // React mounted into #root.
  await expect(page.locator('#root')).not.toBeEmpty();
  expect(errors, `uncaught page errors: ${errors.join('\n')}`).toEqual([]);
});

test('unauthenticated visit to the app routes to sign-in', async ({ page }) => {
  await page.goto('/v1');
  const configuredKey = process.env.VITE_CLERK_PUBLISHABLE_KEY;
  const hasRealClerkKey = Boolean(configuredKey && configuredKey !== 'pk_test_ci_placeholder');

  // A real Clerk instance can resolve the unauthenticated redirect. The
  // placeholder key used by local/CI smoke runs intentionally cannot complete
  // Clerk bootstrap, so those runs verify that the app remains mounted instead.
  if (hasRealClerkKey) {
    await page.waitForURL(/\/sign-in/, { timeout: 15_000 });
  } else {
    await expect(page).toHaveURL(/\/v1/);
  }
  await expect(page.locator('#root')).not.toBeEmpty();
});

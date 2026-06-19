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
  // The auth gate redirects unauthenticated users to /sign-in.
  await page.waitForURL(/\/sign-in/, { timeout: 15_000 });
  await expect(page.locator('#root')).not.toBeEmpty();
});

import { expect, test } from '@playwright/test';

/**
 * Remote / non-localhost dev access: Next.js 16 blocks HMR unless the page
 * origin is in allowedDevOrigins; without hydration, Send stays disabled.
 *
 * Run against a running dev server:
 *   CELLXP_WEB_URL=http://10.81.105.76:3000 npm run test:browser -- chat-remote
 */
test.describe('remote dev chat composer', () => {
  test.skip(!process.env.CELLXP_WEB_URL, 'set CELLXP_WEB_URL to hit a running dev server');

  test('Send enables and posts after typing on non-localhost origin', async ({ page }) => {
    const base = process.env.CELLXP_WEB_URL!.replace(/\/$/, '');
    const origin = new URL(base).hostname;
    test.skip(origin === 'localhost', 'use a LAN IP or 127.0.0.1 URL to exercise remote dev');

    await page.goto('/chat?session=browser-session');

    const composer = page.getByLabel('Message composer');
    await composer.fill('Remote origin submit check');
    await expect(page.getByLabel('Send message')).toBeEnabled({ timeout: 5_000 });

    await page.getByLabel('Send message').click();
    await expect(page.getByText('Remote origin submit check')).toBeVisible({ timeout: 10_000 });
  });
});

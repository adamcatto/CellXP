import { expect, test } from '@playwright/test';

/**
 * Exercises the user's running dev stack (no API mocks).
 * Run: CELLXP_WEB_URL=http://localhost:3000 npm run test:browser -- chat-live
 */
test.describe('live stack chat submission', () => {
  test.skip(!process.env.CELLXP_WEB_URL, 'set CELLXP_WEB_URL to hit a running dev server');

  test('Send and Enter post a user turn', async ({ page }) => {
    await page.goto('/chat?session=browser-session');

    const composer = page.getByLabel('Message composer');
    await composer.click();
    await composer.type('Playwright live submit check');
    await page.getByLabel('Send message').click();

    await expect(page.getByText('Playwright live submit check')).toBeVisible({ timeout: 10_000 });
  });
});

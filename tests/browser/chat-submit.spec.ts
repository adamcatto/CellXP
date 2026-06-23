import { expect, test } from '@playwright/test';

import { mockRun, submitMessage } from './helpers';

test.describe('chat composer submission', () => {
  test.beforeEach(async ({ page }) => {
    await mockRun(page, 'run-submit', [
      { type: 'message.delta', data: { token: 'Acknowledged.' } },
      { type: 'run.completed', data: {} },
    ]);
    await page.goto('/chat?session=browser-session');
  });

  test('submits via Send button after typing', async ({ page }) => {
    const composer = page.getByLabel('Message composer');
    await composer.click();
    await composer.type('What does BRCA1 do?');
    await page.getByLabel('Send message').click();

    await expect(page.getByText('What does BRCA1 do?')).toBeVisible();
    await expect(page.getByText('Acknowledged.')).toBeVisible();
  });

  test('submits via Enter key', async ({ page }) => {
    const composer = page.getByLabel('Message composer');
    await composer.click();
    await composer.type('Explain PCSK9');
    await composer.press('Enter');

    await expect(page.getByText('Explain PCSK9')).toBeVisible();
    await expect(page.getByText('Acknowledged.')).toBeVisible();
  });

  test('does not block gene symbols on paste', async ({ page }) => {
    const composer = page.getByLabel('Message composer');
    await composer.click();
    // Playwright fill can dispatch paste; gene symbols must not require format confirmation.
    await composer.fill('CYP2D6');
    await expect(page.getByText(/Detected .* content/)).toHaveCount(0);
    await expect(page.getByLabel('Send message')).toBeEnabled();
    await page.getByLabel('Send message').click();

    await expect(page.getByText('CYP2D6')).toBeVisible();
    await expect(page.getByText('Acknowledged.')).toBeVisible();
  });
});

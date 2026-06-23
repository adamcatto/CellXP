import { expect, test } from '@playwright/test';

import { mockRun } from './helpers';

const API = (() => {
  const configured =
    process.env.CELLXP_API_BASE ??
    process.env.NEXT_PUBLIC_API_BASE ??
    '/api/v1';
  if (configured.startsWith('/')) {
    const web = process.env.CELLXP_WEB_URL ?? 'http://localhost:3000';
    return `${web.replace(/\/$/, '')}${configured}`;
  }
  return configured;
})();

const NEW_SESSION = {
  id: 'auto-created-session',
  title: 'New session',
  type: 'general',
  defaults: {
    organism: 'hsapiens',
    assembly: 'GRCh38',
    review_posture: 'standard',
  },
  revision: 0,
  created_at: '2026-06-23T00:00:00Z',
  updated_at: '2026-06-23T00:00:00Z',
  run_count: 0,
  artifact_count: 0,
};

test.describe('chat session bootstrap', () => {
  test.beforeEach(async ({ page }) => {
    await page.route(`${API}/sessions`, async route => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(NEW_SESSION),
        });
        return;
      }
      await route.continue();
    });
    await page.route(`${API}/sessions/${NEW_SESSION.id}`, async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(NEW_SESSION),
      });
    });
    await mockRun(page, 'run-bootstrap', [
      { type: 'message.delta', data: { token: 'Hello.' } },
      { type: 'run.completed', data: {} },
    ]);
  });

  test('creates a session when /chat has no ?session=', async ({ page }) => {
    await page.goto('/chat');
    await expect(page).toHaveURL(/session=auto-created-session/, { timeout: 10_000 });

    const composer = page.getByLabel('Message composer');
    await composer.fill('First message without session param');
    await page.getByLabel('Send message').click();

    await expect(page.getByText('First message without session param')).toBeVisible();
    await expect(page.getByText('Hello.')).toBeVisible();
  });
});

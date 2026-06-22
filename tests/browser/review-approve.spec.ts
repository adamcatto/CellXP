import { expect, test } from '@playwright/test';

import { mockRun, submitMessage } from './helpers';

test('keeps actionable CRISPR output behind review and records approval', async ({ page }) => {
  let decision: unknown;
  const artifact = {
    id: 'guide-pool-1', type: 'guide_table', title: 'PCSK9 guide candidates',
    status: 'ready', run_id: 'run-review', actionable: true,
    review_status: 'pending', created_at: '2026-06-22T00:00:00Z',
  };
  await mockRun(page, 'run-review', [
    { type: 'artifact.added', data: artifact },
    {
      type: 'review.requested',
      data: {
        id: 'review-1', run_id: 'run-review', artifact_ref: artifact,
        rationale: 'Guide sequences are build-ready actionable biology.',
        risks: ['Genome-wide off-target activity requires review.'],
      },
    },
  ], async route => {
    if (route.request().url().endsWith('/reviews/review-1/decision')) {
      decision = route.request().postDataJSON();
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fallback();
  });

  await page.goto('/chat?session=browser-session');
  await submitMessage(page, 'Design CRISPR guides for PCSK9');
  await expect(page.getByText('Review required — candidate output')).toBeVisible();
  await expect(page.getByText('PCSK9 guide candidates').first()).toBeVisible();
  await page.getByPlaceholder('Optional note…').fill('Reviewed target and off-target context.');
  await page.getByRole('button', { name: 'Approve' }).click();
  await expect.poll(() => decision).toEqual({
    decision: 'approve',
    note: 'Reviewed target and off-target context.',
    expected_run_status: 'awaiting_review',
  });
});

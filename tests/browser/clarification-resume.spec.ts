import { expect, test } from '@playwright/test';

import { mockRun, submitMessage } from './helpers';

test('answers an assembly clarification through the resume endpoint', async ({ page }) => {
  let answer: unknown;
  await mockRun(page, 'run-clarify', [
    {
      type: 'clarification.requested',
      data: {
        id: 'clar-1', run_id: 'run-clarify', question: 'Which assembly should be used?',
        options: [
          { id: 'grch38', label: 'GRCh38', is_recommended: true },
          { id: 'grch37', label: 'GRCh37' },
        ],
        allow_multiple: false, allow_freeform: false,
      },
    },
  ], async route => {
    if (route.request().url().endsWith('/clarifications/clar-1/answer')) {
      answer = route.request().postDataJSON();
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fallback();
  });

  await page.goto('/chat?session=browser-session');
  await submitMessage(page, 'Interpret chr1:100 A>G');
  await expect(page.getByText('Which assembly should be used?')).toBeVisible();
  await page.getByRole('button', { name: /GRCh38/ }).click();
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect.poll(() => answer).toEqual({ selected_option_ids: ['grch38'] });
});

import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { mockRun, submitMessage } from './helpers';

test('streams a variant answer with inspectable evidence and artifacts', async ({ page }) => {
  await mockRun(page, 'run-variant', [
    { type: 'intent.classified', data: { label: 'variant_effect' } },
    {
      type: 'step.started',
      data: { step_id: 'step-1', label: 'Score variant', tool: 'alphagenome' },
    },
    {
      type: 'evidence.added',
      data: {
        id: 'evidence-1', run_id: 'run-variant', kind: 'model_output',
        source: 'alphagenome', title: 'Regulatory effect prediction',
      },
    },
    {
      type: 'artifact.added',
      data: {
        id: 'artifact-1', type: 'genome_track', title: 'Regulatory activity',
        status: 'ready', run_id: 'run-variant', actionable: false,
        review_status: 'not_required', created_at: '2026-06-22T00:00:00Z',
      },
    },
    { type: 'message.delta', data: { token: 'The variant has tissue-specific regulatory evidence.' } },
    { type: 'run.completed', data: { model: 'alphagenome', provider: 'worker' } },
  ]);

  await page.goto('/chat?session=browser-session');
  await submitMessage(page, 'Could rs1421085 alter regulatory activity?');

  await expect(page.getByText('The variant has tissue-specific regulatory evidence.')).toBeVisible();
  await expect(page.getByRole('link', { name: /Open Genome Track: Regulatory activity/i })).toBeVisible();
  await expect(page.getByText('variant_effect')).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.filter(item => ['critical', 'serious'].includes(item.impact ?? '')))
    .toEqual([]);
});

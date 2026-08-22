import path from 'node:path';

import { expect, test } from '@playwright/test';

const SCREENSHOTS = path.resolve(
  __dirname,
  '../../documentation/assets/screenshots',
);
const UPDATE = process.env.UPDATE_README_SCREENSHOTS === '1';

test.use({
  colorScheme: 'dark',
  viewport: { width: 1440, height: 900 },
});

test.skip(!UPDATE, 'Set UPDATE_README_SCREENSHOTS=1 to regenerate README screenshots.');

test('captures CopilotKit clarification in the biological workspace', async ({ page }) => {
  await page.goto('/chat');
  await expect(page).toHaveURL(/session=/, { timeout: 15_000 });

  const composer = page.getByPlaceholder(
    'Ask about a gene, variant, structure, pathway, or analysis…',
  );
  await composer.fill('Help me analyze this biological result');
  const send = page.getByTestId('copilot-send-button');
  await expect(send).toBeEnabled({ timeout: 15_000 });
  await send.click();

  await expect(
    page.getByText('What kind of analysis should CellXP perform?'),
  ).toBeVisible({ timeout: 30_000 });
  await page.screenshot({
    path: path.join(SCREENSHOTS, 'copilotkit-clarification.png'),
    animations: 'disabled',
  });
});

test('captures the confidence-colored structure artifact', async ({ page }) => {
  await page.route('**/api/v1/artifacts/demo-structure', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(structureManifest()),
    });
  });

  await page.goto('/artifacts/demo-structure');
  await expect(
    page.getByRole('img', { name: 'Rotatable structure coordinate preview' }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(SCREENSHOTS, 'structure-artifact.png'),
    animations: 'disabled',
  });
});

function structureManifest() {
  const now = '2026-08-22T00:00:00Z';
  return {
    id: 'demo-structure',
    schema_version: '1.0',
    payload_schema: 'cellxp.structure_3d/1.0',
    type: 'structure_3d',
    title: 'Predicted regulatory protein structure',
    description: 'Confidence-colored structure preview generated from a deterministic fixture.',
    status: 'ready',
    revision: 1,
    session_id: 'readme-demo',
    run_id: 'readme-demo-run',
    evidence_ids: ['evidence-structure-1'],
    source_artifact_ids: [],
    summary: { residues: 72, mean_confidence: 0.84 },
    payload: {
      schema: 'structure_3d',
      version: '1.0',
      data: { pdb: pdbHelix() },
    },
    coordinate_frame: {
      kind: 'structure',
      chain_map: { A: 'regulatory-domain' },
    },
    confidence: {
      value: 0.84,
      band: 'high',
      model: 'deterministic-readme-fixture',
    },
    limitations: ['Fixture coordinates demonstrate the renderer, not a biological prediction.'],
    transform_notes: [],
    interactions: [{ kind: 'select', label: 'Select residue' }],
    exports: [{ format: 'pdb', label: 'PDB', media_type: 'chemical/x-pdb' }],
    accessibility: {
      summary_text: 'A 72-residue confidence-colored structure with one chain.',
      alt: 'Confidence-colored helical protein structure.',
    },
    actionable: false,
    review_status: 'not_required',
    created_at: now,
    updated_at: now,
  };
}

function pdbHelix(): string {
  const lines = Array.from({ length: 72 }, (_, index) => {
    const residue = index + 1;
    const angle = index * 0.52;
    const radius = 8 + Math.sin(index * 0.19) * 2.5;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    const z = (index - 36) * 0.72 + Math.sin(index * 0.31) * 3;
    const confidence = 58 + ((index * 17) % 40);
    return [
      'ATOM  ',
      String(residue).padStart(5),
      '  CA  ALA A',
      String(residue).padStart(4),
      '    ',
      x.toFixed(3).padStart(8),
      y.toFixed(3).padStart(8),
      z.toFixed(3).padStart(8),
      '  1.00',
      confidence.toFixed(2).padStart(6),
      '           C',
    ].join('');
  });
  return `${lines.join('\n')}\nEND\n`;
}

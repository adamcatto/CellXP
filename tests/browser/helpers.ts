import type { Page, Route } from '@playwright/test';

function resolveApiBase(): string {
  const configured =
    process.env.CELLXP_API_BASE ??
    process.env.NEXT_PUBLIC_API_BASE ??
    '/api/v1';
  if (configured.startsWith('/')) {
    const web = process.env.CELLXP_WEB_URL ?? 'http://localhost:3000';
    return `${web.replace(/\/$/, '')}${configured}`;
  }
  return configured;
}

const API = resolveApiBase();

export interface MockEvent {
  type: string;
  data: Record<string, unknown>;
}

function eventFrame(runId: string, event: MockEvent, index: number): string {
  return [
    `id: ${index + 1}`,
    `event: ${event.type}`,
    `data: ${JSON.stringify({
      schema_version: '1.0',
      run_id: runId,
      seq: index + 1,
      at: '2026-06-22T00:00:00Z',
      data: event.data,
    })}`,
    '',
  ].join('\n');
}

export async function mockRun(
  page: Page,
  runId: string,
  events: MockEvent[],
  onMutation?: (route: Route) => Promise<void>,
): Promise<void> {
  await page.route(`${API}/sessions/*/runs`, async route => {
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: runId,
        session_id: 'browser-session',
        status: 'queued',
        stream_url: `${API}/runs/${runId}/events`,
        created_at: '2026-06-22T00:00:00Z',
      }),
    });
  });
  await page.route(`${API}/runs/${runId}/events`, async route => {
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream',
        'cache-control': 'no-cache',
      },
      body: `${events.map((event, index) => eventFrame(runId, event, index)).join('\n')}\n`,
    });
  });
  if (onMutation) {
    await page.route(`${API}/runs/${runId}/**`, onMutation);
  }
}

export async function submitMessage(page: Page, message: string): Promise<void> {
  await page.getByLabel('Message composer').fill(message);
  await page.getByLabel('Send message').click();
}

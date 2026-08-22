import { HttpAgent } from '@ag-ui/client';
import {
  CopilotRuntime,
  createCopilotRuntimeHandler,
} from '@copilotkit/runtime/v2';

const backendBase = (
  process.env.CELLXP_API_PROXY_TARGET ?? 'http://127.0.0.1:8001'
).replace(/\/+$/, '');

const runtime = new CopilotRuntime({
  agents: {
    cellxp: new HttpAgent({
      url: process.env.CELLXP_AG_UI_URL ?? `${backendBase}/ag-ui`,
    }),
  },
  telemetryProperties: {
    product: 'cellxp',
    integration: 'ag-ui',
  },
});

const handler = createCopilotRuntimeHandler({
  runtime,
  basePath: '/api/copilotkit',
});

export const dynamic = 'force-dynamic';
export const GET = handler;
export const POST = handler;
export const OPTIONS = handler;

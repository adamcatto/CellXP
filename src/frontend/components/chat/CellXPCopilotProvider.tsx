'use client';

import { CopilotKit } from '@copilotkit/react-core/v2';
import type { ReactNode } from 'react';

interface CellXPCopilotProviderProps {
  children: ReactNode;
  sessionId: string;
}

/**
 * Same-origin CopilotKit boundary.
 *
 * The Next.js runtime brokers AG-UI traffic to FastAPI; CellXP remains the source of truth for
 * session identity, run state, artifacts, and review decisions.
 */
export function CellXPCopilotProvider({
  children,
  sessionId,
}: CellXPCopilotProviderProps) {
  return (
    <CopilotKit
      agent="cellxp"
      threadId={sessionId}
      runtimeUrl="/api/copilotkit"
      useSingleEndpoint={false}
      enableInspector={process.env.NODE_ENV === 'development'}
      showDevConsole={process.env.NODE_ENV === 'development'}
    >
      {children}
    </CopilotKit>
  );
}

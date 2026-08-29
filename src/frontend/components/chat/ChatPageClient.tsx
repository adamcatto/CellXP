'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { WorkspaceLayout } from '../workspace/WorkspaceLayout';
import { api } from '../../lib/api';
import type { SessionSummary } from '../../lib/types';
import { CellXPCopilotProvider } from './CellXPCopilotProvider';

interface ChatPageClientProps {
  sessionId?: string;
}

function placeholderSession(id: string): SessionSummary {
  return {
    id,
    title: 'New session',
    type: 'general',
    defaults: {
      organism: 'hsapiens',
      assembly: 'GRCh38',
      review_posture: 'standard',
    },
    revision: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    run_count: 0,
    artifact_count: 0,
  };
}

function isNotFound(err: unknown): boolean {
  return typeof err === 'object' && err !== null && 'status' in err && (err as { status: number }).status === 404;
}

export function ChatPageClient({ sessionId }: ChatPageClientProps) {
  const router = useRouter();
  const [session, setSession] = useState<SessionSummary | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function ensureSession() {
      if (!sessionId) {
        try {
          const created = await api.sessions.create({ type: 'general', title: 'New session' });
          if (!cancelled) router.replace(`/chat?session=${created.id}`);
        } catch {
          if (!cancelled) setSession(placeholderSession('local-session'));
        }
        return;
      }

      try {
        const fetched = await api.sessions.get(sessionId);
        if (!cancelled) setSession(fetched);
      } catch (err) {
        if (isNotFound(err)) {
          try {
            const created = await api.sessions.create({ type: 'general', title: 'New session' });
            if (!cancelled) router.replace(`/chat?session=${created.id}`);
          } catch {
            if (!cancelled) setSession(placeholderSession(sessionId));
          }
          return;
        }
        if (!cancelled) setSession(placeholderSession(sessionId));
      }
    }

    void ensureSession();
    return () => {
      cancelled = true;
    };
  }, [sessionId, router]);

  if (!session) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          color: 'var(--text-muted, #888)',
        }}
      >
        Loading session…
      </div>
    );
  }

  return (
    <CellXPCopilotProvider sessionId={session.id}>
      <WorkspaceLayout session={session} />
    </CellXPCopilotProvider>
  );
}

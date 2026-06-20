// Workspace page — renders the full three-column workspace for a session.
// Session ID comes from the URL search param `?session=<id>`.
// If no session ID is given, a default general session is assumed so the
// page renders even before sessions are created.

import { WorkspaceLayout } from '../../components/workspace/WorkspaceLayout';
import type { SessionSummary } from '../../lib/types';

interface ChatPageProps {
  searchParams?: Promise<{ session?: string }>;
}

// Placeholder session for local development before the backend is running.
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

export default async function ChatPage({ searchParams }: ChatPageProps) {
  const params = await searchParams;
  const sessionId = params?.session ?? 'local-session';
  // In production, fetch from GET /sessions/{id}; for now use a placeholder
  // so the page renders when the backend is not yet running.
  const session = placeholderSession(sessionId);

  return <WorkspaceLayout session={session} />;
}

// Run detail page — full-page run inspector for deep-linked runs.
// Accessible at /runs/<run-id>; embeds the RunInspector component.

import { RunInspector } from '../../../components/workspace/RunInspector';

interface RunDetailPageProps {
  params: Promise<{ runId: string }>;
}

export default async function RunDetailPage({ params }: RunDetailPageProps) {
  const { runId } = await params;
  return (
    <main
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        background: 'var(--bg)',
        color: 'var(--text)',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <header
        style={{
          padding: '10px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <a
          href="/chat"
          style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: 13 }}
        >
          ← Back to workspace
        </a>
        <span style={{ color: 'var(--text-muted)' }}>·</span>
        <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {runId}
        </span>
      </header>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <RunInspector runId={runId} />
      </div>
    </main>
  );
}

// Artifact deep-link page — renders a single artifact in full-page context.
// Accessible at /artifacts/<artifact-id> (FR-28, ART-3 deep-linkable).

import { ArtifactPanel } from '../../../components/workspace/ArtifactPanel';

interface ArtifactPageProps {
  params: Promise<{ artifactId: string }>;
}

// ArtifactPanel expects ArtifactRef[] but for the deep-link page we only know
// the ID. We render with a minimal pending ref; the panel fetches the manifest.
export default async function ArtifactPage({ params }: ArtifactPageProps) {
  const { artifactId } = await params;

  const stubRef = {
    id: artifactId,
    type: 'file' as const,
    title: artifactId.slice(0, 12) + '…',
    status: 'ready' as const,
    run_id: '',
    actionable: false,
    review_status: 'not_required' as const,
    created_at: new Date().toISOString(),
  };

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
          {artifactId}
        </span>
      </header>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <ArtifactPanel artifacts={[stubRef]} initialArtifactId={artifactId} />
      </div>
    </main>
  );
}

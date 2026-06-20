// Runs list page — shows recent runs across all sessions.
// Links each run to /runs/[runId] for the full run inspector view.

export default function RunsPage() {
  return (
    <main
      style={{
        maxWidth: 760,
        margin: '40px auto',
        padding: '0 20px',
        fontFamily: 'system-ui, sans-serif',
        color: 'var(--text)',
      }}
    >
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 20 }}>Run history</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>
        Select a session from the workspace sidebar to browse its runs, or navigate directly to{' '}
        <code>/runs/&lt;run-id&gt;</code> to inspect a specific run.
      </p>
    </main>
  );
}

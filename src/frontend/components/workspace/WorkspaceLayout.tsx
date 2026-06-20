'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import type { SessionSummary, RunId, ArtifactRef, GenomeViewport } from '../../lib/types';
import { ChatPanel } from '../chat/ChatPanel';
import { ArtifactPanel } from './ArtifactPanel';
import { RunInspector } from './RunInspector';

// ---------------------------------------------------------------------------
// Workspace layout — workspace_interface.md §2
// Three resizable regions: sidebar | chat | pane dock
// ---------------------------------------------------------------------------

interface WorkspaceLayoutProps {
  session: SessionSummary;
  children?: React.ReactNode;
}

export function WorkspaceLayout({ session }: WorkspaceLayoutProps) {
  // Collected artifacts for the dock (updated as runs produce them)
  const [dockArtifacts, setDockArtifacts] = useState<ArtifactRef[]>([]);
  const [inspectedRunId, setInspectedRunId] = useState<RunId | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [dockOpen, setDockOpen] = useState(true);
  const [dockView, setDockView] = useState<'artifacts' | 'run'>('artifacts');

  // Resizable sidebar
  const [sidebarWidth, setSidebarWidth] = useState(240);
  const sidebarDragRef = useRef<{ startX: number; startW: number } | null>(null);

  // Resizable dock
  const [dockWidth, setDockWidth] = useState(420);
  const dockDragRef = useRef<{ startX: number; startW: number } | null>(null);

  const handleSidebarMouseDown = (e: React.MouseEvent) => {
    sidebarDragRef.current = { startX: e.clientX, startW: sidebarWidth };
    e.preventDefault();
  };
  const handleDockMouseDown = (e: React.MouseEvent) => {
    dockDragRef.current = { startX: e.clientX, startW: dockWidth };
    e.preventDefault();
  };

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (sidebarDragRef.current) {
        const delta = e.clientX - sidebarDragRef.current.startX;
        setSidebarWidth(Math.max(160, Math.min(400, sidebarDragRef.current.startW + delta)));
      }
      if (dockDragRef.current) {
        const delta = dockDragRef.current.startX - e.clientX;
        setDockWidth(Math.max(280, Math.min(800, dockDragRef.current.startW + delta)));
      }
    };
    const onUp = () => {
      sidebarDragRef.current = null;
      dockDragRef.current = null;
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  // Keyboard shortcuts — workspace_interface.md §2
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.metaKey && !e.ctrlKey) return;
      if (e.key === '\\') { setSidebarOpen(v => !v); e.preventDefault(); }
      if (e.key === 'j' || e.key === 'J') { setDockOpen(v => !v); e.preventDefault(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const openRunInspector = useCallback((runId: RunId) => {
    setInspectedRunId(runId);
    setDockView('run');
    setDockOpen(true);
  }, []);

  const handleArtifactAdded = useCallback((artifact: ArtifactRef) => {
    setDockArtifacts(prev => {
      const exists = prev.find(a => a.id === artifact.id);
      if (exists) return prev.map(a => a.id === artifact.id ? artifact : a);
      return [...prev, artifact];
    });
    setDockView('artifacts');
    setDockOpen(true);
  }, []);

  const defaultViewport: GenomeViewport | undefined = session.defaults.assembly
    ? {
        organism: session.defaults.organism ?? 'hsapiens',
        assembly: session.defaults.assembly,
        contig: 'chr1',
        start: 0,
        end: 10_000_000,
        strand: '+',
        circular: false,
      }
    : undefined;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--bg)',
      }}
    >
      {/* Top bar */}
      <TopBar session={session} onToggleSidebar={() => setSidebarOpen(v => !v)} />

      {/* Main three-column area */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Sidebar */}
        {sidebarOpen && (
          <>
            <aside
              aria-label="Session sidebar"
              style={{
                width: sidebarWidth,
                flexShrink: 0,
                background: 'var(--bg-raised)',
                borderRight: '1px solid var(--border)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}
            >
              <SessionSidebar session={session} onRunOpen={openRunInspector} />
            </aside>

            {/* Sidebar resize handle */}
            <div
              onMouseDown={handleSidebarMouseDown}
              aria-hidden="true"
              style={{
                width: 4,
                cursor: 'col-resize',
                background: 'transparent',
                flexShrink: 0,
                zIndex: 10,
              }}
            />
          </>
        )}

        {/* Chat */}
        <main
          aria-label="Chat thread"
          style={{ flex: 1, minWidth: 300, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
        >
          <ChatPanel
            sessionId={session.id}
            title={session.title}
            organism={session.defaults.organism}
            assembly={session.defaults.assembly}
            onRunOpen={openRunInspector}
          />
        </main>

        {/* Dock resize handle + pane dock */}
        {dockOpen && (
          <>
            <div
              onMouseDown={handleDockMouseDown}
              aria-hidden="true"
              style={{
                width: 4,
                cursor: 'col-resize',
                background: 'transparent',
                flexShrink: 0,
                zIndex: 10,
              }}
            />
            <aside
              aria-label="Pane dock"
              style={{
                width: dockWidth,
                flexShrink: 0,
                background: 'var(--bg-raised)',
                borderLeft: '1px solid var(--border)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}
            >
              {/* Dock header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  borderBottom: '1px solid var(--border)',
                  background: 'var(--bg-overlay)',
                  flexShrink: 0,
                }}
              >
                <button
                  onClick={() => setDockView('artifacts')}
                  aria-pressed={dockView === 'artifacts'}
                  style={dockTabStyle(dockView === 'artifacts')}
                >
                  ◇ Artifacts
                </button>
                {inspectedRunId && (
                  <button
                    onClick={() => setDockView('run')}
                    aria-pressed={dockView === 'run'}
                    style={dockTabStyle(dockView === 'run')}
                  >
                    ⚙ Run
                  </button>
                )}
                <button
                  onClick={() => setDockOpen(false)}
                  aria-label="Close pane dock"
                  title="Close dock (⌘J)"
                  style={{
                    marginLeft: 'auto',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    fontSize: 16,
                    padding: '4px 10px',
                  }}
                >
                  ×
                </button>
              </div>

              {/* Dock content */}
              <div style={{ flex: 1, overflow: 'hidden' }}>
                {dockView === 'artifacts' && (
                  <ArtifactPanel
                    artifacts={dockArtifacts}
                    defaultViewport={defaultViewport}
                  />
                )}
                {dockView === 'run' && inspectedRunId && (
                  <RunInspector runId={inspectedRunId} />
                )}
              </div>
            </aside>
          </>
        )}
      </div>

      {/* Status bar */}
      <StatusBar session={session} dockOpen={dockOpen} onToggleDock={() => setDockOpen(v => !v)} />
    </div>
  );

  // Suppress unused warning — this callback is wired to ChatPanel events in real impl
  void handleArtifactAdded;
}

// ---------------------------------------------------------------------------
// Top bar
// ---------------------------------------------------------------------------

function TopBar({ session, onToggleSidebar }: { session: SessionSummary; onToggleSidebar: () => void }) {
  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        height: 40,
        background: 'var(--bg-raised)',
        borderBottom: '1px solid var(--border)',
        gap: 8,
        flexShrink: 0,
      }}
    >
      <button
        onClick={onToggleSidebar}
        aria-label="Toggle sidebar"
        title="Toggle sidebar (⌘\\)"
        style={iconBtnStyle}
      >
        ☰
      </button>
      <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>CellXP</span>
      <span style={{ color: 'var(--border)' }}>·</span>
      <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{session.title}</span>
      {session.defaults.organism && (
        <span
          style={{
            fontSize: 11,
            padding: '1px 8px',
            background: 'var(--bg-overlay)',
            borderRadius: 10,
            color: 'var(--text-muted)',
          }}
        >
          {session.defaults.organism}{session.defaults.assembly ? ` · ${session.defaults.assembly}` : ''}
        </span>
      )}
    </header>
  );
}

// ---------------------------------------------------------------------------
// Session sidebar
// ---------------------------------------------------------------------------

function SessionSidebar({
  session,
  onRunOpen,
}: {
  session: SessionSummary;
  onRunOpen?: (id: RunId) => void;
}) {
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
      <SidebarSection label="Session">
        <div style={{ padding: '4px 12px', fontSize: 12, color: 'var(--text-muted)' }}>
          <div style={{ marginBottom: 4, color: 'var(--text)' }}>{session.title}</div>
          <div>Type: {session.type}</div>
          <div>Runs: {session.run_count}</div>
          <div>Artifacts: {session.artifact_count}</div>
        </div>
      </SidebarSection>

      <SidebarSection label="Defaults">
        <div style={{ padding: '4px 12px', fontSize: 12, color: 'var(--text-muted)' }}>
          {session.defaults.organism && <div>Organism: {session.defaults.organism}</div>}
          {session.defaults.assembly && <div>Assembly: {session.defaults.assembly}</div>}
          {session.defaults.persona && <div>Persona: {session.defaults.persona}</div>}
          <div>Review: {session.defaults.review_posture ?? 'standard'}</div>
        </div>
      </SidebarSection>
    </div>
  );
  void onRunOpen;
}

function SidebarSection({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          width: '100%',
          padding: '5px 12px',
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          textAlign: 'left',
          fontFamily: 'inherit',
        }}
      >
        <span style={{ fontSize: 9 }}>{open ? '▼' : '▶'}</span>
        {label}
      </button>
      {open && children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status bar
// ---------------------------------------------------------------------------

function StatusBar({
  session: _session,
  dockOpen,
  onToggleDock,
}: {
  session: SessionSummary;
  dockOpen: boolean;
  onToggleDock: () => void;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        height: 24,
        background: 'var(--bg-overlay)',
        borderTop: '1px solid var(--border)',
        fontSize: 11,
        color: 'var(--text-muted)',
        gap: 12,
        flexShrink: 0,
      }}
    >
      <span>CellXP</span>
      <span style={{ marginLeft: 'auto' }}>
        <button
          onClick={onToggleDock}
          aria-label="Toggle pane dock"
          title="Toggle dock (⌘J)"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontSize: 11,
            fontFamily: 'inherit',
          }}
        >
          {dockOpen ? '⊟ dock' : '⊞ dock'}
        </button>
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const iconBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontSize: 16,
  padding: '2px 6px',
  borderRadius: 4,
};

function dockTabStyle(active: boolean): React.CSSProperties {
  return {
    background: 'none',
    border: 'none',
    borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
    color: active ? 'var(--text)' : 'var(--text-muted)',
    cursor: 'pointer',
    fontSize: 12,
    fontFamily: 'inherit',
    fontWeight: active ? 600 : 400,
    padding: '6px 12px',
    marginBottom: -1,
  };
}

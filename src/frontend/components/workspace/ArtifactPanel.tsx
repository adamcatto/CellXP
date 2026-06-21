'use client';

import React, { useState, useEffect } from 'react';
import type { ArtifactRef, ArtifactManifest, TrackDescriptor, GenomeViewport } from '../../lib/types';
import { api } from '../../lib/api';
import { artifactIcon, artifactLabel, isGenomicArtifact } from '../../lib/artifacts';
import { GenomeBrowser } from '../genome/GenomeBrowser';
import { Tabs, TabPanel } from '../ui/Tabs';
import { SelectionProvider } from '../../lib/selection';
import { LocusInspector } from '../plots/LocusInspector';
import { StructureViewer3D } from '../structure/StructureViewer3D';

// ---------------------------------------------------------------------------
// Artifact pane dock — workspace_interface.md §4
// Renders typed artifact content or a placeholder while loading.
// ---------------------------------------------------------------------------

interface ArtifactPanelProps {
  artifacts: ArtifactRef[];
  initialArtifactId?: string;
  defaultViewport?: GenomeViewport;
}

export function ArtifactPanel({ artifacts, initialArtifactId, defaultViewport }: ArtifactPanelProps) {
  const [activeId, setActiveId] = useState<string>(
    initialArtifactId ?? artifacts[0]?.id ?? '',
  );

  // When new artifacts arrive, activate the latest one
  useEffect(() => {
    if (artifacts.length > 0 && !artifacts.find(a => a.id === activeId)) {
      setActiveId(artifacts[artifacts.length - 1].id);
    }
  }, [artifacts, activeId]);

  if (artifacts.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: 'var(--text-muted)',
          fontSize: 13,
          textAlign: 'center',
          padding: 24,
        }}
      >
        <div>
          <div style={{ fontSize: 28, marginBottom: 10 }}>◇</div>
          <p>Artifacts produced during a run will appear here.</p>
        </div>
      </div>
    );
  }

  const tabs = artifacts.map(a => ({
    id: a.id,
    label: a.title,
    icon: artifactIcon(a.type),
    badge: a.status === 'pending' ? '…' : undefined,
  }));

  return (
    <SelectionProvider>
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Tabs tabs={tabs} activeId={activeId} onChange={setActiveId} />
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {artifacts.map(a => (
          <TabPanel key={a.id} id={a.id} activeId={activeId} style={{ height: '100%' }}>
            <ArtifactViewer
              artifactRef={a}
              defaultViewport={defaultViewport}
            />
          </TabPanel>
        ))}
      </div>
    </div>
    </SelectionProvider>
  );
}

// ---------------------------------------------------------------------------
// Per-artifact viewer — dispatches to the right renderer
// ---------------------------------------------------------------------------

interface ArtifactViewerProps {
  artifactRef: ArtifactRef;
  defaultViewport?: GenomeViewport;
}

function ArtifactViewer({ artifactRef, defaultViewport }: ArtifactViewerProps) {
  const [manifest, setManifest] = useState<ArtifactManifest | null>(null);
  const [loading, setLoading] = useState(artifactRef.status !== 'pending');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (artifactRef.status === 'pending') return;
    let cancelled = false;
    setLoading(true);
    api.artifacts.get(artifactRef.id)
      .then(m => { if (!cancelled) { setManifest(m); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, [artifactRef.id, artifactRef.status]);

  if (artifactRef.status === 'pending') {
    return (
      <div style={centeredStyle}>
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Rendering {artifactLabel(artifactRef.type)}…</span>
      </div>
    );
  }

  if (loading) {
    return <div style={centeredStyle}><span style={{ color: 'var(--text-muted)' }}>Loading…</span></div>;
  }

  if (error || !manifest) {
    return <div style={centeredStyle}><span style={{ color: 'var(--danger)' }}>{error ?? 'Failed to load artifact'}</span></div>;
  }

  return <ArtifactRenderer manifest={manifest} defaultViewport={defaultViewport} />;
}

// ---------------------------------------------------------------------------
// Renderer dispatch
// ---------------------------------------------------------------------------

interface ArtifactRendererProps {
  manifest: ArtifactManifest;
  defaultViewport?: GenomeViewport;
}

function ArtifactRenderer({ manifest, defaultViewport }: ArtifactRendererProps) {
  const { type } = manifest;

  // Pane chrome — coordinates + provenance + confidence header
  const coordFrame = manifest.coordinate_frame;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Pane chrome */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '5px 10px',
          background: 'var(--bg-raised)',
          borderBottom: '1px solid var(--border)',
          fontSize: 11,
          color: 'var(--text-muted)',
          flexShrink: 0,
          flexWrap: 'wrap',
        }}
      >
        <span style={{ fontWeight: 600, color: 'var(--text)' }}>
          {artifactIcon(type)} {manifest.title}
        </span>
        {manifest.revision > 0 && (
          <span>rev {manifest.revision}</span>
        )}
        {coordFrame?.assembly && (
          <span style={{ fontFamily: 'var(--font-mono)' }}>
            {coordFrame.assembly}
            {coordFrame.contig && ` · ${coordFrame.contig}`}
          </span>
        )}
        {manifest.confidence?.band && (
          <span>Confidence: {manifest.confidence.band}</span>
        )}
        {manifest.transform_notes && manifest.transform_notes.length > 0 && (
          <span title={manifest.transform_notes.join('; ')} style={{ color: 'var(--warning)' }}>
            ⚠ transformed
          </span>
        )}
        {/* Export link */}
        {manifest.exports && manifest.exports.length > 0 && (
          <a
            href={api.artifacts.contentUrl(manifest.id)}
            download
            style={{ marginLeft: 'auto', color: 'var(--accent)', textDecoration: 'none' }}
          >
            ↓ Download
          </a>
        )}
        {/* Table fallback link (ART-6) */}
        {manifest.accessibility?.table_fallback_url && (
          <a
            href={manifest.accessibility.table_fallback_url}
            style={{ color: 'var(--text-muted)', textDecoration: 'none' }}
          >
            Table view
          </a>
        )}
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {type === 'structure_3d' ? (
          <StructureViewer3D manifest={manifest} />
        ) : type === 'locus_plot' ? (
          <LocusInspector manifest={manifest} />
        ) : isGenomicArtifact(type) && defaultViewport ? (
          <GenomeBrowser
            initialViewport={coordFrame
              ? {
                  organism: coordFrame.organism ?? defaultViewport.organism,
                  assembly: coordFrame.assembly ?? defaultViewport.assembly,
                  contig: coordFrame.contig ?? defaultViewport.contig,
                  start: coordFrame.start ?? defaultViewport.start,
                  end: coordFrame.end ?? defaultViewport.end,
                  strand: coordFrame.strand ?? defaultViewport.strand ?? '+',
                  circular: coordFrame.circular ?? false,
                }
              : defaultViewport}
            tracks={extractTracks(manifest)}
            payloads={extractPayloads(manifest)}
            style={{ height: '100%', border: 'none', borderRadius: 0 }}
          />
        ) : type === 'report' ? (
          <ReportRenderer manifest={manifest} />
        ) : type === 'feature_table' || type === 'coordinate_table' ? (
          <TableRenderer manifest={manifest} />
        ) : (
          <GenericArtifactRenderer manifest={manifest} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Specialised renderers
// ---------------------------------------------------------------------------

function ReportRenderer({ manifest }: { manifest: ArtifactManifest }) {
  const text = manifest.payload?.text as string | undefined;
  if (!text) return <GenericArtifactRenderer manifest={manifest} />;
  return (
    <div style={{ padding: 20, lineHeight: 1.7, fontSize: 14, color: 'var(--text)', whiteSpace: 'pre-wrap' }}>
      {text}
    </div>
  );
}

function TableRenderer({ manifest }: { manifest: ArtifactManifest }) {
  const rows = manifest.payload?.rows as Record<string, unknown>[] | undefined;
  const columns = manifest.payload?.columns as string[] | undefined;
  if (!rows || !columns) return <GenericArtifactRenderer manifest={manifest} />;

  return (
    <div style={{ overflowX: 'auto', padding: 8 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            {columns.map(col => (
              <th
                key={col}
                style={{
                  padding: '4px 10px',
                  borderBottom: '1px solid var(--border)',
                  color: 'var(--text-muted)',
                  fontWeight: 600,
                  textAlign: 'left',
                  whiteSpace: 'nowrap',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
              {columns.map(col => (
                <td key={col} style={{ padding: '4px 10px', color: 'var(--text)' }}>
                  {String(row[col] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GenericArtifactRenderer({ manifest }: { manifest: ArtifactManifest }) {
  return (
    <div style={{ padding: 16, fontSize: 12, color: 'var(--text-muted)' }}>
      <p style={{ marginBottom: 8 }}>
        {manifest.description ?? `${artifactLabel(manifest.type)} artifact`}
      </p>
      {manifest.summary && Object.keys(manifest.summary).length > 0 && (
        <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
          {JSON.stringify(manifest.summary, null, 2)}
        </pre>
      )}
      {manifest.storage_ref && (
        <a
          href={api.artifacts.contentUrl(manifest.id)}
          download
          style={{ color: 'var(--accent)', display: 'inline-block', marginTop: 8 }}
        >
          Download raw content
        </a>
      )}
      {manifest.accessibility?.summary_text && (
        <p style={{ marginTop: 12, fontStyle: 'italic' }}>{manifest.accessibility.summary_text}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Payload helpers for genome browser integration
// ---------------------------------------------------------------------------

function extractTracks(manifest: ArtifactManifest): TrackDescriptor[] {
  const payload = manifest.payload;
  if (!payload) return [];
  const tracks = payload.tracks as TrackDescriptor[] | undefined;
  if (tracks) return tracks;
  // Single-track artifact: synthesise a descriptor
  return [{
    id: manifest.id,
    artifact_id: manifest.id,
    title: manifest.title,
    family: 'custom',
    coordinate_frame: manifest.coordinate_frame ?? { kind: 'genomic' },
    visible: true,
    height_px: 60,
    storage_ref: manifest.storage_ref,
    transform_notes: manifest.transform_notes,
  }];
}

function extractPayloads(manifest: ArtifactManifest): Record<string, import('../genome/TrackViewer').TrackPayload> {
  if (!manifest.payload) return {};
  const payloads = manifest.payload.payloads as Record<string, import('../genome/TrackViewer').TrackPayload> | undefined;
  if (payloads) return payloads;
  return { [manifest.id]: { kind: 'empty' } };
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

const centeredStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100%',
  padding: 20,
};

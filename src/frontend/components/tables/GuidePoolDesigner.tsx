'use client';

import React, { useMemo, useState } from 'react';
import type { ArtifactManifest, ReviewStatus } from '../../lib/types';
import { useWorkspaceSelection } from '../../lib/selection';

interface GuideRow {
  id: string;
  sequence: string;
  contig?: string;
  start?: number;
  end?: number;
  strand?: string;
  pam?: string;
  onTarget?: number;
  offTarget?: number;
  editor?: string;
  raw: Record<string, unknown>;
}

export function payloadRows(payload: Record<string, unknown> | undefined): Record<string, unknown>[] {
  if (!payload) return [];
  const data = payload.data as Record<string, unknown> | undefined;
  const rows = payload.rows ?? payload.guides ?? payload.off_targets ?? data?.rows ?? data?.guides ?? data?.off_targets ?? data;
  return Array.isArray(rows) ? rows.filter(v => v && typeof v === 'object') as Record<string, unknown>[] : [];
}

function parseGuides(manifest: ArtifactManifest): GuideRow[] {
  return payloadRows(manifest.payload).map((raw, index) => {
    const startValue = raw.start ?? raw.position ?? raw.pos;
    const start = startValue === undefined ? undefined : Number(startValue);
    const sequence = String(raw.sequence ?? raw.guide_sequence ?? raw.spacer ?? raw.guide ?? '');
    return {
      id: String(raw.id ?? raw.guide_id ?? `guide-${index + 1}`),
      sequence,
      contig: raw.contig === undefined && raw.chrom === undefined ? manifest.coordinate_frame?.contig : String(raw.contig ?? raw.chrom),
      start: Number.isFinite(start) ? start : undefined,
      end: Number.isFinite(Number(raw.end)) ? Number(raw.end) : Number.isFinite(start) ? Number(start) + sequence.length : undefined,
      strand: raw.strand === undefined ? undefined : String(raw.strand),
      pam: raw.pam === undefined ? undefined : String(raw.pam),
      onTarget: numeric(raw.on_target_score ?? raw.on_target ?? raw.efficiency ?? raw.score),
      offTarget: numeric(raw.off_target_score ?? raw.specificity),
      editor: raw.editor === undefined && raw.nuclease === undefined ? undefined : String(raw.editor ?? raw.nuclease),
      raw,
    };
  });
}

function numeric(value: unknown): number | undefined {
  if (value === undefined || value === null) return undefined;
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function statusLabel(status: ReviewStatus): string {
  return ({ not_required: 'Candidate', pending: 'Pending review', approved: 'Approved', rejected: 'Rejected', changes_requested: 'Changes requested' } as Record<ReviewStatus, string>)[status];
}

export function GuidePoolDesigner({ manifest }: { manifest: ArtifactManifest }) {
  const guides = useMemo(() => parseGuides(manifest), [manifest]);
  const [pool, setPool] = useState<string[]>([]);
  const [sort, setSort] = useState<'onTarget' | 'offTarget'>('onTarget');
  const { selection, publish } = useWorkspaceSelection();
  const ordered = [...guides].sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity));
  const activeRow = selection?.kind === 'row' ? String(selection.payload.row_id ?? '') : '';

  const toggle = (id: string) => setPool(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  const move = (id: string, delta: number) => setPool(current => {
    const index = current.indexOf(id);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= current.length) return current;
    const next = [...current];
    [next[index], next[target]] = [next[target], next[index]];
    return next;
  });
  const emit = (guide: GuideRow) => {
    publish({ kind: 'row', artifact_id: manifest.id, coordinate_frame: manifest.coordinate_frame ?? { kind: 'none' }, payload: { table_id: manifest.id, row_id: guide.id } });
    if (guide.contig && guide.start !== undefined && guide.end !== undefined) {
      publish({ kind: 'interval', artifact_id: manifest.id, coordinate_frame: manifest.coordinate_frame ?? { kind: 'genomic', contig: guide.contig }, payload: { contig: guide.contig, start: guide.start, end: guide.end, strand: guide.strand } });
    }
  };

  if (!guides.length) return <p style={messageStyle}>No guide preview is available. Use the data export to inspect the complete result.</p>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 320, height: '100%' }}>
      <div style={bannerStyle}><strong>{statusLabel(manifest.review_status)}</strong><span>Guide candidates are actionable and remain review-gated.</span><label style={{ marginLeft: 'auto' }}>Sort <select value={sort} onChange={event => setSort(event.target.value as typeof sort)} style={selectStyle}><option value="onTarget">On-target</option><option value="offTarget">Specificity</option></select></label></div>
      <div style={{ overflow: 'auto', flex: 1 }}>
        <table aria-label="CRISPR guide candidates" style={tableStyle}>
          <thead><tr>{['Pool', 'Guide', 'Sequence / PAM', 'Locus', 'On-target', 'Specificity', 'System'].map(label => <th key={label} style={thStyle}>{label}</th>)}</tr></thead>
          <tbody>{ordered.map(guide => {
            const poolIndex = pool.indexOf(guide.id);
            return <tr key={guide.id} onClick={() => emit(guide)} style={{ ...rowStyle, background: activeRow === guide.id ? 'var(--bg-overlay)' : undefined }}>
              <td style={tdStyle}><input type="checkbox" aria-label={`Include ${guide.id} in pool`} checked={poolIndex >= 0} onClick={event => event.stopPropagation()} onChange={() => toggle(guide.id)} />{poolIndex >= 0 && <span style={{ marginLeft: 5 }}>{poolIndex + 1}<button aria-label={`Move ${guide.id} up`} onClick={event => { event.stopPropagation(); move(guide.id, -1); }} style={miniButton}>↑</button><button aria-label={`Move ${guide.id} down`} onClick={event => { event.stopPropagation(); move(guide.id, 1); }} style={miniButton}>↓</button></span>}</td>
              <td style={tdStyle}>{guide.id}</td><td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{guide.sequence || '—'}{guide.pam && <strong style={{ color: 'var(--accent)' }}>{guide.pam}</strong>}</td><td style={tdStyle}>{guide.contig && guide.start !== undefined ? `${guide.contig}:${guide.start + 1}` : '—'} {guide.strand}</td><td style={scoreStyle(guide.onTarget)}>{formatScore(guide.onTarget)}</td><td style={scoreStyle(guide.offTarget)}>{formatScore(guide.offTarget)}</td><td style={tdStyle}>{guide.editor ?? '—'}</td>
            </tr>;
          })}</tbody>
        </table>
      </div>
      <div style={poolStyle}><strong>Draft pool · {pool.length} guide{pool.length === 1 ? '' : 's'}</strong><span style={{ color: 'var(--text-muted)' }}>{pool.length ? pool.join(' → ') : 'Select candidates to compose a pool.'}</span><span title="The backend candidate endpoint is not part of the current wire contract" style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>Commit requires candidate API</span></div>
    </div>
  );
}

function formatScore(value: number | undefined) { return value === undefined ? '—' : value.toFixed(value <= 1 ? 3 : 1); }
function scoreStyle(value: number | undefined): React.CSSProperties { return { ...tdStyle, fontWeight: 600, color: value === undefined ? 'var(--text-muted)' : value >= (value <= 1 ? 0.7 : 70) ? 'var(--success)' : 'var(--text)' }; }
const messageStyle: React.CSSProperties = { padding: 20, color: 'var(--text-muted)', fontSize: 13 };
const bannerStyle: React.CSSProperties = { display: 'flex', gap: 10, alignItems: 'center', padding: '7px 10px', fontSize: 11, background: 'color-mix(in srgb, var(--warning) 12%, var(--bg))', borderBottom: '1px solid var(--border)' };
const poolStyle: React.CSSProperties = { display: 'flex', gap: 10, alignItems: 'center', padding: '8px 10px', borderTop: '1px solid var(--border)', fontSize: 11 };
const selectStyle: React.CSSProperties = { background: 'var(--bg-overlay)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 4 };
const tableStyle: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: 11 };
const thStyle: React.CSSProperties = { position: 'sticky', top: 0, padding: 6, textAlign: 'left', background: 'var(--bg-raised)', borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', zIndex: 1 };
const tdStyle: React.CSSProperties = { padding: 6, borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', color: 'var(--text)' };
const rowStyle: React.CSSProperties = { cursor: 'pointer' };
const miniButton: React.CSSProperties = { background: 'none', color: 'var(--text-muted)', border: 0, cursor: 'pointer', padding: '0 2px' };

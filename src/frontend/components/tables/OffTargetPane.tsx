'use client';

import React, { useMemo, useState } from 'react';
import type { ArtifactManifest } from '../../lib/types';
import { useWorkspaceSelection } from '../../lib/selection';
import { payloadRows } from './GuidePoolDesigner';

interface Hit { id: string; guide: string; contig: string; start: number; end: number; strand?: string; mismatches: number; seedMismatches?: number; score?: number; gene?: string; }

function number(value: unknown, fallback = 0): number { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : fallback; }

function parseHits(manifest: ArtifactManifest): Hit[] {
  return payloadRows(manifest.payload).flatMap((row, index) => {
    const start = number(row.start ?? row.position ?? row.pos, NaN);
    if (!Number.isFinite(start)) return [];
    const sequence = String(row.sequence ?? row.target_sequence ?? '');
    return [{ id: String(row.id ?? row.hit_id ?? `hit-${index + 1}`), guide: String(row.guide_id ?? row.guide ?? '—'), contig: String(row.contig ?? row.chrom ?? manifest.coordinate_frame?.contig ?? ''), start, end: number(row.end, start + Math.max(1, sequence.length)), strand: row.strand === undefined ? undefined : String(row.strand), mismatches: number(row.mismatches ?? row.mismatch_count), seedMismatches: row.seed_mismatches === undefined ? undefined : number(row.seed_mismatches), score: row.score === undefined && row.off_target_score === undefined ? undefined : number(row.score ?? row.off_target_score), gene: row.gene === undefined ? undefined : String(row.gene) }];
  });
}

export function OffTargetPane({ manifest }: { manifest: ArtifactManifest }) {
  const hits = useMemo(() => parseHits(manifest), [manifest]);
  const maxObserved = Math.max(0, ...hits.map(hit => hit.mismatches));
  const [maxMismatches, setMaxMismatches] = useState(maxObserved);
  const [seedOnly, setSeedOnly] = useState(false);
  const { publish } = useWorkspaceSelection();
  const filtered = hits.filter(hit => hit.mismatches <= maxMismatches && (!seedOnly || (hit.seedMismatches ?? 0) > 0));
  const select = (hit: Hit) => publish({ kind: 'interval', artifact_id: manifest.id, coordinate_frame: manifest.coordinate_frame ?? { kind: 'genomic', contig: hit.contig }, payload: { contig: hit.contig, start: hit.start, end: hit.end, strand: hit.strand } });
  if (!hits.length) return <p style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>No off-target hits were reported in the bounded preview.</p>;
  return <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 300 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '7px 10px', borderBottom: '1px solid var(--border)', fontSize: 11 }}><label>Maximum mismatches <input type="range" min={0} max={Math.max(1, maxObserved)} value={maxMismatches} onChange={event => setMaxMismatches(Number(event.target.value))} /> {maxMismatches}</label><label><input type="checkbox" checked={seedOnly} onChange={event => setSeedOnly(event.target.checked)} /> Seed-region mismatches only</label><span style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>{filtered.length} / {hits.length} hits</span></div>
    <div style={{ overflow: 'auto', flex: 1 }}><table aria-label="CRISPR off-target hits" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}><thead><tr>{['Hit', 'Guide', 'Locus', 'MM', 'Seed MM', 'Score', 'Gene'].map(label => <th key={label} style={thStyle}>{label}</th>)}</tr></thead><tbody>{filtered.map(hit => <tr key={hit.id} tabIndex={0} onClick={() => select(hit)} onKeyDown={event => event.key === 'Enter' && select(hit)} style={{ cursor: 'pointer' }}><td style={tdStyle}>{hit.id}</td><td style={tdStyle}>{hit.guide}</td><td style={tdStyle}>{hit.contig}:{hit.start + 1}-{hit.end} {hit.strand}</td><td style={tdStyle}>{hit.mismatches}</td><td style={tdStyle}>{hit.seedMismatches ?? '—'}</td><td style={tdStyle}>{hit.score?.toFixed(3) ?? '—'}</td><td style={tdStyle}>{hit.gene ?? '—'}</td></tr>)}</tbody></table></div>
    <p style={{ padding: '6px 10px', margin: 0, color: 'var(--text-muted)', borderTop: '1px solid var(--border)', fontSize: 11 }}>Select a hit to center linked genomic panes. Coordinates display as 1-based inclusive.</p>
  </div>;
}

const thStyle: React.CSSProperties = { position: 'sticky', top: 0, padding: 6, textAlign: 'left', background: 'var(--bg-raised)', borderBottom: '1px solid var(--border)', color: 'var(--text-muted)' };
const tdStyle: React.CSSProperties = { padding: 6, borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', color: 'var(--text)' };

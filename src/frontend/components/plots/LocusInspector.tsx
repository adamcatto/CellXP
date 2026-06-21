'use client';

import React, { useMemo, useRef, useState } from 'react';
import type { ArtifactManifest } from '../../lib/types';
import { useWorkspaceSelection } from '../../lib/selection';

interface Association {
  id: string;
  contig: string;
  pos: number;
  pValue: number;
  ref?: string;
  alt?: string;
  trait?: string;
  ld?: number;
}

function records(payload: Record<string, unknown> | undefined): Record<string, unknown>[] {
  if (!payload) return [];
  const data = payload.data as Record<string, unknown> | undefined;
  const value = payload.associations ?? payload.variants ?? data?.associations ?? data?.variants ?? data;
  if (Array.isArray(value)) return value.filter(v => v && typeof v === 'object') as Record<string, unknown>[];
  return [];
}

function parseAssociations(manifest: ArtifactManifest): Association[] {
  const fallbackContig = manifest.coordinate_frame?.contig ?? '';
  return records(manifest.payload).flatMap((row, index) => {
    const pos = Number(row.pos ?? row.position ?? row.bp);
    const pValue = Number(row.p_value ?? row.pValue ?? row.p ?? 1);
    if (!Number.isFinite(pos) || !Number.isFinite(pValue) || pValue <= 0) return [];
    return [{
      id: String(row.id ?? row.variant_id ?? row.rsid ?? `${fallbackContig}:${pos}:${index}`),
      contig: String(row.contig ?? row.chrom ?? row.chromosome ?? fallbackContig),
      pos,
      pValue,
      ref: row.ref === undefined ? undefined : String(row.ref),
      alt: row.alt === undefined ? undefined : String(row.alt),
      trait: row.trait === undefined ? undefined : String(row.trait),
      ld: row.ld === undefined && row.r2 === undefined ? undefined : Number(row.ld ?? row.r2),
    }];
  });
}

export function LocusInspector({ manifest }: { manifest: ArtifactManifest }) {
  const associations = useMemo(() => parseAssociations(manifest), [manifest]);
  const { selection, publish } = useWorkspaceSelection();
  const [brush, setBrush] = useState<{ start: number; end: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const width = 760;
  const height = 250;
  const left = 48;
  const right = 14;
  const top = 12;
  const bottom = 35;
  const positions = associations.map(a => a.pos);
  const frame = manifest.coordinate_frame;
  const minPos = frame?.start ?? (positions.length ? Math.min(...positions) : 0);
  const maxPos = frame?.end ?? (positions.length ? Math.max(...positions) : minPos + 1);
  const span = Math.max(1, maxPos - minPos);
  const maxScore = Math.max(1, ...associations.map(a => -Math.log10(a.pValue)));
  const x = (pos: number) => left + ((pos - minPos) / span) * (width - left - right);
  const y = (p: number) => top + (1 - (-Math.log10(p) / maxScore)) * (height - top - bottom);
  const selectedId = selection?.kind === 'variant' ? String(selection.payload.id ?? '') : '';

  const mousePos = (event: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return minPos;
    const px = ((event.clientX - rect.left) / rect.width) * width;
    return Math.round(minPos + ((px - left) / (width - left - right)) * span);
  };

  const finishBrush = () => {
    if (!brush || !frame) return setBrush(null);
    const start = Math.max(0, Math.min(brush.start, brush.end));
    const end = Math.max(start + 1, Math.max(brush.start, brush.end));
    publish({
      kind: 'interval',
      artifact_id: manifest.id,
      coordinate_frame: frame,
      payload: { contig: frame.contig, start, end, strand: frame.strand },
    });
    setBrush(null);
  };

  if (!associations.length) {
    return <p style={emptyStyle}>No association preview is available. Use the artifact export for the complete dataset.</p>;
  }

  return (
    <div style={{ padding: 12, minWidth: 480 }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 6 }}>
        {frame?.assembly ?? 'Assembly unspecified'} · {frame?.contig ?? associations[0].contig} · −log₁₀(p). Drag to select an interval.
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Locus association plot with ${associations.length} variants`}
        style={{ width: '100%', minHeight: 220, display: 'block', background: 'var(--bg-overlay)', borderRadius: 6 }}
        onMouseDown={event => setBrush({ start: mousePos(event), end: mousePos(event) })}
        onMouseMove={event => brush && setBrush(current => current ? { ...current, end: mousePos(event) } : null)}
        onMouseUp={finishBrush}
        onMouseLeave={() => brush && finishBrush()}
      >
        <line x1={left} y1={height - bottom} x2={width - right} y2={height - bottom} stroke="var(--border)" />
        <line x1={left} y1={top} x2={left} y2={height - bottom} stroke="var(--border)" />
        {associations.map(a => {
          const active = selectedId === a.id;
          return (
            <circle
              key={a.id}
              cx={x(a.pos)}
              cy={y(a.pValue)}
              r={active ? 6 : 3.5}
              fill={a.ld === undefined ? 'var(--accent)' : `hsl(${220 - Math.max(0, Math.min(1, a.ld)) * 210} 75% 55%)`}
              stroke={active ? 'var(--text)' : 'none'}
              tabIndex={0}
              aria-label={`${a.id}, p ${a.pValue}`}
              onMouseDown={event => event.stopPropagation()}
              onClick={event => {
                event.stopPropagation();
                publish({
                  kind: 'variant', artifact_id: manifest.id,
                  coordinate_frame: frame ?? { kind: 'genomic', contig: a.contig },
                  payload: { id: a.id, contig: a.contig, pos: a.pos, ref: a.ref, alt: a.alt },
                });
              }}
              onKeyDown={event => event.key === 'Enter' && event.currentTarget.dispatchEvent(new MouseEvent('click', { bubbles: true }))}
            >
              <title>{a.id} · p={a.pValue.toExponential(2)}{a.trait ? ` · ${a.trait}` : ''}</title>
            </circle>
          );
        })}
        {brush && <rect x={x(Math.min(brush.start, brush.end))} y={top} width={Math.abs(x(brush.end) - x(brush.start))} height={height - top - bottom} fill="var(--accent)" opacity={0.18} />}
        <text x={(left + width - right) / 2} y={height - 8} textAnchor="middle" fill="var(--text-muted)" fontSize={11}>Genomic position (0-based payload)</text>
      </svg>
      <details style={{ marginTop: 10 }}>
        <summary style={{ color: 'var(--text-muted)', fontSize: 12, cursor: 'pointer' }}>Accessible association table</summary>
        <div style={{ maxHeight: 220, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead><tr>{['Variant', 'Position', 'P value', 'LD', 'Trait'].map(label => <th key={label} style={thStyle}>{label}</th>)}</tr></thead>
            <tbody>{associations.map(a => <tr key={a.id}><td style={tdStyle}>{a.id}</td><td style={tdStyle}>{a.pos.toLocaleString()}</td><td style={tdStyle}>{a.pValue.toExponential(2)}</td><td style={tdStyle}>{a.ld?.toFixed(3) ?? '—'}</td><td style={tdStyle}>{a.trait ?? '—'}</td></tr>)}</tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

const emptyStyle: React.CSSProperties = { padding: 20, color: 'var(--text-muted)', fontSize: 13 };
const thStyle: React.CSSProperties = { padding: 5, textAlign: 'left', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' };
const tdStyle: React.CSSProperties = { padding: 5, color: 'var(--text)', borderBottom: '1px solid var(--border)' };

'use client';

import React, { useState } from 'react';

// ---------------------------------------------------------------------------
// Variant table — accessible fallback for the genome browser overlay (ART-6)
// ---------------------------------------------------------------------------

export interface VariantRow {
  id: string;
  chrom: string;
  pos: number;  // 1-based display
  ref: string;
  alt: string;
  af?: number;
  score?: number;
  scoreName?: string;
  trait?: string;
  consequence?: string;
}

interface VariantTableProps {
  variants: VariantRow[];
  onVariantSelect?: (v: VariantRow) => void;
}

export function VariantTable({ variants, onVariantSelect }: VariantTableProps) {
  const [sortKey, setSortKey] = useState<keyof VariantRow>('pos');
  const [sortDir, setSortDir] = useState<1 | -1>(1);

  const sort = (key: keyof VariantRow) => {
    if (sortKey === key) setSortDir(d => (d === 1 ? -1 : 1));
    else { setSortKey(key); setSortDir(1); }
  };

  const sorted = [...variants].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av === undefined) return 1;
    if (bv === undefined) return -1;
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * sortDir;
    return String(av).localeCompare(String(bv)) * sortDir;
  });

  if (variants.length === 0) {
    return (
      <p style={{ color: 'var(--text-muted)', fontSize: 13, padding: '12px 0' }}>
        No variants in this region.
      </p>
    );
  }

  const cols: { key: keyof VariantRow; label: string }[] = [
    { key: 'chrom', label: 'Chr' },
    { key: 'pos', label: 'Pos' },
    { key: 'ref', label: 'Ref' },
    { key: 'alt', label: 'Alt' },
    { key: 'af', label: 'AF' },
    { key: 'score', label: 'Score' },
    { key: 'consequence', label: 'Consequence' },
  ];

  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 12,
          fontFamily: 'var(--font-mono)',
        }}
        aria-label="Variant table"
      >
        <thead>
          <tr>
            {cols.map(col => (
              <th
                key={col.key}
                onClick={() => sort(col.key)}
                aria-sort={
                  sortKey === col.key
                    ? sortDir === 1 ? 'ascending' : 'descending'
                    : 'none'
                }
                style={{
                  padding: '4px 10px',
                  textAlign: 'left',
                  borderBottom: '1px solid var(--border)',
                  cursor: 'pointer',
                  color: sortKey === col.key ? 'var(--accent)' : 'var(--text-muted)',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  userSelect: 'none',
                }}
              >
                {col.label} {sortKey === col.key ? (sortDir === 1 ? '↑' : '↓') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map(v => (
            <tr
              key={v.id}
              onClick={() => onVariantSelect?.(v)}
              style={{
                cursor: onVariantSelect ? 'pointer' : 'default',
                borderBottom: '1px solid var(--border)',
              }}
              tabIndex={onVariantSelect ? 0 : undefined}
              onKeyDown={e => e.key === 'Enter' && onVariantSelect?.(v)}
            >
              <td style={cellStyle}>{v.chrom}</td>
              <td style={cellStyle}>{v.pos.toLocaleString()}</td>
              <td style={{ ...cellStyle, color: 'var(--success)' }}>{v.ref}</td>
              <td style={{ ...cellStyle, color: 'var(--danger)' }}>{v.alt}</td>
              <td style={cellStyle}>{v.af !== undefined ? v.af.toFixed(4) : '—'}</td>
              <td style={{ ...cellStyle, fontWeight: v.score !== undefined ? 600 : 400 }}>
                {v.score !== undefined ? v.score.toFixed(3) : '—'}
              </td>
              <td style={{ ...cellStyle, fontFamily: 'inherit' }}>{v.consequence ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const cellStyle: React.CSSProperties = {
  padding: '4px 10px',
  color: 'var(--text)',
  whiteSpace: 'nowrap',
};

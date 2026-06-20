'use client';

import React, { useState } from 'react';
import type { EvidenceItem } from '../../lib/types';

// ---------------------------------------------------------------------------
// Evidence inspector pane — chat_interface.md §6, streaming_protocol.md §5
// ---------------------------------------------------------------------------

interface EvidencePanelProps {
  items: EvidenceItem[];
  highlightedId?: string;
}

export function EvidencePanel({ items, highlightedId }: EvidencePanelProps) {
  const [filter, setFilter] = useState('');

  const filtered = filter.trim()
    ? items.filter(
        e =>
          (e.title ?? '').toLowerCase().includes(filter.toLowerCase()) ||
          (e.source ?? '').toLowerCase().includes(filter.toLowerCase()) ||
          (e.accession ?? '').toLowerCase().includes(filter.toLowerCase()),
      )
    : items;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <h2 style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
          Evidence ({items.length})
        </h2>
        <input
          type="search"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter evidence…"
          aria-label="Filter evidence"
          style={{
            width: '100%',
            background: 'var(--bg-overlay)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            color: 'var(--text)',
            fontFamily: 'inherit',
            fontSize: 12,
            padding: '4px 8px',
            boxSizing: 'border-box',
          }}
        />
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px' }}>
        {filtered.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            {items.length === 0 ? 'No evidence for this run.' : 'No matches.'}
          </p>
        ) : (
          <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {filtered.map(ev => (
              <EvidenceCard key={ev.id} item={ev} highlighted={ev.id === highlightedId} />
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Single evidence card
// ---------------------------------------------------------------------------

function EvidenceCard({ item, highlighted }: { item: EvidenceItem; highlighted?: boolean }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li
      id={`evidence-${item.id}`}
      style={{
        border: `1px solid ${highlighted ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 6,
        overflow: 'hidden',
        background: highlighted ? 'rgba(79,127,255,0.06)' : 'var(--bg-raised)',
      }}
    >
      <button
        onClick={() => setExpanded(v => !v)}
        aria-expanded={expanded}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
          width: '100%',
          padding: '8px 10px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          fontFamily: 'inherit',
        }}
      >
        <span
          style={{
            fontSize: 10,
            padding: '1px 6px',
            background: 'var(--bg-overlay)',
            borderRadius: 10,
            color: 'var(--text-muted)',
            flexShrink: 0,
            marginTop: 2,
          }}
        >
          {item.kind}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 12,
              color: 'var(--text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {item.title ?? item.source}
          </div>
          {item.accession && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
              {item.accession}
            </div>
          )}
        </div>
        {item.confidence?.band && (
          <span
            title={`Confidence: ${item.confidence.band}`}
            style={{
              fontSize: 10,
              padding: '1px 6px',
              background: confidenceColor(item.confidence.band) + '22',
              color: confidenceColor(item.confidence.band),
              border: `1px solid ${confidenceColor(item.confidence.band)}`,
              borderRadius: 10,
              flexShrink: 0,
            }}
          >
            {item.confidence.band}
          </span>
        )}
        <span style={{ color: 'var(--text-muted)', fontSize: 12, flexShrink: 0, marginLeft: 4 }}>
          {expanded ? '▲' : '▼'}
        </span>
      </button>

      {expanded && (
        <div style={{ padding: '0 10px 10px', fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {item.summary && (
            <p style={{ margin: 0, color: 'var(--text)', lineHeight: 1.5 }}>{item.summary}</p>
          )}
          <div style={{ display: 'flex', gap: 12, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            {item.url && (
              <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>
                View source ↗
              </a>
            )}
            {item.retrieved_at && (
              <span>Retrieved {new Date(item.retrieved_at).toLocaleDateString()}</span>
            )}
            {item.confidence?.value !== undefined && (
              <span>Confidence: {(item.confidence.value * 100).toFixed(0)}%</span>
            )}
            {item.confidence?.model && (
              <span>Model: {item.confidence.model}</span>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

function confidenceColor(band: string): string {
  switch (band) {
    case 'high': return 'var(--success)';
    case 'medium': return 'var(--warning)';
    case 'low': return 'var(--danger)';
    default: return 'var(--text-muted)';
  }
}

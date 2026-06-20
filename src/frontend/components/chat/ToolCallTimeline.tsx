'use client';

import React, { useState } from 'react';
import type { ActivityRow } from '../../lib/streaming';

interface ToolCallTimelineProps {
  rows: ActivityRow[];
  intentLabel?: string;
  planRevision?: number;
}

const STATUS_ICON: Record<ActivityRow['status'], string> = {
  queued: '○',
  running: '◌',
  completed: '✓',
  failed: '✕',
};

const STATUS_COLOR: Record<ActivityRow['status'], string> = {
  queued: 'var(--text-muted)',
  running: 'var(--accent)',
  completed: 'var(--success)',
  failed: 'var(--danger)',
};

export function ToolCallTimeline({ rows, intentLabel, planRevision }: ToolCallTimelineProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  if (!intentLabel && rows.length === 0) return null;

  return (
    <div
      aria-label="Activity log"
      style={{
        fontSize: 12,
        color: 'var(--text-muted)',
        margin: '4px 0 8px',
        borderLeft: '2px solid var(--border)',
        paddingLeft: 10,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      {intentLabel && (
        <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>
          <span style={{ fontWeight: 600, color: 'var(--text)' }}>Intent:</span>{' '}
          {intentLabel}
          {planRevision !== undefined && (
            <span style={{ marginLeft: 8 }}>· plan rev {planRevision}</span>
          )}
        </div>
      )}
      {rows.map((row) => {
        const isExpanded = expanded.has(row.id);
        const hasDetail = row.inputSummary || row.outputSummary || row.toolVersion;
        return (
          <div key={row.id}>
            <button
              onClick={() => hasDetail && toggle(row.id)}
              disabled={!hasDetail}
              aria-expanded={hasDetail ? isExpanded : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'none',
                border: 'none',
                padding: '1px 0',
                cursor: hasDetail ? 'pointer' : 'default',
                fontFamily: 'inherit',
                fontSize: 12,
                color: 'var(--text-muted)',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <span
                aria-label={row.status}
                style={{ color: STATUS_COLOR[row.status], fontSize: 10, flexShrink: 0 }}
              >
                {STATUS_ICON[row.status]}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>
                {row.tool ?? row.label}
              </span>
              <span style={{ color: 'var(--text-muted)' }}>{row.label !== row.tool && row.label}</span>
              {row.status === 'running' && row.interim && (
                <span style={{ color: 'var(--accent)', marginLeft: 4 }}>{row.interim}</span>
              )}
              {row.durationMs !== undefined && (
                <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', flexShrink: 0 }}>
                  {row.durationMs < 1000
                    ? `${row.durationMs}ms`
                    : `${(row.durationMs / 1000).toFixed(1)}s`}
                </span>
              )}
              {hasDetail && (
                <span style={{ marginLeft: row.durationMs !== undefined ? 4 : 'auto', flexShrink: 0 }}>
                  {isExpanded ? '▲' : '▼'}
                </span>
              )}
            </button>

            {isExpanded && hasDetail && (
              <div
                style={{
                  marginLeft: 16,
                  marginTop: 4,
                  padding: '6px 10px',
                  background: 'var(--bg-overlay)',
                  borderRadius: 4,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                }}
              >
                {row.toolVersion && (
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>version:</span>{' '}
                    <code style={{ color: 'var(--text)' }}>{row.toolVersion}</code>
                  </div>
                )}
                {row.inputSummary && (
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>input:</span>{' '}
                    <span style={{ color: 'var(--text)' }}>{row.inputSummary}</span>
                  </div>
                )}
                {row.outputSummary && (
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>output:</span>{' '}
                    <span style={{ color: 'var(--text)' }}>{row.outputSummary}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

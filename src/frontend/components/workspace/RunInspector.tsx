'use client';

import React, { useState, useEffect } from 'react';
import type { RunSnapshot, RunStep, EvidenceItem, ArtifactRef } from '../../lib/types';
import { api } from '../../lib/api';
import { artifactIcon, artifactLabel } from '../../lib/artifacts';
import { Tabs, TabPanel } from '../ui/Tabs';
import { Card } from '../ui/Card';

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  queued: 'var(--text-muted)',
  running: 'var(--accent)',
  awaiting_input: 'var(--warning)',
  awaiting_review: 'var(--warning)',
  completed: 'var(--success)',
  failed: 'var(--danger)',
  cancelled: 'var(--text-muted)',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '1px 8px',
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 600,
        background: `${STATUS_COLORS[status] ?? 'var(--border)'}22`,
        color: STATUS_COLORS[status] ?? 'var(--text-muted)',
        border: `1px solid ${STATUS_COLORS[status] ?? 'var(--border)'}`,
      }}
    >
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Steps timeline
// ---------------------------------------------------------------------------

function StepsTimeline({ steps }: { steps: RunStep[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (steps.length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No steps recorded.</p>;
  }

  return (
    <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
      {steps.map(step => {
        const isExp = expanded.has(step.id);
        return (
          <li key={step.id}>
            <button
              onClick={() => setExpanded(prev => {
                const n = new Set(prev);
                n.has(step.id) ? n.delete(step.id) : n.add(step.id);
                return n;
              })}
              aria-expanded={isExp}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                background: 'none',
                border: 'none',
                borderBottom: '1px solid var(--border)',
                padding: '6px 0',
                cursor: 'pointer',
                textAlign: 'left',
                fontFamily: 'inherit',
                fontSize: 12,
              }}
            >
              <StatusBadge status={step.status} />
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontSize: 11 }}>
                {step.tool}
              </span>
              <span style={{ flex: 1, color: 'var(--text)' }}>{step.label}</span>
              {step.duration_ms !== undefined && (
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                  {step.duration_ms < 1000 ? `${step.duration_ms}ms` : `${(step.duration_ms / 1000).toFixed(1)}s`}
                </span>
              )}
              <span style={{ color: 'var(--text-muted)' }}>{isExp ? '▲' : '▼'}</span>
            </button>
            {isExp && (
              <div
                style={{
                  padding: '8px 12px',
                  background: 'var(--bg-overlay)',
                  borderRadius: 4,
                  marginTop: 4,
                  fontSize: 12,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                }}
              >
                {step.tool_version && (
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>version:</span>{' '}
                    <code>{step.tool_version}</code>
                  </div>
                )}
                {step.input_summary && (
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>input:</span>{' '}
                    <span>{step.input_summary}</span>
                  </div>
                )}
                {step.output_summary && (
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>output:</span>{' '}
                    <span>{step.output_summary}</span>
                  </div>
                )}
                {step.error && (
                  <div style={{ color: 'var(--danger)' }}>
                    <span style={{ fontWeight: 600 }}>error:</span> {step.error}
                  </div>
                )}
                {step.artifact_ids.length > 0 && (
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>artifacts:</span>{' '}
                    {step.artifact_ids.map(id => (
                      <a
                        key={id}
                        href={`/artifacts/${id}`}
                        style={{ color: 'var(--accent)', fontSize: 11, marginLeft: 4 }}
                      >
                        {id.slice(0, 8)}…
                      </a>
                    ))}
                  </div>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// Evidence list
// ---------------------------------------------------------------------------

function EvidenceList({ items }: { items: EvidenceItem[] }) {
  if (items.length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No evidence recorded.</p>;
  }

  return (
    <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
      {items.map(ev => (
        <li key={ev.id} style={{ borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
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
              {ev.kind}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text)' }}>
                {ev.title ?? ev.source}
              </div>
              {ev.accession && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {ev.url ? (
                    <a href={ev.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>
                      {ev.accession}
                    </a>
                  ) : ev.accession}
                </div>
              )}
              {ev.summary && (
                <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 2 }}>{ev.summary}</div>
              )}
              {ev.confidence?.band && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  Confidence: {ev.confidence.band}
                  {ev.confidence.value !== undefined && ` (${(ev.confidence.value * 100).toFixed(0)}%)`}
                </div>
              )}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// Artifacts grid
// ---------------------------------------------------------------------------

function ArtifactsGrid({ artifacts }: { artifacts: ArtifactRef[] }) {
  if (artifacts.length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No artifacts produced.</p>;
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {artifacts.map(a => (
        <a
          key={a.id}
          href={`/artifacts/${a.id}`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 12px',
            background: 'var(--bg-overlay)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            fontSize: 12,
            color: 'var(--text)',
            textDecoration: 'none',
            minWidth: 120,
          }}
        >
          <span>{artifactIcon(a.type)}</span>
          <div>
            <div style={{ fontWeight: 600 }}>{a.title}</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{artifactLabel(a.type)}</div>
          </div>
        </a>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RunInspector
// ---------------------------------------------------------------------------

interface RunInspectorProps {
  runId: string;
  /** Pre-fetched snapshot (if available from streaming) */
  initialSnapshot?: RunSnapshot;
}

const TABS = [
  { id: 'steps', label: 'Steps', icon: '⚙' },
  { id: 'evidence', label: 'Evidence', icon: '📎' },
  { id: 'artifacts', label: 'Artifacts', icon: '◇' },
];

export function RunInspector({ runId, initialSnapshot }: RunInspectorProps) {
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(initialSnapshot ?? null);
  const [steps, setSteps] = useState<RunStep[]>(initialSnapshot?.steps ?? []);
  const [evidence, setEvidence] = useState<EvidenceItem[]>(initialSnapshot?.evidence ?? []);
  const [loading, setLoading] = useState(!initialSnapshot);
  const [activeTab, setActiveTab] = useState('steps');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      api.runs.get(runId),
      api.runs.steps(runId),
      api.runs.evidence(runId),
    ])
      .then(([snap, stepsResp, evidenceResp]) => {
        if (cancelled) return;
        setSnapshot(snap);
        setSteps(stepsResp.items);
        setEvidence(evidenceResp.items);
      })
      .catch(e => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load run');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [runId]);

  if (loading) {
    return (
      <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
        Loading run {runId.slice(0, 8)}…
      </div>
    );
  }

  if (error || !snapshot) {
    return (
      <div style={{ padding: 20, color: 'var(--danger)', fontSize: 13 }}>
        {error ?? 'Run not found'}
      </div>
    );
  }

  const elapsed = snapshot.elapsed_ms !== undefined
    ? snapshot.elapsed_ms < 1000
      ? `${snapshot.elapsed_ms}ms`
      : `${(snapshot.elapsed_ms / 1000).toFixed(1)}s`
    : undefined;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <StatusBadge status={snapshot.status} />
          {elapsed && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{elapsed}</span>
          )}
          {snapshot.model && (
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {snapshot.model}{snapshot.provider ? ` · ${snapshot.provider}` : ''}
            </span>
          )}
        </div>

        {/* Run message */}
        {snapshot.message && (
          <p style={{ margin: '0 0 4px', fontSize: 13, color: 'var(--text)', lineHeight: 1.5 }}>
            {snapshot.message}
          </p>
        )}

        {/* Token usage */}
        {snapshot.token_usage && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {snapshot.token_usage.input.toLocaleString()} in ·{' '}
            {snapshot.token_usage.output.toLocaleString()} out
            {snapshot.token_usage.cache_read !== undefined && (
              <> · {snapshot.token_usage.cache_read.toLocaleString()} cached</>
            )}
          </div>
        )}

        {/* Fatal errors */}
        {snapshot.errors.filter(e => e.fatal).map((err, i) => (
          <Card key={i} accent="red" style={{ marginTop: 8, padding: '6px 10px' }}>
            <span style={{ fontSize: 12, color: 'var(--danger)' }}>{err.message}</span>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs
        tabs={TABS.map(t => ({
          ...t,
          badge: t.id === 'steps' ? steps.length
            : t.id === 'evidence' ? evidence.length
            : snapshot.artifacts.length,
        }))}
        activeId={activeTab}
        onChange={setActiveTab}
      />

      {/* Tab panels */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
        <TabPanel id="steps" activeId={activeTab}>
          <StepsTimeline steps={steps} />
        </TabPanel>
        <TabPanel id="evidence" activeId={activeTab}>
          <EvidenceList items={evidence} />
        </TabPanel>
        <TabPanel id="artifacts" activeId={activeTab}>
          <ArtifactsGrid artifacts={snapshot.artifacts} />
        </TabPanel>
      </div>
    </div>
  );
}

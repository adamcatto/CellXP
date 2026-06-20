'use client';

import React, { useState } from 'react';
import type { ArtifactRef, EvidenceItem, RunError, Clarification, ReviewItem, TokenUsage } from '../../lib/types';
import type { ActivityRow, StreamingRunState } from '../../lib/streaming';
import { artifactIcon, artifactLabel, artifactPath } from '../../lib/artifacts';
import { ToolCallTimeline } from './ToolCallTimeline';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';

// ---------------------------------------------------------------------------
// User turn
// ---------------------------------------------------------------------------

interface UserTurnProps {
  message: string;
  timestamp?: string;
  onEdit?: () => void;
}

export function UserTurn({ message, timestamp, onEdit }: UserTurnProps) {
  return (
    <div
      role="article"
      aria-label="User message"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        margin: '8px 0',
      }}
    >
      <div
        style={{
          maxWidth: '75%',
          background: 'var(--accent)',
          color: '#fff',
          borderRadius: '14px 14px 4px 14px',
          padding: '8px 14px',
          fontSize: 14,
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {message}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 3, alignItems: 'center' }}>
        {timestamp && (
          <time style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </time>
        )}
        {onEdit && (
          <button
            onClick={onEdit}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: 11,
              padding: '0 2px',
            }}
          >
            Edit
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Thinking disclosure
// ---------------------------------------------------------------------------

interface ThinkingDisclosureProps {
  text: string;
  summary: string;
  node?: string;
  defaultExpanded?: boolean;
}

export function ThinkingDisclosure({ text, summary, node, defaultExpanded = false }: ThinkingDisclosureProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const content = expanded ? text : summary;
  if (!text && !summary) return null;

  return (
    <div style={{ marginBottom: 6 }}>
      <button
        onClick={() => setExpanded(v => !v)}
        aria-expanded={expanded}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          fontSize: 12,
          padding: '2px 0',
          fontFamily: 'inherit',
        }}
      >
        <span style={{ fontSize: 10 }}>{expanded ? '▼' : '▶'}</span>
        Thinking
        {node && <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>· {node}</span>}
        {!expanded && text && (
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: 'var(--accent)',
              animation: 'pulse 1.2s ease-in-out infinite',
              flexShrink: 0,
            }}
          />
        )}
      </button>
      {expanded && content && (
        <div
          style={{
            marginTop: 4,
            padding: '8px 12px',
            background: 'var(--bg-overlay)',
            borderRadius: 6,
            fontSize: 12,
            color: 'var(--text-muted)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            lineHeight: 1.6,
            fontStyle: 'italic',
            maxHeight: 300,
            overflow: 'auto',
          }}
        >
          {content}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Artifact bubble
// ---------------------------------------------------------------------------

interface ArtifactBubbleProps {
  artifact: ArtifactRef;
}

function ArtifactBubble({ artifact }: ArtifactBubbleProps) {
  return (
    <a
      href={artifactPath(artifact.id)}
      aria-label={`Open ${artifactLabel(artifact.type)}: ${artifact.title}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        background: 'var(--bg-overlay)',
        border: '1px solid var(--border)',
        borderRadius: 20,
        fontSize: 12,
        color: 'var(--text)',
        textDecoration: 'none',
        transition: 'background 120ms',
      }}
    >
      <span aria-hidden="true">{artifactIcon(artifact.type)}</span>
      <span style={{ fontWeight: 500 }}>{artifact.title}</span>
      {artifact.status === 'pending' && (
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>rendering…</span>
      )}
      {artifact.actionable && artifact.review_status === 'pending' && (
        <span
          title="Pending review"
          style={{ color: 'var(--warning)', fontSize: 11, fontWeight: 700 }}
        >
          ⚠
        </span>
      )}
    </a>
  );
}

// ---------------------------------------------------------------------------
// Clarification card — CHT-4, streaming_protocol.md §7
// ---------------------------------------------------------------------------

interface ClarificationCardProps {
  clarification: Clarification;
  onAnswer: (answer: { selected_option_ids: string[]; freeform?: string }) => void;
}

export function ClarificationCard({ clarification, onAnswer }: ClarificationCardProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [freeform, setFreeform] = useState('');

  const toggle = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (clarification.allow_multiple) {
        next.has(id) ? next.delete(id) : next.add(id);
      } else {
        return new Set([id]);
      }
      return next;
    });
  };

  const canSubmit = selected.size > 0 || (clarification.allow_freeform && freeform.trim().length > 0);

  return (
    <Card accent="blue" style={{ margin: '8px 0', maxWidth: 460 }}>
      <p style={{ margin: '0 0 12px', fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>
        {clarification.question}
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {clarification.options.map(opt => {
          const isSelected = selected.has(opt.id);
          return (
            <button
              key={opt.id}
              onClick={() => toggle(opt.id)}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                padding: '8px 12px',
                background: isSelected ? 'rgba(79,127,255,0.15)' : 'var(--bg-overlay)',
                border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 6,
                cursor: 'pointer',
                fontFamily: 'inherit',
                fontSize: 13,
                color: 'var(--text)',
                textAlign: 'left',
                transition: 'background 120ms, border-color 120ms',
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: clarification.allow_multiple ? 3 : '50%',
                  border: `2px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                  background: isSelected ? 'var(--accent)' : 'none',
                  flexShrink: 0,
                  marginTop: 1,
                }}
              />
              <div>
                <span>
                  {opt.label}
                  {opt.is_recommended && (
                    <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                      (recommended)
                    </span>
                  )}
                </span>
                {opt.description && (
                  <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--text-muted)' }}>
                    {opt.description}
                  </p>
                )}
              </div>
            </button>
          );
        })}
        {clarification.allow_freeform && (
          <div style={{ marginTop: 4 }}>
            <label
              htmlFor={`clarification-freeform-${clarification.id}`}
              style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}
            >
              Yes, and… (add anything else)
            </label>
            <textarea
              id={`clarification-freeform-${clarification.id}`}
              value={freeform}
              onChange={e => setFreeform(e.target.value)}
              rows={2}
              style={{
                width: '100%',
                resize: 'vertical',
                background: 'var(--bg-overlay)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                color: 'var(--text)',
                fontFamily: 'inherit',
                fontSize: 13,
                padding: '6px 10px',
                boxSizing: 'border-box',
              }}
            />
          </div>
        )}
        <Button
          variant="primary"
          onClick={() => onAnswer({ selected_option_ids: [...selected], freeform: freeform || undefined })}
          disabled={!canSubmit}
          style={{ marginTop: 4, alignSelf: 'flex-start' }}
        >
          Continue
        </Button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Review-gate card — streaming_protocol.md §8
// ---------------------------------------------------------------------------

interface ReviewCardProps {
  review: ReviewItem;
  onDecide: (decision: 'approve' | 'reject' | 'request_changes', note?: string) => void;
}

export function ReviewCard({ review, onDecide }: ReviewCardProps) {
  const [note, setNote] = useState('');

  return (
    <Card accent="yellow" style={{ margin: '8px 0', maxWidth: 500 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span aria-hidden="true" style={{ fontSize: 18 }}>🛡</span>
        <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>
          Review required — candidate output
        </span>
      </div>
      <div
        style={{
          padding: '8px 12px',
          background: 'var(--bg-overlay)',
          borderRadius: 6,
          marginBottom: 10,
        }}
      >
        <p style={{ margin: '0 0 6px', fontWeight: 500, color: 'var(--text)', fontSize: 13 }}>
          {review.artifact_ref.title}
        </p>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)' }}>{review.rationale}</p>
        {review.risks.length > 0 && (
          <ul style={{ margin: '6px 0 0', paddingLeft: 16, fontSize: 12, color: 'var(--warning)' }}>
            {review.risks.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        )}
      </div>
      <textarea
        placeholder="Optional note…"
        value={note}
        onChange={e => setNote(e.target.value)}
        rows={2}
        style={{
          width: '100%',
          resize: 'vertical',
          background: 'var(--bg-overlay)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          color: 'var(--text)',
          fontFamily: 'inherit',
          fontSize: 13,
          padding: '6px 10px',
          boxSizing: 'border-box',
          marginBottom: 10,
        }}
      />
      <div style={{ display: 'flex', gap: 8 }}>
        <Button variant="primary" onClick={() => onDecide('approve', note || undefined)}>
          Approve
        </Button>
        <Button variant="secondary" onClick={() => onDecide('request_changes', note || undefined)}>
          Request changes
        </Button>
        <Button variant="danger" onClick={() => onDecide('reject', note || undefined)}>
          Reject
        </Button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Run error notice
// ---------------------------------------------------------------------------

interface RunErrorNoticeProps {
  error: RunError;
  onDismiss?: () => void;
}

function RunErrorNotice({ error, onDismiss }: RunErrorNoticeProps) {
  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        padding: '6px 10px',
        background: 'rgba(224,82,82,0.12)',
        border: '1px solid var(--danger)',
        borderRadius: 6,
        fontSize: 12,
        color: 'var(--danger)',
        margin: '4px 0',
      }}
    >
      <span aria-hidden="true">✕</span>
      <span style={{ flex: 1 }}>{error.message}</span>
      {onDismiss && !error.fatal && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss error"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontSize: 14 }}
        >
          ×
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Assistant turn
// ---------------------------------------------------------------------------

interface AssistantTurnProps {
  state: StreamingRunState;
  onAnswerClarification?: (answer: { selected_option_ids: string[]; freeform?: string }) => void;
  onReviewDecision?: (decision: 'approve' | 'reject' | 'request_changes', note?: string) => void;
  onViewRun?: () => void;
}

export function AssistantTurn({
  state,
  onAnswerClarification,
  onReviewDecision,
  onViewRun,
}: AssistantTurnProps) {
  const [dismissedErrors, setDismissedErrors] = useState<Set<string>>(new Set());

  const visibleErrors = state.errors.filter(
    e => !dismissedErrors.has(e.code + (e.at ?? ''))
  );

  const bodyText = state.reportText || state.messageText;

  return (
    <div
      role="article"
      aria-label="Assistant message"
      style={{ margin: '8px 0' }}
    >
      {/* Thinking disclosure */}
      {(state.thinking || state.thinkingSummary) && (
        <ThinkingDisclosure
          text={state.thinking}
          summary={state.thinkingSummary}
        />
      )}

      {/* Activity log */}
      {(state.intentLabel || state.activityRows.length > 0) && (
        <ToolCallTimeline
          rows={state.activityRows}
          intentLabel={state.intentLabel}
          planRevision={state.plan?.revision}
        />
      )}

      {/* Message body */}
      {bodyText && (
        <div
          style={{
            fontSize: 14,
            lineHeight: 1.7,
            color: 'var(--text)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {bodyText}
          {state.status === 'running' && (
            <span
              aria-label="Streaming"
              style={{
                display: 'inline-block',
                width: 2,
                height: '1em',
                background: 'var(--text)',
                marginLeft: 2,
                verticalAlign: 'middle',
                animation: 'blink 1s step-end infinite',
              }}
            />
          )}
        </div>
      )}

      {/* Artifact bubbles */}
      {state.artifacts.length > 0 && (
        <div
          aria-label="Artifacts"
          style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '10px 0' }}
        >
          {state.artifacts.map(a => (
            <ArtifactBubble key={a.id} artifact={a} />
          ))}
        </div>
      )}

      {/* Clarification card */}
      {state.pendingClarification && onAnswerClarification && (
        <ClarificationCard
          clarification={state.pendingClarification}
          onAnswer={onAnswerClarification}
        />
      )}

      {/* Review gate card */}
      {state.pendingReview && onReviewDecision && (
        <ReviewCard
          review={state.pendingReview}
          onDecide={onReviewDecision}
        />
      )}

      {/* Non-fatal error notices */}
      {visibleErrors.map((err, i) => (
        <RunErrorNotice
          key={`${err.code}-${i}`}
          error={err}
          onDismiss={
            !err.fatal
              ? () => setDismissedErrors(prev => new Set([...prev, err.code + (err.at ?? '')]))
              : undefined
          }
        />
      ))}

      {/* Footer */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginTop: 8,
          fontSize: 11,
          color: 'var(--text-muted)',
        }}
      >
        {state.model && (
          <span style={{ fontFamily: 'var(--font-mono)' }}>
            {state.model}{state.provider && ` · ${state.provider}`}
          </span>
        )}
        {onViewRun && (
          <button
            onClick={onViewRun}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent)',
              cursor: 'pointer',
              fontSize: 11,
              padding: 0,
              fontFamily: 'inherit',
            }}
          >
            view run →
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Types for composed ChatMessage
// ---------------------------------------------------------------------------

export interface ChatTurn {
  id: string;
  role: 'user' | 'assistant';
  /** For user turns: raw message text */
  userMessage?: string;
  /** For assistant turns: streaming run state */
  runState?: StreamingRunState;
  timestamp?: string;
}

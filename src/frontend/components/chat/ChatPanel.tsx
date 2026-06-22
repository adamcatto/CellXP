'use client';

import React, { useState, useEffect, useRef, useCallback, useId } from 'react';
import type { SessionId, RunId, ArtifactRef, ClarificationAnswer, ReviewDecisionRequest } from '../../lib/types';
import { api } from '../../lib/api';
import {
  connectToRunStream,
  applyRunEvent,
  makeEmptyStreamState,
  type StreamingRunState,
} from '../../lib/streaming';
import { UserTurn, AssistantTurn, type ChatTurn } from './ChatMessage';
import { ChatInput } from './ChatInput';

// ---------------------------------------------------------------------------
// Thread header
// ---------------------------------------------------------------------------

interface ThreadHeaderProps {
  title: string;
  organism?: string;
  assembly?: string;
}

function ThreadHeader({ title, organism, assembly }: ThreadHeaderProps) {
  return (
    <div
      style={{
        padding: '10px 16px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        flexShrink: 0,
      }}
    >
      <h1 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>{title}</h1>
      {organism && (
        <span
          style={{
            fontSize: 11,
            padding: '2px 8px',
            background: 'var(--bg-overlay)',
            borderRadius: 10,
            color: 'var(--text-muted)',
          }}
        >
          {organism}{assembly ? ` · ${assembly}` : ''}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Jump-to-latest button
// ---------------------------------------------------------------------------

function JumpToLatest({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label="Jump to latest message"
      style={{
        position: 'absolute',
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'var(--bg-raised)',
        border: '1px solid var(--border)',
        borderRadius: 20,
        padding: '4px 14px',
        fontSize: 12,
        color: 'var(--text)',
        cursor: 'pointer',
        boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
        zIndex: 10,
      }}
    >
      ↓ Jump to latest
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main ChatPanel
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  sessionId: SessionId;
  /** Initial run history to hydrate from the run snapshot API */
  initialRunIds?: RunId[];
  organism?: string;
  assembly?: string;
  title?: string;
  pinnedEntities?: string[];
  recentArtifacts?: ArtifactRef[];
  onArtifactOpen?: (artifactId: string) => void;
  onRunOpen?: (runId: RunId) => void;
}

export function ChatPanel({
  sessionId,
  title = 'CellXP',
  organism,
  assembly,
  pinnedEntities = [],
  recentArtifacts = [],
  onArtifactOpen: _onArtifactOpen,
  onRunOpen,
}: ChatPanelProps) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [activeRunId, setActiveRunId] = useState<RunId | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const disposeStreamRef = useRef<(() => void) | null>(null);
  const idCounter = useRef(0);
  const liveRegionId = useId();

  const nextId = () => `turn-${++idCounter.current}`;

  // Auto-scroll unless user has scrolled up
  const scrollToBottom = useCallback(() => {
    const el = threadRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    if (!userScrolledUp) scrollToBottom();
  }, [turns, userScrolledUp, scrollToBottom]);

  const handleScroll = () => {
    const el = threadRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    setUserScrolledUp(!atBottom);
  };

  // Patch the active assistant turn's run state
  const patchRun = useCallback((runId: RunId, updater: (prev: StreamingRunState) => StreamingRunState) => {
    setTurns(prev =>
      prev.map(t =>
        t.role === 'assistant' && t.runState?.runId === runId
          ? { ...t, runState: updater(t.runState!) }
          : t,
      ),
    );
  }, []);

  // Open SSE stream for a run
  const openStream = useCallback((runId: RunId) => {
    disposeStreamRef.current?.();
    setActiveRunId(runId);
    setIsRunning(true);

    const dispose = connectToRunStream(runId, {
      onEvent: (type, event) => {
        patchRun(runId, prev => applyRunEvent(prev, type, event));
        if (type === 'run.completed') {
          setIsRunning(false);
          setActiveRunId(null);
        }
      },
      onError: () => {
        setIsRunning(false);
      },
      onClose: () => {
        setIsRunning(false);
      },
    });
    disposeStreamRef.current = dispose;
  }, [patchRun]);

  const handleSend = useCallback(async (message: string) => {
    if (isRunning) return;

    const userTurnId = nextId();
    const assistantTurnId = nextId();

    // Add user turn immediately
    setTurns(prev => [
      ...prev,
      {
        id: userTurnId,
        role: 'user',
        userMessage: message,
        timestamp: new Date().toISOString(),
      },
    ]);

    // Add placeholder assistant turn
    let placeholderRunId = `optimistic-${assistantTurnId}`;
    setTurns(prev => [
      ...prev,
      {
        id: assistantTurnId,
        role: 'assistant',
        runState: makeEmptyStreamState(placeholderRunId),
        timestamp: new Date().toISOString(),
      },
    ]);
    setUserScrolledUp(false);

    try {
      const response = await api.runs.create(sessionId, {
        message,
        client_request_id: assistantTurnId,
      });
      placeholderRunId = response.run_id;

      // Replace placeholder state with the real run id
      setTurns(prev =>
        prev.map(t =>
          t.id === assistantTurnId
            ? { ...t, runState: makeEmptyStreamState(response.run_id) }
            : t,
        ),
      );
      openStream(response.run_id);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Request failed';
      setTurns(prev =>
        prev.map(t =>
          t.id === assistantTurnId
            ? {
                ...t,
                runState: {
                  ...makeEmptyStreamState(placeholderRunId),
                  status: 'failed',
                  errors: [{ code: 'request_failed', message: errorMessage, fatal: true }],
                },
              }
            : t,
        ),
      );
      setIsRunning(false);
    }
  }, [isRunning, sessionId, openStream]);

  const handleStop = useCallback(async () => {
    if (!activeRunId) return;
    await api.runs.cancel(activeRunId).catch(() => {});
    disposeStreamRef.current?.();
    setIsRunning(false);
    setActiveRunId(null);
  }, [activeRunId]);

  const handleAnswerClarification = useCallback(async (answer: ClarificationAnswer) => {
    const runId = activeRunId;
    if (!runId) return;
    // Find the clarification id from the active run state
    const activeTurn = turns.find(
      t => t.role === 'assistant' && t.runState?.runId === runId,
    );
    const clarId = activeTurn?.runState?.pendingClarification?.id;
    if (!clarId) return;
    try {
      await api.runs.answerClarification(runId, clarId, answer);
      patchRun(runId, prev => ({ ...prev, pendingClarification: null, status: 'running' }));
    } catch {
      // Leave the card visible so the user can retry
    }
  }, [activeRunId, turns, patchRun]);

  const handleReviewDecision = useCallback(async (
    decision: 'approve' | 'reject' | 'request_changes',
    note?: string,
  ) => {
    const runId = activeRunId;
    if (!runId) return;
    const activeTurn = turns.find(
      t => t.role === 'assistant' && t.runState?.runId === runId,
    );
    const reviewId = activeTurn?.runState?.pendingReview?.id;
    if (!reviewId) return;
    const body: ReviewDecisionRequest = {
      decision,
      note,
      expected_run_status: 'awaiting_review',
    };
    try {
      await api.runs.reviewDecision(runId, reviewId, body);
      patchRun(runId, prev => ({ ...prev, pendingReview: null, status: 'running' }));
    } catch {
      // Leave card visible
    }
  }, [activeRunId, turns, patchRun]);

  // Cleanup on unmount
  useEffect(() => () => disposeStreamRef.current?.(), []);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--bg)',
        position: 'relative',
      }}
    >
      <ThreadHeader title={title} organism={organism} assembly={assembly} />

      {/* ARIA live region for streaming announcements (CHT-8) */}
      <div
        id={liveRegionId}
        role="status"
        aria-live="polite"
        aria-atomic="false"
        className="sr-only"
      >
        {isRunning ? 'Assistant is responding…' : ''}
      </div>

      {/* Thread */}
      <div
        ref={threadRef}
        onScroll={handleScroll}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
        }}
      >
        {turns.length === 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--text-muted)',
              fontSize: 14,
              textAlign: 'center',
            }}
          >
            <div>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🧬</div>
              <p>Ask about a gene, variant, structure, or pathway.</p>
              <p style={{ fontSize: 12 }}>
                Type <code style={{ color: 'var(--accent)' }}>/</code> for macros or{' '}
                <code style={{ color: 'var(--accent)' }}>@</code> to reference an entity.
              </p>
            </div>
          </div>
        )}

        {turns.map(turn => (
          <div key={turn.id}>
            {turn.role === 'user' ? (
              <UserTurn
                message={turn.userMessage ?? ''}
                timestamp={turn.timestamp}
              />
            ) : turn.runState ? (
              <AssistantTurn
                state={turn.runState}
                onAnswerClarification={handleAnswerClarification}
                onReviewDecision={handleReviewDecision}
                onViewRun={
                  onRunOpen && turn.runState.runId && !turn.runState.runId.startsWith('optimistic')
                    ? () => onRunOpen(turn.runState!.runId)
                    : undefined
                }
              />
            ) : null}
          </div>
        ))}
      </div>

      {/* Jump-to-latest */}
      {userScrolledUp && (
        <div style={{ position: 'relative' }}>
          <JumpToLatest onClick={() => { scrollToBottom(); setUserScrolledUp(false); }} />
        </div>
      )}

      {/* Composer */}
      <ChatInput
        sessionId={sessionId}
        running={isRunning}
        onSend={handleSend}
        onStop={handleStop}
        pinnedEntities={pinnedEntities}
        recentArtifacts={recentArtifacts}
      />
    </div>
  );
}

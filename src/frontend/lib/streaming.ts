// SSE streaming client — api_contracts.md §8, streaming_protocol.md §2, §9.
// Opens an EventSource for a run, routes typed events to handlers, and
// manages reconnect via Last-Event-ID (the browser EventSource does this
// automatically when the server closes the stream).

import type { RunEvent, StreamEventType } from './types';

export type EventHandler = (type: StreamEventType, event: RunEvent) => void;

export interface StreamOptions {
  onEvent: EventHandler;
  onError?: (err: Error) => void;
  onClose?: () => void;
  /** Reconnect with a specific last-seen sequence (passed as ?last_event_id=N) */
  lastEventId?: number;
}

// All named SSE event types the server emits.
const STREAM_EVENT_TYPES: StreamEventType[] = [
  'reasoning.delta',
  'reasoning.summary',
  'intent.classified',
  'activity.update',
  'step.started',
  'step.finished',
  'plan.updated',
  'subtask.updated',
  'message.delta',
  'report.delta',
  'artifact.added',
  'artifact.updated',
  'evidence.added',
  'clarification.requested',
  'review.requested',
  'error.added',
  'run.status',
  'run.completed',
  'stream.reset',
];

const TERMINAL_EVENTS: StreamEventType[] = ['run.completed', 'run.status'];

/**
 * Open an SSE stream for a run.
 * Returns a dispose function that closes the connection.
 */
export function connectToRunStream(runId: string, opts: StreamOptions): () => void {
  const base =
    (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE) ||
    'http://localhost:8000/api/v1';

  const params = opts.lastEventId !== undefined
    ? `?last_event_id=${opts.lastEventId}`
    : '';
  const url = `${base}/runs/${runId}/events${params}`;

  let es: EventSource | null = null;
  let disposed = false;

  function open() {
    if (disposed) return;
    es = new EventSource(url, { withCredentials: false });

    const handleMessage = (e: MessageEvent) => {
      if (disposed) return;
      try {
        const event = JSON.parse(e.data as string) as RunEvent;
        const type = e.type as StreamEventType;
        opts.onEvent(type, event);
        // Close after terminal event so we don't keep a dead stream open.
        if (TERMINAL_EVENTS.includes(type)) {
          const statusData = event.data as { status?: string };
          if (
            type === 'run.completed' ||
            (type === 'run.status' &&
              (statusData.status === 'completed' ||
               statusData.status === 'failed' ||
               statusData.status === 'cancelled'))
          ) {
            dispose();
            opts.onClose?.();
          }
        }
      } catch {
        // Ignore malformed frames.
      }
    };

    for (const t of STREAM_EVENT_TYPES) {
      es.addEventListener(t, handleMessage);
    }
    // Fallback for unnamed frames.
    es.addEventListener('message', handleMessage);

    es.onerror = () => {
      if (disposed) return;
      opts.onError?.(new Error('SSE connection error'));
      // EventSource will retry automatically; we don't need to do anything.
    };
  }

  function dispose() {
    disposed = true;
    if (es) {
      es.close();
      es = null;
    }
  }

  open();
  return dispose;
}

// ---------------------------------------------------------------------------
// In-memory run state accumulator
// ---------------------------------------------------------------------------

/** Mutable view of a run that the SSE event stream patches progressively. */
export interface StreamingRunState {
  runId: string;
  status: string;
  thinking: string;
  thinkingSummary: string;
  intentLabel: string;
  activityRows: ActivityRow[];
  messageText: string;
  reportText: string;
  artifacts: import('./types').ArtifactRef[];
  evidence: import('./types').EvidenceItem[];
  errors: import('./types').RunError[];
  pendingClarification: import('./types').Clarification | null;
  pendingReview: import('./types').ReviewItem | null;
  plan: import('./types').RunPlan | null;
  model?: string;
  provider?: string;
}

export interface ActivityRow {
  id: string;
  label: string;
  tool?: string;
  status: 'running' | 'completed' | 'failed' | 'queued';
  inputSummary?: string;
  outputSummary?: string;
  durationMs?: number;
  toolVersion?: string;
  interim?: string;
}

export function makeEmptyStreamState(runId: string): StreamingRunState {
  return {
    runId,
    status: 'queued',
    thinking: '',
    thinkingSummary: '',
    intentLabel: '',
    activityRows: [],
    messageText: '',
    reportText: '',
    artifacts: [],
    evidence: [],
    errors: [],
    pendingClarification: null,
    pendingReview: null,
    plan: null,
  };
}

/**
 * Apply a single SSE event to produce the next run state.
 * Returns a new object (does not mutate `prev`).
 */
export function applyRunEvent(
  prev: StreamingRunState,
  type: StreamEventType,
  event: RunEvent,
): StreamingRunState {
  const d = event.data;
  switch (type) {
    case 'reasoning.delta': {
      const token = (d.token as string | undefined) ?? '';
      return { ...prev, thinking: prev.thinking + token };
    }
    case 'reasoning.summary': {
      return { ...prev, thinkingSummary: (d.summary as string | undefined) ?? '', thinking: '' };
    }
    case 'intent.classified': {
      return { ...prev, intentLabel: (d.label as string | undefined) ?? '' };
    }
    case 'activity.update': {
      const stepId = d.step_id as string | undefined;
      if (!stepId) return prev;
      const interim = d.status as string | undefined;
      const rows = prev.activityRows.map(r =>
        r.id === stepId ? { ...r, interim } : r,
      );
      return { ...prev, activityRows: rows };
    }
    case 'step.started': {
      const row: ActivityRow = {
        id: (d.step_id as string) ?? event.seq.toString(),
        label: (d.label as string | undefined) ?? (d.tool as string | undefined) ?? 'Tool call',
        tool: d.tool as string | undefined,
        toolVersion: d.tool_version as string | undefined,
        inputSummary: d.input_summary as string | undefined,
        status: 'running',
      };
      return { ...prev, activityRows: [...prev.activityRows, row] };
    }
    case 'step.finished': {
      const stepId = d.step_id as string | undefined;
      const rows = prev.activityRows.map(r =>
        r.id === stepId
          ? {
              ...r,
              status: (d.error ? 'failed' : 'completed') as ActivityRow['status'],
              outputSummary: d.output_summary as string | undefined,
              durationMs: d.duration_ms as number | undefined,
            }
          : r,
      );
      return { ...prev, activityRows: rows };
    }
    case 'plan.updated': {
      const plan = d as unknown as import('./types').RunPlan;
      return { ...prev, plan };
    }
    case 'message.delta': {
      const token = (d.token as string | undefined) ?? '';
      return { ...prev, messageText: prev.messageText + token };
    }
    case 'report.delta': {
      const token = (d.token as string | undefined) ?? '';
      return { ...prev, reportText: prev.reportText + token };
    }
    case 'artifact.added': {
      const ref = d as unknown as import('./types').ArtifactRef;
      return { ...prev, artifacts: [...prev.artifacts, ref] };
    }
    case 'artifact.updated': {
      const updated = d as unknown as import('./types').ArtifactRef;
      const artifacts = prev.artifacts.map(a => (a.id === updated.id ? updated : a));
      return { ...prev, artifacts };
    }
    case 'evidence.added': {
      const item = d as unknown as import('./types').EvidenceItem;
      return { ...prev, evidence: [...prev.evidence, item] };
    }
    case 'clarification.requested': {
      const clarification = d as unknown as import('./types').Clarification;
      return { ...prev, pendingClarification: clarification, status: 'awaiting_input' };
    }
    case 'review.requested': {
      const review = d as unknown as import('./types').ReviewItem;
      return { ...prev, pendingReview: review, status: 'awaiting_review' };
    }
    case 'error.added': {
      const err = d as unknown as import('./types').RunError;
      return { ...prev, errors: [...prev.errors, err] };
    }
    case 'run.status': {
      return { ...prev, status: (d.status as string | undefined) ?? prev.status };
    }
    case 'run.completed': {
      return {
        ...prev,
        status: 'completed',
        model: (d.model as string | undefined) ?? prev.model,
        provider: (d.provider as string | undefined) ?? prev.provider,
      };
    }
    default:
      return prev;
  }
}

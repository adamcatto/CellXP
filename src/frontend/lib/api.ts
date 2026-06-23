// REST client for CellXP — api_contracts.md §3–§7.
// Base URL from `getApiBase()` (same-origin `/api/v1` by default in dev).

import { getApiBase } from './apiBase';
import type {
  SessionId, RunId, ArtifactId, ClarificationId, ReviewItemId, UploadId,
  SessionSummary, SessionType, SessionDefaults,
  CreateRunRequest, CreateRunResponse, RunSnapshot, RunStep, EvidenceItem,
  ClarificationAnswer, ReviewDecisionRequest,
  ArtifactManifest, ArtifactRef, GuidePool,
  UploadRef,
  CollectionResponse,
} from './types';

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

interface ApiError extends Error {
  status: number;
  code?: string;
  body?: unknown;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${getApiBase()}${path}`, init);
  if (!res.ok) {
    const problem = await res.json().catch(() => ({ title: res.statusText }));
    const message =
      (typeof problem.title === 'string' && problem.title) ||
      (typeof problem.detail === 'string' && problem.detail) ||
      res.statusText;
    const err = new Error(message) as ApiError;
    err.status = res.status;
    err.code = problem.code;
    err.body = problem;
    throw err;
  }
  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

const sessions = {
  list: (): Promise<CollectionResponse<SessionSummary>> =>
    request('GET', '/sessions'),

  get: (id: SessionId): Promise<SessionSummary> =>
    request('GET', `/sessions/${id}`),

  create: (body: {
    type: SessionType;
    title: string;
    defaults?: SessionDefaults;
  }): Promise<SessionSummary> =>
    request('POST', '/sessions', body),

  patch: (
    id: SessionId,
    body: { title?: string; defaults?: Partial<SessionDefaults>; expected_revision: number },
  ): Promise<SessionSummary> =>
    request('PATCH', `/sessions/${id}`, body),

  delete: (id: SessionId): Promise<void> =>
    request('DELETE', `/sessions/${id}`),

  runs: (id: SessionId): Promise<CollectionResponse<RunSnapshot>> =>
    request('GET', `/sessions/${id}/runs`),

  artifacts: (id: SessionId): Promise<CollectionResponse<ArtifactRef>> =>
    request('GET', `/sessions/${id}/artifacts`),

  files: (id: SessionId): Promise<CollectionResponse<UploadRef>> =>
    request('GET', `/sessions/${id}/files`),

  upload: async (id: SessionId, file: File, input_kind?: string): Promise<UploadRef> => {
    const form = new FormData();
    form.append('file', file);
    if (input_kind) form.append('input_kind', input_kind);
    const res = await fetch(`${getApiBase()}/sessions/${id}/uploads`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const problem = await res.json().catch(() => ({ title: res.statusText }));
      const message =
        (typeof problem.title === 'string' && problem.title) ||
        (typeof problem.detail === 'string' && problem.detail) ||
        res.statusText;
      const err = new Error(message) as ApiError;
      err.status = res.status;
      throw err;
    }
    return res.json();
  },
};

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

const runs = {
  create: (sessionId: SessionId, body: CreateRunRequest): Promise<CreateRunResponse> =>
    request('POST', `/sessions/${sessionId}/runs`, body),

  get: (id: RunId): Promise<RunSnapshot> =>
    request('GET', `/runs/${id}`),

  cancel: (id: RunId): Promise<void> =>
    request('POST', `/runs/${id}/cancel`),

  reproduce: (id: RunId): Promise<CreateRunResponse> =>
    request('POST', `/runs/${id}/reproduce`),

  steps: (id: RunId, cursor?: string): Promise<CollectionResponse<RunStep>> =>
    request('GET', `/runs/${id}/steps${cursor ? `?cursor=${cursor}` : ''}`),

  evidence: (id: RunId, cursor?: string): Promise<CollectionResponse<EvidenceItem>> =>
    request('GET', `/runs/${id}/evidence${cursor ? `?cursor=${cursor}` : ''}`),

  answerClarification: (
    runId: RunId,
    clarId: ClarificationId,
    body: ClarificationAnswer,
  ): Promise<void> =>
    request('POST', `/runs/${runId}/clarifications/${clarId}/answer`, body),

  reviewDecision: (
    runId: RunId,
    reviewId: ReviewItemId,
    body: ReviewDecisionRequest,
  ): Promise<void> =>
    request('POST', `/runs/${runId}/reviews/${reviewId}/decision`, body),
};

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

const artifacts = {
  get: (id: ArtifactId): Promise<ArtifactManifest> =>
    request('GET', `/artifacts/${id}`),

  guidePools: (id: ArtifactId): Promise<CollectionResponse<GuidePool>> =>
    request('GET', `/artifacts/${id}/guide-pools`),

  saveGuidePool: (
    id: ArtifactId,
    body: { session_id: SessionId; name: string; guide_ids: string[]; expected_revision?: number },
    poolId?: string,
  ): Promise<GuidePool> => request(
    poolId ? 'PUT' : 'POST',
    poolId ? `/artifacts/${id}/guide-pools/${poolId}` : `/artifacts/${id}/guide-pools`,
    body,
  ),

  /** URL of raw artifact content (use with fetch + Authorization if needed) */
  contentUrl: (id: ArtifactId): string =>
    `${getApiBase()}/artifacts/${id}/content`,

  /** URL template for tile requests */
  tileUrl: (
    id: ArtifactId,
    contig: string,
    start: number,
    end: number,
    resolution: number,
  ): string =>
    `${getApiBase()}/artifacts/${id}/tiles?contig=${encodeURIComponent(contig)}&start=${start}&end=${end}&res=${resolution}`,

  requestExport: (
    id: ArtifactId,
    format: string,
    viewState?: Record<string, unknown>,
  ): Promise<{ export_id: string; status: string }> =>
    request('POST', `/artifacts/${id}/exports`, { format, view_state: viewState }),

  getExport: (
    id: ArtifactId,
    exportId: string,
  ): Promise<{ export_id: string; status: string; download_url?: string }> =>
    request('GET', `/artifacts/${id}/exports/${exportId}`),
};

// ---------------------------------------------------------------------------
// Upload helpers (session-scoped; exposed here for convenience)
// ---------------------------------------------------------------------------

export const uploadFile = sessions.upload;
export const uploadId = (ref: UploadRef): UploadId => ref.id;

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

export const api = { sessions, runs, artifacts } as const;

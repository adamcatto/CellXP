// Wire types for CellXP — derived from api_contracts.md, streaming_protocol.md, artifact_model.md.
// All IDs are opaque UUIDv7/ULID strings; timestamps are UTC ISO-8601.

// ---------------------------------------------------------------------------
// Opaque ID aliases
// ---------------------------------------------------------------------------

export type RunId = string;
export type SessionId = string;
export type ArtifactId = string;
export type StepId = string;
export type EvidenceId = string;
export type SubtaskId = string;
export type UploadId = string;
export type ClarificationId = string;
export type ReviewItemId = string;

// ---------------------------------------------------------------------------
// Enums / union literals
// ---------------------------------------------------------------------------

export type RunStatus =
  | 'queued'
  | 'running'
  | 'awaiting_input'
  | 'awaiting_review'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type ArtifactType =
  | 'genome_track'
  | 'locus_plot'
  | 'feature_table'
  | 'coordinate_table'
  | 'motif_logo'
  | 'structure_3d'
  | 'contact_map'
  | 'sequence_viewer'
  | 'guide_table'
  | 'off_target_table'
  | 'report'
  | 'protein_design_table'
  | 'origami_layout'
  | 'citation_set'
  | 'file';

export type ArtifactStatus = 'pending' | 'ready' | 'partial' | 'failed';

export type ReviewStatus =
  | 'not_required'
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'changes_requested';

export type StepStatus = 'queued' | 'running' | 'completed' | 'failed' | 'skipped';

export type SessionType =
  | 'variant_interpretation'
  | 'genome_editing'
  | 'strain_optimization'
  | 'structure_and_binding'
  | 'annotation_and_discovery'
  | 'dna_nanotech'
  | 'literature'
  | 'general';

export type TrackFamily =
  | 'gene_model'
  | 'regulatory'
  | 'conservation'
  | 'assay_delta'
  | 'splice_score'
  | 'binding'
  | 'accessibility'
  | 'dna_shape'
  | 'crispr_guides'
  | 'off_target'
  | 'gwas'
  | 'variant_overlay'
  | 'custom';

export type StreamEventType =
  | 'reasoning.delta'
  | 'reasoning.summary'
  | 'intent.classified'
  | 'activity.update'
  | 'step.started'
  | 'step.finished'
  | 'plan.updated'
  | 'subtask.updated'
  | 'message.delta'
  | 'report.delta'
  | 'artifact.added'
  | 'artifact.updated'
  | 'evidence.added'
  | 'clarification.requested'
  | 'review.requested'
  | 'error.added'
  | 'run.status'
  | 'run.completed'
  | 'stream.reset';

// ---------------------------------------------------------------------------
// Coordinate types
// ---------------------------------------------------------------------------

export interface CoordinateFrame {
  kind: 'genomic' | 'sequence' | 'structure' | 'shape' | 'none';
  organism?: string;
  assembly?: string;
  contig?: string;
  /** 0-based half-open start */
  start?: number;
  end?: number;
  strand?: '+' | '-' | '.';
  circular?: boolean;
}

export interface Confidence {
  /** Calibrated 0–1 */
  value?: number;
  band?: 'high' | 'medium' | 'low' | 'very_low';
  model?: string;
  notes?: string[];
}

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

export interface ArtifactRef {
  id: ArtifactId;
  type: ArtifactType;
  title: string;
  status: ArtifactStatus;
  run_id: RunId;
  subtask_id?: SubtaskId;
  step_id?: StepId;
  summary?: Record<string, unknown>;
  storage_ref?: string;
  actionable: boolean;
  review_status: ReviewStatus;
  created_at: string;
}

export interface ExportDescriptor {
  format: string;
  label: string;
  media_type: string;
}

export interface AccessibilityMetadata {
  table_fallback_url?: string;
  summary_text?: string;
  alt?: string;
}

export interface Interaction {
  kind: string;
  label: string;
  target?: string;
}

/** Full manifest returned by GET /artifacts/{id} */
export interface ArtifactManifest extends ArtifactRef {
  schema_version: string;
  payload_schema: string;
  description?: string;
  revision: number;
  session_id: SessionId;
  evidence_ids: EvidenceId[];
  source_artifact_ids: ArtifactId[];
  /** ID of artifact this corrects */
  supersedes?: ArtifactId;
  /** Inline payload when small enough (≤ OBJECT_INLINE_MAX) */
  payload?: Record<string, unknown>;
  content_type?: string;
  content_hash?: string;
  coordinate_frame?: CoordinateFrame;
  units?: Record<string, string>;
  confidence?: Confidence;
  limitations?: string[];
  transform_notes?: string[];
  interactions?: Interaction[];
  exports?: ExportDescriptor[];
  accessibility?: AccessibilityMetadata;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Evidence
// ---------------------------------------------------------------------------

export interface EvidenceItem {
  id: EvidenceId;
  run_id: RunId;
  kind: 'model_output' | 'db_record' | 'citation' | 'upload';
  source: string;
  accession?: string;
  url?: string;
  title?: string;
  summary?: string;
  confidence?: Confidence;
  retrieved_at?: string;
  step_id?: StepId;
}

// ---------------------------------------------------------------------------
// Clarification / Review
// ---------------------------------------------------------------------------

export interface ClarificationOption {
  id: string;
  label: string;
  description?: string;
  is_recommended?: boolean;
}

export interface Clarification {
  id: ClarificationId;
  run_id: RunId;
  question: string;
  options: ClarificationOption[];
  allow_multiple: boolean;
  allow_freeform: boolean;
  node?: string;
}

export interface ClarificationAnswer {
  selected_option_ids: string[];
  freeform?: string;
}

export interface ReviewItem {
  id: ReviewItemId;
  run_id: RunId;
  artifact_ref: ArtifactRef;
  rationale: string;
  risks: string[];
  node?: string;
}

export interface ReviewDecisionRequest {
  decision: 'approve' | 'reject' | 'request_changes';
  note?: string;
  expected_run_status: 'awaiting_review';
}

// ---------------------------------------------------------------------------
// Execution trace
// ---------------------------------------------------------------------------

export interface RunStep {
  id: StepId;
  run_id: RunId;
  subtask_id?: SubtaskId;
  tool: string;
  label: string;
  status: StepStatus;
  tool_version?: string;
  input_summary?: string;
  output_summary?: string;
  output_preview?: Record<string, unknown>;
  evidence_ids: EvidenceId[];
  artifact_ids: ArtifactId[];
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  error?: string;
}

export interface Subtask {
  id: SubtaskId;
  label: string;
  capability?: string;
  status: StepStatus;
  depends_on: SubtaskId[];
  step_ids: StepId[];
}

export interface RunPlan {
  intent: string;
  subtasks: Subtask[];
  revision: number;
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export interface SessionDefaults {
  organism?: string;
  assembly?: string;
  persona?: string;
  review_posture?: 'standard' | 'strict';
}

export interface SessionSummary {
  id: SessionId;
  title: string;
  type: SessionType;
  defaults: SessionDefaults;
  revision: number;
  created_at: string;
  updated_at: string;
  run_count: number;
  artifact_count: number;
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

export interface RawInput {
  kind: string;
  value: string | Record<string, unknown>;
  upload_id?: UploadId;
}

export interface RunOverrides {
  organism?: string;
  assembly?: string;
  persona?: string;
  model?: string;
  budget_tokens?: number;
  budget_steps?: number;
}

export interface CreateRunRequest {
  message?: string;
  inputs?: RawInput[];
  overrides?: RunOverrides;
  referenced_artifact_ids?: ArtifactId[];
  /** Client-generated deduplication key */
  client_request_id: string;
}

export interface CreateRunResponse {
  run_id: RunId;
  session_id: SessionId;
  status: RunStatus;
  stream_url: string;
  created_at: string;
}

export interface RunError {
  code: string;
  message: string;
  fatal: boolean;
  step_id?: StepId;
  at?: string;
}

export interface TokenUsage {
  input: number;
  output: number;
  cache_read?: number;
}

export interface RunSnapshot {
  id: RunId;
  session_id: SessionId;
  status: RunStatus;
  message?: string;
  report?: string;
  plan?: RunPlan;
  normalized_inputs?: Record<string, unknown>;
  steps: RunStep[];
  evidence: EvidenceItem[];
  artifacts: ArtifactRef[];
  errors: RunError[];
  pending_clarification?: Clarification;
  pending_review?: ReviewItem;
  overrides?: RunOverrides;
  model?: string;
  provider?: string;
  elapsed_ms?: number;
  token_usage?: TokenUsage;
  created_at: string;
  updated_at: string;
  reproduces_run_id?: RunId;
}

export interface UploadRef {
  id: UploadId;
  filename: string;
  media_type: string;
  size: number;
  content_hash: string;
  status: 'uploaded' | 'scanning' | 'ready' | 'rejected';
  input_kind?: string;
}

// ---------------------------------------------------------------------------
// SSE events
// ---------------------------------------------------------------------------

/** Outer envelope for every SSE frame */
export interface RunEvent {
  schema_version: string;
  run_id: RunId;
  seq: number;
  at: string;
  data: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Genome browser
// ---------------------------------------------------------------------------

export interface TrackDescriptor {
  id: string;
  artifact_id?: ArtifactId;
  title: string;
  family: TrackFamily;
  coordinate_frame: CoordinateFrame;
  visible: boolean;
  height_px: number;
  color?: string;
  confidence_band?: boolean;
  transform_notes?: string[];
  storage_ref?: string;
}

/** Genomic viewport displayed in the browser pane */
export interface GenomeViewport {
  organism: string;
  assembly: string;
  contig: string;
  start: number;
  end: number;
  strand: '+' | '-' | '.';
  circular: boolean;
}

// ---------------------------------------------------------------------------
// Generic collection response
// ---------------------------------------------------------------------------

export interface CollectionResponse<T> {
  items: T[];
  next_cursor: string | null;
}

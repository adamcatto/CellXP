// Artifact helpers — artifact_model.md.
// Type guards, display names, deep-link paths, and export format selection.

import type { ArtifactRef, ArtifactType, ArtifactManifest, ReviewStatus } from './types';

// ---------------------------------------------------------------------------
// Display metadata
// ---------------------------------------------------------------------------

const ARTIFACT_LABELS: Record<ArtifactType, string> = {
  genome_track: 'Genome Track',
  locus_plot: 'Locus Plot',
  feature_table: 'Feature Table',
  coordinate_table: 'Coordinate Table',
  motif_logo: 'Motif Logo',
  structure_3d: '3D Structure',
  contact_map: 'Contact Map',
  sequence_viewer: 'Sequence',
  guide_table: 'Guide Table',
  off_target_table: 'Off-target Table',
  report: 'Report',
  protein_design_table: 'Protein Designs',
  origami_layout: 'Origami Layout',
  citation_set: 'Citations',
  file: 'File',
};

/** Human-readable display name for an artifact type. */
export function artifactLabel(type: ArtifactType): string {
  return ARTIFACT_LABELS[type] ?? type;
}

const ARTIFACT_ICONS: Record<ArtifactType, string> = {
  genome_track: '🧬',
  locus_plot: '📊',
  feature_table: '📋',
  coordinate_table: '📍',
  motif_logo: '🔠',
  structure_3d: '🔮',
  contact_map: '🗺',
  sequence_viewer: '🔡',
  guide_table: '✂️',
  off_target_table: '⚠️',
  report: '📄',
  protein_design_table: '🧪',
  origami_layout: '📐',
  citation_set: '📚',
  file: '📎',
};

export function artifactIcon(type: ArtifactType): string {
  return ARTIFACT_ICONS[type] ?? '▪';
}

// ---------------------------------------------------------------------------
// Deep links
// ---------------------------------------------------------------------------

export function artifactPath(id: string): string {
  return `/artifacts/${id}`;
}

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------

export const isGenomicArtifact = (type: ArtifactType): boolean =>
  ['genome_track', 'locus_plot', 'feature_table', 'coordinate_table', 'motif_logo'].includes(type);

export const isStructuralArtifact = (type: ArtifactType): boolean =>
  ['structure_3d', 'contact_map'].includes(type);

export const isTableArtifact = (type: ArtifactType): boolean =>
  ['feature_table', 'coordinate_table', 'guide_table', 'off_target_table', 'protein_design_table'].includes(type);

export const isActionableArtifact = (ref: ArtifactRef): boolean =>
  ref.actionable;

export const needsReview = (ref: ArtifactRef): boolean =>
  ref.actionable && (ref.review_status === 'pending' || ref.review_status === 'not_required');

// ---------------------------------------------------------------------------
// Review status display
// ---------------------------------------------------------------------------

const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  not_required: '',
  pending: 'Pending review',
  approved: 'Approved',
  rejected: 'Rejected',
  changes_requested: 'Changes requested',
};

export function reviewStatusLabel(status: ReviewStatus): string {
  return REVIEW_STATUS_LABELS[status] ?? status;
}

// ---------------------------------------------------------------------------
// Export format selection
// ---------------------------------------------------------------------------

/** Suggest the most useful export format for a given artifact type. */
export function preferredExportFormat(type: ArtifactType): string {
  if (isGenomicArtifact(type)) return 'bed';
  if (type === 'structure_3d') return 'pdb';
  if (type === 'report') return 'pdf';
  if (isTableArtifact(type)) return 'tsv';
  return 'png';
}

// ---------------------------------------------------------------------------
// Manifest helpers
// ---------------------------------------------------------------------------

export function manifestSummaryText(manifest: ArtifactManifest): string {
  return manifest.accessibility?.summary_text
    ?? manifest.description
    ?? `${artifactLabel(manifest.type)}: ${manifest.title}`;
}

export function manifestHasInlinePayload(manifest: ArtifactManifest): boolean {
  return manifest.payload !== undefined && manifest.payload !== null;
}

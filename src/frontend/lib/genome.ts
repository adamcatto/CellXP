// Genome coordinate utilities — coordinate_systems.md, genome_browser.md §3.
// All internal intervals are 0-based half-open; display uses 1-based inclusive.

import type { CoordinateFrame, GenomeViewport } from './types';

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

/** Format a genomic position as a comma-separated number (1-based display). */
export function formatBp(pos: number): string {
  return pos.toLocaleString('en-US');
}

/** Format a viewport as "chr17:43,044,295-43,125,483" (1-based inclusive). */
export function formatLocus(vp: GenomeViewport): string {
  // Convert 0-based half-open [start, end) → 1-based inclusive [start+1, end].
  return `${vp.contig}:${formatBp(vp.start + 1)}-${formatBp(vp.end)}`;
}

/** Format organism + assembly chip label, e.g. "Homo sapiens · GRCh38". */
export function formatAssemblyChip(vp: Pick<GenomeViewport, 'organism' | 'assembly'>): string {
  return `${vp.organism} · ${vp.assembly}`;
}

/** Span in base pairs. */
export function viewportSpan(vp: GenomeViewport): number {
  return vp.end - vp.start;
}

/** Human-readable span, e.g. "81.2 kb" or "1.3 Mb". */
export function formatSpan(bp: number): string {
  if (bp >= 1_000_000) return `${(bp / 1_000_000).toFixed(1)} Mb`;
  if (bp >= 1_000) return `${(bp / 1_000).toFixed(1)} kb`;
  return `${bp} bp`;
}

// ---------------------------------------------------------------------------
// Parsing
// ---------------------------------------------------------------------------

const LOCUS_RE = /^([^\s:]+):(\d[\d,]*)-(\d[\d,]*)$/;

function stripCommas(s: string): number {
  return parseInt(s.replace(/,/g, ''), 10);
}

/**
 * Parse a locus string like "chr17:43,044,295-43,125,483".
 * Returns null if unparseable (caller should hit the reference service).
 * Input is 1-based inclusive display; output is 0-based half-open.
 */
export function parseLocus(input: string): Pick<GenomeViewport, 'contig' | 'start' | 'end'> | null {
  const m = LOCUS_RE.exec(input.trim());
  if (!m) return null;
  const contig = m[1];
  const start1 = stripCommas(m[2]); // 1-based inclusive → subtract 1
  const end1 = stripCommas(m[3]);   // 1-based inclusive → end is already half-open when used as-is
  if (isNaN(start1) || isNaN(end1) || start1 < 1 || end1 < start1) return null;
  return { contig, start: start1 - 1, end: end1 };
}

// ---------------------------------------------------------------------------
// Viewport manipulation
// ---------------------------------------------------------------------------

const MIN_SPAN = 50;    // base pairs
const MAX_SPAN = 250_000_000;  // 250 Mb

/** Zoom by a factor around the viewport centre (factor > 1 = zoom in). */
export function zoomViewport(vp: GenomeViewport, factor: number): GenomeViewport {
  const centre = (vp.start + vp.end) / 2;
  const halfSpan = viewportSpan(vp) / 2 / factor;
  const start = Math.max(0, Math.round(centre - halfSpan));
  const end = Math.round(centre + halfSpan);
  const span = Math.max(MIN_SPAN, Math.min(MAX_SPAN, end - start));
  return { ...vp, start, end: start + span };
}

/** Pan by a fraction of the current span (positive = rightward). */
export function panViewport(vp: GenomeViewport, fraction: number): GenomeViewport {
  const delta = Math.round(viewportSpan(vp) * fraction);
  const start = Math.max(0, vp.start + delta);
  return { ...vp, start, end: start + viewportSpan(vp) };
}

/** Clamp a viewport so it doesn't exceed contig bounds. */
export function clampViewport(vp: GenomeViewport, contigLen: number): GenomeViewport {
  const span = viewportSpan(vp);
  const start = Math.max(0, Math.min(vp.start, contigLen - span));
  const end = Math.min(contigLen, start + span);
  return { ...vp, start, end };
}

// ---------------------------------------------------------------------------
// Coordinate frame helpers
// ---------------------------------------------------------------------------

export function frameToViewport(frame: CoordinateFrame): Partial<GenomeViewport> | null {
  if (frame.kind !== 'genomic') return null;
  return {
    organism: frame.organism,
    assembly: frame.assembly,
    contig: frame.contig,
    start: frame.start,
    end: frame.end,
    strand: frame.strand ?? '+',
    circular: frame.circular ?? false,
  };
}

/** Pixel offset for a genomic position given a viewport and canvas width. */
export function bpToPixel(bp: number, vp: GenomeViewport, canvasWidth: number): number {
  return ((bp - vp.start) / viewportSpan(vp)) * canvasWidth;
}

/** Genomic position from a pixel offset. */
export function pixelToBp(px: number, vp: GenomeViewport, canvasWidth: number): number {
  return Math.round(vp.start + (px / canvasWidth) * viewportSpan(vp));
}

// ---------------------------------------------------------------------------
// Deep zoom threshold
// ---------------------------------------------------------------------------

/** At ≤ this many bp the browser should render individual bases. */
export const BASE_RENDER_THRESHOLD = 200;

export function isBaseZoom(vp: GenomeViewport): boolean {
  return viewportSpan(vp) <= BASE_RENDER_THRESHOLD;
}

// ---------------------------------------------------------------------------
// Viewport URL encoding
// ---------------------------------------------------------------------------

/** Build the query string for a genome browser deep link. */
export function viewportToParams(vp: GenomeViewport): URLSearchParams {
  return new URLSearchParams({
    org: vp.organism,
    asm: vp.assembly,
    contig: vp.contig,
    start: String(vp.start),
    end: String(vp.end),
    strand: vp.strand,
  });
}

export function paramsToViewport(
  params: URLSearchParams,
  defaults: Partial<GenomeViewport> = {},
): GenomeViewport | null {
  const org = params.get('org') ?? defaults.organism;
  const asm = params.get('asm') ?? defaults.assembly;
  const contig = params.get('contig') ?? defaults.contig;
  const startStr = params.get('start');
  const endStr = params.get('end');
  if (!org || !asm || !contig || !startStr || !endStr) return null;
  return {
    organism: org,
    assembly: asm,
    contig,
    start: parseInt(startStr, 10),
    end: parseInt(endStr, 10),
    strand: (params.get('strand') as GenomeViewport['strand']) ?? '+',
    circular: params.get('circular') === 'true',
  };
}

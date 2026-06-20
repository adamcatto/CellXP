'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import type { TrackDescriptor, GenomeViewport } from '../../lib/types';
import { bpToPixel, viewportSpan } from '../../lib/genome';

// ---------------------------------------------------------------------------
// Data types for track payloads
// ---------------------------------------------------------------------------

/** A single rendered interval (exon, regulatory element, GWAS hit, etc.) */
export interface Interval {
  start: number;  // 0-based
  end: number;
  label?: string;
  color?: string;
  score?: number;
  strand?: '+' | '-' | '.';
}

/** A single-value wiggle datum */
export interface WiggleDatum {
  position: number;  // 0-based
  value: number;
}

export type TrackPayload =
  | { kind: 'intervals'; intervals: Interval[] }
  | { kind: 'wiggle'; data: WiggleDatum[]; min: number; max: number }
  | { kind: 'empty' };

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------

const TRACK_COLORS = {
  gene_model: '#4f7fff',
  regulatory: '#3ecf8e',
  conservation: '#f5a623',
  assay_delta: '#e05252',
  crispr_guides: '#9b59b6',
  gwas: '#e67e22',
  variant_overlay: '#e74c3c',
  default: '#7b82a0',
};

function trackColor(family: TrackDescriptor['family']): string {
  return TRACK_COLORS[family as keyof typeof TRACK_COLORS] ?? TRACK_COLORS.default;
}

// ---------------------------------------------------------------------------
// Canvas renderer
// ---------------------------------------------------------------------------

interface TrackViewerProps {
  track: TrackDescriptor;
  payload: TrackPayload;
  viewport: GenomeViewport;
  width: number;
  onFeatureClick?: (interval: Interval) => void;
  onFeatureHover?: (interval: Interval | null) => void;
}

export function TrackViewer({
  track,
  payload,
  viewport,
  width,
  onFeatureClick,
  onFeatureHover,
}: TrackViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const height = track.height_px;
  const color = track.color ?? trackColor(track.family);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    if (payload.kind === 'empty') {
      // Draw a loading placeholder
      ctx.fillStyle = 'rgba(123,130,160,0.1)';
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = 'rgba(123,130,160,0.4)';
      ctx.font = '11px system-ui';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('Loading…', width / 2, height / 2);
      return;
    }

    if (payload.kind === 'intervals') {
      const { intervals } = payload;
      ctx.fillStyle = color;
      const boxH = Math.min(height - 8, 18);
      const y = (height - boxH) / 2;
      for (const ivl of intervals) {
        if (ivl.end < viewport.start || ivl.start > viewport.end) continue;
        const x1 = bpToPixel(ivl.start, viewport, width);
        const x2 = bpToPixel(ivl.end, viewport, width);
        const w = Math.max(1, x2 - x1);
        ctx.fillStyle = ivl.color ?? color;
        ctx.fillRect(x1, y, w, boxH);

        // Strand arrow
        if (ivl.strand && ivl.strand !== '.' && w > 12) {
          ctx.fillStyle = 'rgba(255,255,255,0.6)';
          ctx.font = '10px sans-serif';
          ctx.textBaseline = 'middle';
          ctx.fillText(ivl.strand === '+' ? '>' : '<', x1 + w / 2, height / 2);
        }

        // Label at sufficient zoom
        if (ivl.label && w > 40) {
          ctx.fillStyle = 'rgba(255,255,255,0.9)';
          ctx.font = '10px system-ui';
          ctx.textBaseline = 'middle';
          ctx.textAlign = 'center';
          ctx.fillText(ivl.label, x1 + w / 2, height / 2);
        }
      }
      ctx.textAlign = 'left';
    }

    if (payload.kind === 'wiggle') {
      const { data, min, max } = payload;
      const range = max - min || 1;
      const midY = height / 2;
      const isSignedWiggle = min < 0;

      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      let first = true;
      for (const d of data) {
        if (d.position < viewport.start || d.position > viewport.end) continue;
        const x = bpToPixel(d.position, viewport, width);
        const normalised = (d.value - min) / range;
        const y = height - normalised * height;
        if (first) { ctx.moveTo(x, y); first = false; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Fill under curve
      ctx.globalAlpha = 0.2;
      ctx.fillStyle = color;
      ctx.lineTo(width, isSignedWiggle ? midY : height);
      ctx.lineTo(0, isSignedWiggle ? midY : height);
      ctx.fill();
      ctx.globalAlpha = 1;

      // Zero line for signed wiggle
      if (isSignedWiggle) {
        ctx.strokeStyle = 'rgba(123,130,160,0.4)';
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.moveTo(0, midY);
        ctx.lineTo(width, midY);
        ctx.stroke();
      }
    }
  }, [payload, viewport, width, height, color]);

  useEffect(() => { draw(); }, [draw]);

  // Hit-test intervals on click
  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (payload.kind !== 'intervals' || !onFeatureClick) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = e.clientX - rect.left;
    const bp = viewport.start + (px / width) * viewportSpan(viewport);
    const hit = payload.intervals.find(i => i.start <= bp && bp <= i.end);
    if (hit) onFeatureClick(hit);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (payload.kind !== 'intervals' || !onFeatureHover) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = e.clientX - rect.left;
    const bp = viewport.start + (px / width) * viewportSpan(viewport);
    const hit = payload.intervals.find(i => i.start <= bp && bp <= i.end) ?? null;
    onFeatureHover(hit);
  };

  return (
    <div style={{ position: 'relative', width, height }}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ display: 'block', width, height }}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => onFeatureHover?.(null)}
        aria-label={`${track.title} track`}
        role="img"
      />
    </div>
  );
}

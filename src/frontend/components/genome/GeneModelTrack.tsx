'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import type { GenomeViewport } from '../../lib/types';
import { bpToPixel } from '../../lib/genome';

// ---------------------------------------------------------------------------
// Gene model types
// ---------------------------------------------------------------------------

export type ExonKind = 'CDS' | 'UTR5' | 'UTR3' | 'non_coding';

export interface Exon {
  start: number;  // 0-based
  end: number;
  kind: ExonKind;
}

export interface Transcript {
  id: string;
  geneSymbol: string;
  start: number;
  end: number;
  strand: '+' | '-';
  exons: Exon[];
  biotype?: string;
  isCanonical?: boolean;
}

// ---------------------------------------------------------------------------
// Colors
// ---------------------------------------------------------------------------

const EXON_COLORS: Record<ExonKind, string> = {
  CDS: '#4f7fff',
  UTR5: '#6fa4ff',
  UTR3: '#6fa4ff',
  non_coding: '#4a5580',
};

const INTRON_COLOR = 'rgba(79,127,255,0.4)';
const INTRON_LINE_HEIGHT = 1;
const EXON_HEIGHT = 14;
const TRANSCRIPT_ROW_H = 26;

// ---------------------------------------------------------------------------
// GeneModelTrack
// ---------------------------------------------------------------------------

interface GeneModelTrackProps {
  transcripts: Transcript[];
  viewport: GenomeViewport;
  width: number;
  onTranscriptClick?: (t: Transcript) => void;
}

export function GeneModelTrack({
  transcripts,
  viewport,
  width,
  onTranscriptClick,
}: GeneModelTrackProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const height = Math.max(TRANSCRIPT_ROW_H, transcripts.length * TRANSCRIPT_ROW_H);

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

    if (transcripts.length === 0) {
      ctx.fillStyle = 'rgba(123,130,160,0.4)';
      ctx.font = '11px system-ui';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('No genes in this region', width / 2, height / 2);
      return;
    }

    for (let ti = 0; ti < transcripts.length; ti++) {
      const tx = transcripts[ti];
      if (tx.end < viewport.start || tx.start > viewport.end) continue;

      const rowY = ti * TRANSCRIPT_ROW_H;
      const midY = rowY + TRANSCRIPT_ROW_H / 2;
      const exonY = midY - EXON_HEIGHT / 2;

      const txX1 = Math.max(0, bpToPixel(tx.start, viewport, width));
      const txX2 = Math.min(width, bpToPixel(tx.end, viewport, width));

      // Intron backbone
      ctx.strokeStyle = INTRON_COLOR;
      ctx.lineWidth = INTRON_LINE_HEIGHT;
      ctx.beginPath();
      ctx.moveTo(txX1, midY);
      ctx.lineTo(txX2, midY);
      ctx.stroke();

      // Strand arrows along backbone
      const arrowSpacing = 40;
      const arrowChar = tx.strand === '+' ? '>' : '<';
      ctx.fillStyle = INTRON_COLOR;
      ctx.font = '10px sans-serif';
      ctx.textBaseline = 'middle';
      ctx.textAlign = 'center';
      for (let ax = txX1 + 10; ax < txX2 - 10; ax += arrowSpacing) {
        ctx.fillText(arrowChar, ax, midY);
      }

      // Exons
      for (const exon of tx.exons) {
        if (exon.end < viewport.start || exon.start > viewport.end) continue;
        const ex1 = Math.max(0, bpToPixel(exon.start, viewport, width));
        const ex2 = Math.min(width, bpToPixel(exon.end, viewport, width));
        const ew = Math.max(1, ex2 - ex1);

        ctx.fillStyle = EXON_COLORS[exon.kind];
        ctx.fillRect(ex1, exonY, ew, EXON_HEIGHT);

        // Exon border
        ctx.strokeStyle = 'rgba(0,0,0,0.2)';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(ex1, exonY, ew, EXON_HEIGHT);
      }

      // Gene symbol label
      if (tx.isCanonical) {
        const labelX = Math.max(4, txX1 + 2);
        ctx.fillStyle = 'var(--text)';
        ctx.font = `${tx.isCanonical ? '600 ' : ''}10px system-ui`;
        ctx.textBaseline = 'top';
        ctx.textAlign = 'left';
        ctx.fillStyle = '#e8eaf0';
        ctx.fillText(tx.geneSymbol, labelX, rowY + 2);
      }
    }
  }, [transcripts, viewport, width, height]);

  useEffect(() => { draw(); }, [draw]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onTranscriptClick) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const py = e.clientY - rect.top;
    const ti = Math.floor(py / TRANSCRIPT_ROW_H);
    if (ti >= 0 && ti < transcripts.length) {
      onTranscriptClick(transcripts[ti]);
    }
  };

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ display: 'block', width, height }}
      onClick={handleClick}
      aria-label="Gene model track"
      role="img"
    />
  );
}

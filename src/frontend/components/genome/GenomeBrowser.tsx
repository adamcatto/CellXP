'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import type { TrackDescriptor, GenomeViewport, ArtifactRef } from '../../lib/types';
import {
  formatLocus,
  formatAssemblyChip,
  formatSpan,
  viewportSpan,
  parseLocus,
  zoomViewport,
  panViewport,
  bpToPixel,
} from '../../lib/genome';
import { TrackViewer, type TrackPayload } from './TrackViewer';
import { GeneModelTrack, type Transcript } from './GeneModelTrack';

// ---------------------------------------------------------------------------
// Coordinate ruler
// ---------------------------------------------------------------------------

interface RulerProps {
  viewport: GenomeViewport;
  width: number;
}

function CoordinateRuler({ viewport, width }: RulerProps) {
  const span = viewportSpan(viewport);
  // Pick a sensible tick interval
  const rawInterval = span / 8;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawInterval)));
  const tickInterval = Math.ceil(rawInterval / magnitude) * magnitude;
  const ticks: number[] = [];
  const firstTick = Math.ceil(viewport.start / tickInterval) * tickInterval;
  for (let t = firstTick; t <= viewport.end; t += tickInterval) ticks.push(t);

  return (
    <div style={{ position: 'relative', height: 24, flexShrink: 0 }}>
      <svg width={width} height={24} style={{ display: 'block' }} aria-hidden="true">
        {/* Baseline */}
        <line x1={0} y1={20} x2={width} y2={20} stroke="var(--border)" strokeWidth={1} />
        {ticks.map(t => {
          const x = bpToPixel(t, viewport, width);
          return (
            <g key={t}>
              <line x1={x} y1={14} x2={x} y2={22} stroke="var(--border)" strokeWidth={1} />
              <text
                x={x}
                y={12}
                fontSize={10}
                textAnchor="middle"
                fill="var(--text-muted)"
              >
                {(t + 1).toLocaleString()}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Track header
// ---------------------------------------------------------------------------

interface TrackHeaderProps {
  track: TrackDescriptor;
  onToggle: () => void;
}

function TrackHeader({ track, onToggle }: TrackHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '2px 8px',
        background: 'var(--bg-overlay)',
        borderBottom: '1px solid var(--border)',
        height: 24,
        flexShrink: 0,
      }}
    >
      <button
        onClick={onToggle}
        aria-pressed={track.visible}
        style={{
          background: 'none',
          border: 'none',
          color: track.visible ? 'var(--text)' : 'var(--text-muted)',
          cursor: 'pointer',
          fontSize: 11,
          fontFamily: 'inherit',
          fontWeight: 600,
          padding: '0 4px 0 0',
          flex: 1,
          textAlign: 'left',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {track.title}
      </button>
      {track.transform_notes && track.transform_notes.length > 0 && (
        <span
          title={track.transform_notes.join('; ')}
          style={{ fontSize: 10, color: 'var(--warning)', marginLeft: 4 }}
        >
          ⚠
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

interface TooltipState {
  x: number;
  y: number;
  text: string;
}

// ---------------------------------------------------------------------------
// Main GenomeBrowser
// ---------------------------------------------------------------------------

export interface GenomeBrowserProps {
  initialViewport: GenomeViewport;
  tracks: TrackDescriptor[];
  payloads: Record<string, TrackPayload>;
  /** Gene model transcripts, keyed by artifact/track id or empty for all */
  transcripts?: Transcript[];
  onViewportChange?: (vp: GenomeViewport) => void;
  onFeatureAction?: (action: string, details: Record<string, unknown>) => void;
  /** Called when the user types a gene/rsID that the browser can't resolve locally */
  onLocusSearch?: (query: string) => void;
  style?: React.CSSProperties;
}

export function GenomeBrowser({
  initialViewport,
  tracks,
  payloads,
  transcripts = [],
  onViewportChange,
  onFeatureAction,
  onLocusSearch,
  style,
}: GenomeBrowserProps) {
  const [viewport, setViewport] = useState<GenomeViewport>(initialViewport);
  const [localTracks, setLocalTracks] = useState<TrackDescriptor[]>(tracks);
  const [locusInput, setLocusInput] = useState('');
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(800);

  // Observe container width
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      setContainerWidth(entries[0].contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Sync external track list
  useEffect(() => { setLocalTracks(tracks); }, [tracks]);

  const updateViewport = useCallback((vp: GenomeViewport) => {
    setViewport(vp);
    onViewportChange?.(vp);
  }, [onViewportChange]);

  // Wheel zoom
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.3 : 0.77;
    updateViewport(zoomViewport(viewport, factor));
  };

  // Drag pan
  const dragStart = useRef<{ x: number; startBp: number } | null>(null);
  const handleMouseDown = (e: React.MouseEvent) => {
    dragStart.current = { x: e.clientX, startBp: viewport.start };
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragStart.current) return;
    const dx = dragStart.current.x - e.clientX;
    const fraction = dx / containerWidth;
    const delta = Math.round(fraction * viewportSpan(viewport));
    updateViewport({
      ...viewport,
      start: Math.max(0, dragStart.current.startBp + delta),
      end: Math.max(viewportSpan(viewport), dragStart.current.startBp + delta + viewportSpan(viewport)),
    });
  };
  const handleMouseUp = () => { dragStart.current = null; };

  // Locus search
  const handleLocusSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = locusInput.trim();
    if (!q) return;
    const parsed = parseLocus(q);
    if (parsed) {
      updateViewport({ ...viewport, ...parsed });
      setLocusInput('');
    } else {
      // Pass to reference service
      onLocusSearch?.(q);
    }
  };

  // Keyboard shortcuts: +/- zoom, arrow pan, g to search
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === '+' || e.key === '=') updateViewport(zoomViewport(viewport, 1.5));
    if (e.key === '-') updateViewport(zoomViewport(viewport, 0.67));
    if (e.key === 'ArrowRight') updateViewport(panViewport(viewport, 0.2));
    if (e.key === 'ArrowLeft') updateViewport(panViewport(viewport, -0.2));
  }, [viewport, updateViewport]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const toggleTrackVisible = (id: string) => {
    setLocalTracks(prev =>
      prev.map(t => t.id === id ? { ...t, visible: !t.visible } : t),
    );
  };

  const visibleTracks = localTracks.filter(t => t.visible);

  // Gene model track — find it in localTracks or render inline
  const geneModelTrack = localTracks.find(t => t.family === 'gene_model');

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        overflow: 'hidden',
        ...style,
      }}
    >
      {/* Chrome — assembly/coordinate info + search */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '6px 10px',
          background: 'var(--bg-raised)',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
          flexWrap: 'wrap',
        }}
      >
        {/* GBR-1: always show organism/assembly/contig/strand */}
        <span
          aria-label="Assembly"
          style={{
            fontSize: 11,
            padding: '2px 8px',
            background: 'var(--bg-overlay)',
            borderRadius: 10,
            color: 'var(--text-muted)',
            flexShrink: 0,
          }}
        >
          {formatAssemblyChip(viewport)}
        </span>
        <span
          aria-label="Contig"
          style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}
        >
          {viewport.contig}
        </span>
        <span
          aria-label="Strand"
          style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}
        >
          {viewport.strand !== '.' ? viewport.strand : ''}
          {viewport.circular && ' ⟳'}
        </span>

        {/* Locus search */}
        <form onSubmit={handleLocusSearch} style={{ flex: 1, display: 'flex', gap: 4, minWidth: 160 }}>
          <input
            value={locusInput}
            onChange={e => setLocusInput(e.target.value)}
            placeholder={formatLocus(viewport)}
            aria-label="Locus search"
            style={{
              flex: 1,
              background: 'var(--bg-overlay)',
              border: '1px solid var(--border)',
              borderRadius: 4,
              color: 'var(--text)',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              padding: '3px 8px',
            }}
          />
          <button
            type="submit"
            aria-label="Go to locus"
            style={{
              background: 'var(--accent)',
              border: 'none',
              borderRadius: 4,
              color: '#fff',
              cursor: 'pointer',
              fontSize: 12,
              padding: '3px 8px',
            }}
          >
            Go
          </button>
        </form>

        {/* Span display */}
        <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>
          {formatSpan(viewportSpan(viewport))}
        </span>

        {/* Zoom controls */}
        <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
          <button
            onClick={() => updateViewport(zoomViewport(viewport, 1.5))}
            aria-label="Zoom in"
            title="Zoom in (+)"
            style={iconBtnStyle}
          >
            +
          </button>
          <button
            onClick={() => updateViewport(zoomViewport(viewport, 0.67))}
            aria-label="Zoom out"
            title="Zoom out (-)"
            style={iconBtnStyle}
          >
            −
          </button>
          <button
            onClick={() => updateViewport(panViewport(viewport, -0.5))}
            aria-label="Pan left"
            title="Pan left (←)"
            style={iconBtnStyle}
          >
            ←
          </button>
          <button
            onClick={() => updateViewport(panViewport(viewport, 0.5))}
            aria-label="Pan right"
            title="Pan right (→)"
            style={iconBtnStyle}
          >
            →
          </button>
        </div>
      </div>

      {/* Track container */}
      <div
        ref={containerRef}
        style={{ flex: 1, overflowY: 'auto', position: 'relative', cursor: 'grab' }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* Coordinate ruler */}
        <CoordinateRuler viewport={viewport} width={containerWidth} />

        {/* Gene model track (always first) */}
        {geneModelTrack && geneModelTrack.visible && (
          <div>
            <TrackHeader track={geneModelTrack} onToggle={() => toggleTrackVisible(geneModelTrack.id)} />
            <GeneModelTrack
              transcripts={transcripts}
              viewport={viewport}
              width={containerWidth}
              onTranscriptClick={t => {
                onFeatureAction?.('transcript_click', { transcript_id: t.id, gene: t.geneSymbol });
              }}
            />
          </div>
        )}

        {/* Other tracks */}
        {visibleTracks
          .filter(t => t.family !== 'gene_model')
          .map(track => {
            const payload: TrackPayload = payloads[track.id] ?? { kind: 'empty' };
            return (
              <div key={track.id}>
                <TrackHeader track={track} onToggle={() => toggleTrackVisible(track.id)} />
                <TrackViewer
                  track={track}
                  payload={payload}
                  viewport={viewport}
                  width={containerWidth}
                  onFeatureClick={ivl => {
                    onFeatureAction?.('feature_click', {
                      track_id: track.id,
                      interval: ivl,
                    });
                  }}
                  onFeatureHover={ivl => {
                    if (!ivl) { setTooltip(null); return; }
                    // Position tooltip near center of feature
                    const x = bpToPixel((ivl.start + ivl.end) / 2, viewport, containerWidth);
                    setTooltip({ x, y: 0, text: ivl.label ?? `${ivl.start + 1}–${ivl.end}` });
                  }}
                />
              </div>
            );
          })}

        {/* Tooltip */}
        {tooltip && (
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              left: tooltip.x + 8,
              top: 40,
              background: 'var(--bg-raised)',
              border: '1px solid var(--border)',
              borderRadius: 4,
              padding: '3px 8px',
              fontSize: 11,
              color: 'var(--text)',
              pointerEvents: 'none',
              zIndex: 20,
              boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
              whiteSpace: 'nowrap',
            }}
          >
            {tooltip.text}
          </div>
        )}

        {/* Empty state */}
        {localTracks.length === 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: 200,
              color: 'var(--text-muted)',
              fontSize: 13,
            }}
          >
            No tracks. Open a genome artifact to add tracks.
          </div>
        )}
      </div>

      {/* Track list toggle panel (collapsed by default) */}
      <TrackListPanel
        tracks={localTracks}
        onToggle={toggleTrackVisible}
      />

      {/* Accessibility: summary text (GBR-8) */}
      <div className="sr-only" aria-live="polite">
        {`Genome browser at ${formatLocus(viewport)}, ${visibleTracks.length} tracks visible`}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Track list panel
// ---------------------------------------------------------------------------

function TrackListPanel({
  tracks,
  onToggle,
}: {
  tracks: TrackDescriptor[];
  onToggle: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  if (tracks.length === 0) return null;

  return (
    <div style={{ borderTop: '1px solid var(--border)', flexShrink: 0 }}>
      <button
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          width: '100%',
          padding: '5px 10px',
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          fontSize: 11,
          fontFamily: 'inherit',
          textAlign: 'left',
        }}
      >
        <span>{open ? '▼' : '▶'}</span>
        Tracks ({tracks.filter(t => t.visible).length}/{tracks.length} visible)
      </button>
      {open && (
        <div style={{ padding: '4px 10px 8px', display: 'flex', flexDirection: 'column', gap: 3 }}>
          {tracks.map(t => (
            <label
              key={t.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 12,
                color: t.visible ? 'var(--text)' : 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={t.visible}
                onChange={() => onToggle(t.id)}
                aria-label={`Toggle ${t.title}`}
              />
              {t.title}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared icon button style
// ---------------------------------------------------------------------------

const iconBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 22,
  height: 22,
  background: 'var(--bg-overlay)',
  border: '1px solid var(--border)',
  borderRadius: 4,
  color: 'var(--text)',
  cursor: 'pointer',
  fontSize: 13,
  fontFamily: 'inherit',
  padding: 0,
};

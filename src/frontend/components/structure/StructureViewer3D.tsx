'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { ArtifactManifest } from '../../lib/types';
import { api } from '../../lib/api';
import { useWorkspaceSelection } from '../../lib/selection';

interface Atom {
  x: number;
  y: number;
  z: number;
  chain: string;
  resi: number;
  residue: string;
  atom: string;
  confidence?: number;
}

export interface StructureViewerAdapter {
  /** Adapter seam for a future Mol* renderer without changing pane or selection contracts. */
  render: (target: HTMLElement, coordinates: string, options: { colorMode: ColorMode; chains: string[] }) => () => void;
}

type ColorMode = 'confidence' | 'chain';

function parsePdb(text: string): Atom[] {
  const atoms: Atom[] = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.startsWith('ATOM') && !line.startsWith('HETATM')) continue;
    const x = Number(line.slice(30, 38));
    const y = Number(line.slice(38, 46));
    const z = Number(line.slice(46, 54));
    const resi = Number(line.slice(22, 26));
    if (![x, y, z, resi].every(Number.isFinite)) continue;
    atoms.push({
      x, y, z, resi,
      atom: line.slice(12, 16).trim(),
      residue: line.slice(17, 20).trim(),
      chain: line.slice(21, 22).trim() || '_',
      confidence: Number.isFinite(Number(line.slice(60, 66))) ? Number(line.slice(60, 66)) / 100 : undefined,
    });
  }
  return atoms;
}

function inlineCoordinates(manifest: ArtifactManifest): string | null {
  const payload = manifest.payload;
  const data = payload?.data as Record<string, unknown> | undefined;
  const value = payload?.pdb ?? payload?.coordinates ?? payload?.structure ?? data?.pdb ?? data?.coordinates;
  return typeof value === 'string' ? value : null;
}

function confidenceColor(value: number | undefined): string {
  if (value === undefined) return '#9aa4b2';
  if (value >= 0.9) return '#315efb';
  if (value >= 0.7) return '#35b6d4';
  if (value >= 0.5) return '#f2c94c';
  return '#e85d75';
}

const CHAIN_COLORS = ['#6e8cff', '#4cc9a4', '#f29e4c', '#d66efd', '#ef6f6c', '#57b8ff'];

export function StructureViewer3D({ manifest, adapter }: { manifest: ArtifactManifest; adapter?: StructureViewerAdapter }) {
  const [coordinates, setCoordinates] = useState<string | null>(() => inlineCoordinates(manifest));
  const [error, setError] = useState<string | null>(null);
  const [colorMode, setColorMode] = useState<ColorMode>('confidence');
  const [hiddenChains, setHiddenChains] = useState<Set<string>>(new Set());
  const [rotation, setRotation] = useState({ x: -0.25, y: 0.35 });
  const drag = useRef<{ x: number; y: number; rx: number; ry: number } | null>(null);
  const adapterTarget = useRef<HTMLDivElement>(null);
  const { selection, publish } = useWorkspaceSelection();

  useEffect(() => {
    const inline = inlineCoordinates(manifest);
    if (inline) { setCoordinates(inline); return; }
    if (!manifest.storage_ref) return;
    const controller = new AbortController();
    fetch(api.artifacts.contentUrl(manifest.id), { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error(`Coordinates unavailable (${response.status})`);
        return response.text();
      })
      .then(setCoordinates)
      .catch(reason => { if (reason.name !== 'AbortError') setError(reason.message); });
    return () => controller.abort();
  }, [manifest]);

  const atoms = useMemo(() => coordinates ? parsePdb(coordinates) : [], [coordinates]);
  const chains = useMemo(() => [...new Set(atoms.map(a => a.chain))].sort(), [atoms]);

  useEffect(() => {
    if (!adapter || !coordinates || !adapterTarget.current) return;
    return adapter.render(adapterTarget.current, coordinates, { colorMode, chains: chains.filter(c => !hiddenChains.has(c)) });
  }, [adapter, coordinates, colorMode, chains, hiddenChains]);

  const visible = atoms.filter(a => !hiddenChains.has(a.chain) && (a.atom === 'CA' || atoms.length < 300));
  const center = visible.length ? visible.reduce((acc, a) => ({ x: acc.x + a.x / visible.length, y: acc.y + a.y / visible.length, z: acc.z + a.z / visible.length }), { x: 0, y: 0, z: 0 }) : { x: 0, y: 0, z: 0 };
  const rotated = visible.map(atom => {
    const px = atom.x - center.x;
    const py = atom.y - center.y;
    const pz = atom.z - center.z;
    const cy = Math.cos(rotation.y); const sy = Math.sin(rotation.y);
    const cx = Math.cos(rotation.x); const sx = Math.sin(rotation.x);
    const x1 = px * cy + pz * sy;
    const z1 = -px * sy + pz * cy;
    return { atom, x: x1, y: py * cx - z1 * sx, z: py * sx + z1 * cx };
  });
  const extent = Math.max(1, ...rotated.flatMap(p => [Math.abs(p.x), Math.abs(p.y)]));
  const selectedChain = selection?.kind === 'residue' ? String(selection.payload.chain ?? '') : '';
  const selectedResi = selection?.kind === 'residue' ? Number(selection.payload.resi) : NaN;

  if (!coordinates && !error) return <p style={messageStyle}>Loading structure coordinates…</p>;
  if (error) return <p role="alert" style={{ ...messageStyle, color: 'var(--danger)' }}>{error}</p>;
  if (!atoms.length) return <p style={messageStyle}>This coordinate format needs a Mol* adapter. PDB previews render directly; the raw coordinate export remains available.</p>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 360 }}>
      <div style={toolbarStyle}>
        <label>Color <select value={colorMode} onChange={event => setColorMode(event.target.value as ColorMode)} style={selectStyle}><option value="confidence">Confidence</option><option value="chain">Chain</option></select></label>
        <span style={{ color: 'var(--text-muted)' }}>{atoms.length.toLocaleString()} atoms · {chains.length} chain{chains.length === 1 ? '' : 's'}</span>
        <button onClick={() => setRotation({ x: -0.25, y: 0.35 })} style={buttonStyle}>Reset view</button>
      </div>
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <div
          style={{ flex: 1, minWidth: 0, position: 'relative', background: '#090d14', cursor: 'grab' }}
          onMouseDown={event => { drag.current = { x: event.clientX, y: event.clientY, rx: rotation.x, ry: rotation.y }; }}
          onMouseMove={event => drag.current && setRotation({ x: drag.current.rx + (event.clientY - drag.current.y) / 160, y: drag.current.ry + (event.clientX - drag.current.x) / 160 })}
          onMouseUp={() => { drag.current = null; }}
          onMouseLeave={() => { drag.current = null; }}
        >
          {adapter ? <div ref={adapterTarget} style={{ width: '100%', height: '100%' }} /> : (
            <svg viewBox="0 0 640 480" role="img" aria-label="Rotatable structure coordinate preview" style={{ width: '100%', height: '100%', display: 'block' }}>
              {rotated.sort((a, b) => a.z - b.z).map((point, index) => {
                const active = point.atom.chain === selectedChain && point.atom.resi === selectedResi;
                const chainIndex = Math.max(0, chains.indexOf(point.atom.chain));
                return <circle key={`${point.atom.chain}-${point.atom.resi}-${point.atom.atom}-${index}`} cx={320 + point.x / extent * 205} cy={240 + point.y / extent * 205} r={active ? 7 : Math.max(1.8, 3.3 + point.z / (extent * 5))} fill={colorMode === 'confidence' ? confidenceColor(point.atom.confidence) : CHAIN_COLORS[chainIndex % CHAIN_COLORS.length]} stroke={active ? '#fff' : 'none'} tabIndex={point.atom.atom === 'CA' ? 0 : undefined} onClick={() => publish({ kind: 'residue', artifact_id: manifest.id, coordinate_frame: { kind: 'structure' }, payload: { chain: point.atom.chain, resi: point.atom.resi } })}><title>{point.atom.chain}:{point.atom.resi} {point.atom.residue} · confidence {point.atom.confidence?.toFixed(2) ?? 'unknown'}</title></circle>;
              })}
            </svg>
          )}
        </div>
        <aside aria-label="Structure chains" style={{ width: 150, padding: 10, overflow: 'auto', borderLeft: '1px solid var(--border)', fontSize: 12 }}>
          <strong style={{ display: 'block', marginBottom: 8 }}>Chains</strong>
          {chains.map((chain, index) => <label key={chain} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 7 }}><input type="checkbox" checked={!hiddenChains.has(chain)} onChange={() => setHiddenChains(current => { const next = new Set(current); next.has(chain) ? next.delete(chain) : next.add(chain); return next; })} /><span style={{ color: CHAIN_COLORS[index % CHAIN_COLORS.length] }}>●</span>{chain}</label>)}
          <p style={{ color: 'var(--text-muted)', lineHeight: 1.4 }}>Select a residue in the view to link compatible sequence panes.</p>
        </aside>
      </div>
      <details style={{ padding: '6px 10px', borderTop: '1px solid var(--border)', fontSize: 11 }}><summary>Accessible residue summary</summary><p>{chains.map(chain => `${chain}: ${new Set(atoms.filter(a => a.chain === chain).map(a => a.resi)).size} residues`).join(' · ')}</p></details>
    </div>
  );
}

const messageStyle: React.CSSProperties = { padding: 20, color: 'var(--text-muted)', fontSize: 13 };
const toolbarStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 12, padding: '6px 10px', borderBottom: '1px solid var(--border)', fontSize: 11 };
const selectStyle: React.CSSProperties = { marginLeft: 5, background: 'var(--bg-overlay)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 4, padding: 2 };
const buttonStyle: React.CSSProperties = { marginLeft: 'auto', background: 'var(--bg-overlay)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 4, padding: '3px 7px', cursor: 'pointer' };

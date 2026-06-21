'use client';

import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ArtifactId, CoordinateFrame } from './types';

export type SelectionKind =
  | 'interval'
  | 'variant'
  | 'residue'
  | 'motif_hit'
  | 'node'
  | 'staple'
  | 'row';

export interface WorkspaceSelection {
  kind: SelectionKind;
  artifact_id?: ArtifactId;
  coordinate_frame: CoordinateFrame;
  payload: Record<string, unknown>;
}

interface SelectionContextValue {
  selection: WorkspaceSelection | null;
  publish: (selection: WorkspaceSelection) => void;
  clear: () => void;
}

const noop = () => undefined;
const SelectionContext = createContext<SelectionContextValue>({
  selection: null,
  publish: noop,
  clear: noop,
});

export function SelectionProvider({ children }: { children: React.ReactNode }) {
  const [selection, setSelection] = useState<WorkspaceSelection | null>(null);
  const publish = useCallback((next: WorkspaceSelection) => setSelection(next), []);
  const clear = useCallback(() => setSelection(null), []);
  const value = useMemo(() => ({ selection, publish, clear }), [selection, publish, clear]);
  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}

/** Opt a pane into or out of the shared bus without unmounting its local viewer state. */
export function SelectionScope({ enabled, children }: { enabled: boolean; children: React.ReactNode }) {
  const parent = useContext(SelectionContext);
  const value = useMemo<SelectionContextValue>(() => enabled ? parent : {
    selection: null,
    publish: noop,
    clear: noop,
  }, [enabled, parent]);
  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}

/** Workspace-local ephemeral selection bus. Safe to use outside a provider (it becomes inert). */
export function useWorkspaceSelection(): SelectionContextValue {
  return useContext(SelectionContext);
}

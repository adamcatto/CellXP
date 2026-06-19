# Interactive Visualization Guidelines

How we build the visual artifacts the agent produces. Specs:
`specs/interface/artifact_model.md` (data contract), `specs/interface/genome_browser.md`,
`specs/interface/streaming_protocol.md` (how artifacts stream), `architecture_overview.md` §3.
Code: `src/frontend/components/{genome,structure,plots}/*`, `services/visualization/`.

## Principles

- **Artifacts are first-class, typed, and provenance-linked.** Every artifact has an `ArtifactRef`
  (`state_schema.md` §10) with `type`, `evidence_ids`, and a `storage_ref` for heavy payloads.
  A visualization with no link back to its evidence/run is a bug (`FR-29`).
- **Data/presentation split.** The backend produces a typed payload (the *what*); the frontend renders
  it (the *how*). Keep transform logic in the visualization service / `lib`, not in components.
- **Progressive rendering.** Artifacts stream as placeholder → populated (`streaming_protocol.md` §6):
  emit `artifact.added` with type+title immediately, then `artifact.updated` with the payload. Never
  block the answer on a heavy render.
- **Interactive + exportable.** Pan/zoom/hover/select where it helps; always offer export (PNG/SVG +
  the underlying data).
- **Coordinates are explicit.** Any genomic view shows assembly + strand + coordinate convention and
  handles organism realities incl. **circular** bacterial genomes (`coordinate_systems.md`).

## Artifact types → renderers

| Artifact type | Renderer (recommended) | Component |
|---|---|---|
| `genome_track` (annotation / delta / binding) | custom Canvas/SVG | `components/genome/*` |
| `locus_plot` (GWAS/association, credible sets) | visx / D3 | `components/plots/LocusPlot.tsx` |
| `contact_map` | Canvas heatmap | `components/plots/ContactMap.tsx` |
| `motif_logo` | sequence-logo (visx/D3) | `components/plots/MotifLogo.tsx` |
| `structure_3d` (protein/NA/complex) | **Mol\*** | `components/structure/StructureViewer3D.tsx` |
| `guide_table` (CRISPR, **actionable**) | sortable table | `components/tables/GuideTable.tsx` |
| `origami` (**actionable**) | layout view + cadnano export | `components/origami/*` |

> Recommended libs (Mol\*, visx) are defaults; lock them in `specs/interface/*` before implementation
> and add the deps to `src/frontend/package.json` then.

## Confidence & uncertainty are visual

- Show per-residue confidence (pLDDT-style coloring) on structures; confidence bands on tracks/plots;
  contested/conflicting evidence is visibly marked, never silently averaged
  (`evidence_and_confidence.md`, `evidence_integration.md`).

## Actionable artifacts

- `guide_table` and `origami` are **review-gated**: render them as **candidates** with rationale +
  risks until approved (`human_review_policy.md`, `streaming_protocol.md` §8). Don't present a
  gated artifact as a recommendation pre-approval.

## Composition

- The `visualization` capability assembles multi-track/composite views from upstream results
  (`capability-subgraphs/visualization.md`); prefer composing typed artifacts over bespoke one-offs.

## Performance

- Heavy payloads load lazily via `storage_ref`; downsample/virtualize large tracks; render server-side
  when a payload is too big for the client (decide the split in `artifact_model.md`).

## Don't

- Don't render genomic positions without assembly/strand context.
- Don't inline multi-MB payloads in state/events — reference them.
- Don't invent ad-hoc artifact shapes; extend `artifact_model.md`'s taxonomy.

# visualization Subgraph

> Status: Draft v0.1. Capability: visualization (`FR-21`). Parent: `graph_spec.md` §5. Impl:
> `agent/subgraphs/visualization.py`, `services/visualization/`. Not actionable.

## Purpose

Render any capability result into an interactive, exportable artifact; assemble multi-track/composite
views.

## Input (Subtask)

One or more upstream results (evidence/artifacts) + a desired view type.

## Steps

1. **(light)** select artifact type for the data (track, locus plot, contact map, motif logo,
   structure, table) per `artifact_model.md`.
2. **(light/heavy)** transform data into the artifact payload schema; compose multi-track views where
   relevant.
3. **(light)** attach provenance/evidence links + export formats (PNG/SVG + underlying data).

## Outputs

- **artifacts:** typed, interactive artifacts (`artifact_model.md`); always linked back to source
  evidence/run (`FR-29`).

## Notes

This subgraph is often invoked as the terminal step of other capabilities/composed plans, not
standalone. Rendering contract is owned by `specs/interface/artifact_model.md` (data) and the
frontend components (presentation).

## Open questions

- Server-side vs client-side rendering split for heavy artifacts.
- Default composite views per capability.

## Related

`specs/interface/artifact_model.md` · `specs/services/visualization_service.md` ·
`specs/interface/genome_browser.md`.

# Inverse Design Service

> Status: Implemented v0.1. Capability: `FR-18c`. Implementation:
> `src/backend/cellxp/services/inverse_design/`. Methodology:
> `specs/biology/inverse_edit_design.md`.

The service accepts an explicit desired assay/readout effect, locus, organism/assembly, objective
weights, editor preference, and bounded search budget. An injectable backend proposes edits and
jointly assesses each candidate with the organism-appropriate forward oracle and CRISPR feasibility/
off-target tooling. The service computes a deterministic weighted score, identifies a Pareto set,
and retains the best partial candidates when the target is not reached.

Every candidate carries compounded confidence and provenance. The ranked candidate-edit artifact is
always actionable and therefore routes through `human_review_gate`; it is never presented as a
recommendation before approval. Empty search results, unsupported references, and backend failures
remain distinct service outcomes.

## Requirements

- **IDS-1** Search MUST stop at `max_iterations` and `max_candidates`.
- **IDS-2** Every candidate MUST include forward effect, collateral, off-target, and feasibility
  terms plus confidence and provenance.
- **IDS-3** Outputs MUST be marked actionable and review-gated.
- **IDS-4** Unsupported organism/assembly pairs MUST NOT silently fall back to a human oracle.
- **IDS-5** Failure to reach the target MUST return the best partial/Pareto candidates and gap.

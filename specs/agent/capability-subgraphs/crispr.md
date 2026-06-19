# crispr Subgraph

> Status: Draft v0.1. Capability: CRISPR design (`FR-15`). **Actionable → review-gated
> (`FR-25/26`).** Parent: `graph_spec.md` §5. Impl: `agent/subgraphs/crispr.py`, `services/crispr/`.
> Methodology: `specs/biology/crispr_design.md`.

## Purpose

Design gRNAs (and base/prime edits) for a target with on-/off-target scoring and editing-system
trade-offs.

## Input (Subtask)

A target gene/region (+ organism + assembly), desired edit type, optional editing system/PAM
constraints.

## Steps

1. **(light)** resolve target → coordinates + sequence context; pick candidate PAM sites
   (organism/Cas-aware).
2. **(heavy)** on-target scoring (**Rule Set 2/Azimuth**); base/prime outcome (**BE-Hive**,
   **PRIDICT**) when relevant (catalog §10).
3. **(heavy)** off-target: enumerate (**Cas-OFFinder**) + score specificity (**CFD**).
4. **(light)** rank guides; assemble sortable guide table with PAM/strand/score context.
5. **gate:** mark output `is_actionable` → `human_review_gate`.

## Outputs

- **evidence:** per-guide on/off scores, feasibility, editing-system rationale, confidence.
- **artifacts:** `guide_table` (actionable), sequence-context view.

## Actionable & gating

Always review-gated; pre-gate results are candidates with rationale (`human_review_policy.md`). Cas
variant/PAM and editing-system trade-offs: `specs/biology/crispr_design.md`.

## Organism notes

PAM availability, Cas compatibility, and codon/editing-window context are organism-specific (e.g.
*G. oxydans*). Respect circular bacterial coordinates.

## Open questions

- Default Cas variant per organism; guide count/ranking weights.

## Related

`human_review_policy.md` · `specs/biology/crispr_design.md` · catalog §10 ·
`capability-subgraphs/variant_effect.md` (inverse design composition).

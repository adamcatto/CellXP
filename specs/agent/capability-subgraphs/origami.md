# origami Subgraph

> Status: Draft v0.1. Capability: DNA origami / nanotech (`FR-19`). **Actionable → review-gated.**
> Parent: `graph_spec.md` §5. Impl: `agent/subgraphs/origami.py`, `services/origami/`. Methodology:
> `specs/biology/dna_origami.md`.

## Purpose

Design DNA-origami nanostructures: scaffold routing, staple design, constraint checking, and
cadnano-compatible export.

## Input (Subtask)

A target shape/constraints + scaffold sequence/length.

## Steps

1. **(light)** parse target shape + constraints.
2. **(heavy)** scaffold routing / wireframe (**DAEDALUS/PERDIX/TALOS/ATHENA**); staple generation;
   **cadnano/scadnano** layout (catalog §16).
3. **(heavy, optional)** simulate stability (**oxDNA**) / mechanics (**CanDo**).
4. **(light)** constraint/QC checks; emit layout + export files.
5. **gate:** mark output `is_actionable` → `human_review_gate`.

## Outputs

- **evidence:** design parameters, QC/stability results, confidence.
- **artifacts:** `origami` layout + cadnano export (actionable), simulation summary.

## Actionable & gating

Review-gated as a buildable design; presented as candidate with rationale + risks pre-approval.

## Open questions

- Default routing tool per shape class; simulation by default vs on request.

## Related

`specs/biology/dna_origami.md` · catalog §16 · `human_review_policy.md`.

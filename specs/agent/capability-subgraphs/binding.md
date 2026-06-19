# binding Subgraph

> Status: Draft v0.1. Capability: binding-site prediction (`FR-17`). Parent: `graph_spec.md` §5.
> Impl: `agent/subgraphs/binding.py`, `services/binding/`. Methodology:
> `specs/biology/binding_site_prediction.md`. Not actionable.

## Purpose

Predict TF binding, footprints, and occupancy/binding deltas for a sequence (± a variant).

## Input (Subtask)

A sequence/interval (+ organism), optional variant, optional TF set.

## Steps

1. **(light)** prepare sequence context (+ variant allele if present).
2. **(heavy)** binding/accessibility prediction: **AlphaGenome heads** (mammalian),
   **ChromBPNet** footprints; motif scan via **FIMO + JASPAR** (catalog §6).
3. **(light)** if a variant is present → compute occupancy/binding **deltas** (gain/loss of sites).
4. **(light)** emit motif/track artifacts.

## Outputs

- **evidence:** predicted binding/occupancy, motif hits, variant deltas, confidence.
- **artifacts:** `motif_logo`, binding `genome_track`, delta plot.

## Organism notes

Mammalian binding heads are human/mouse only; for other clades use motif scanning + Evo 2-based
priors.

## Open questions

- Default TF panel; motif DB version pinning.

## Related

`specs/biology/binding_site_prediction.md` · catalog §6 · `variant_effect.md` · `task_patterns.md` §2.

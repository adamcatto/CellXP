# variant_effect Subgraph

> Status: Draft v0.1. Capability: variant effect (`FR-13`). Parent: `graph_spec.md` §5. Impl:
> `agent/subgraphs/variant_effect.py`, `services/alphagenome/`. Methodology:
> `specs/biology/variant_effect_prediction.md`. Not actionable.

## Purpose

Predict the regulatory/functional effect of coding & non-coding variants, tissue/assay-resolved where
the model supports it.

## Input (Subtask)

A variant (+ organism + assembly) and optional tissue/assay/cell-type context, referenced from
`entities`/`normalized_inputs`.

## Steps

1. **(light)** resolve variant → canonical coordinates + genomic context (gene, regulatory element).
2. **(heavy)** call the effect oracle (organism-appropriate, `tool_use_policy.md` §4):
   **AlphaGenome** (mammalian) or **Evo 2** (other clades); splice variants → **SpliceAI** (catalog
   §1/§2).
3. **(light)** extract per-assay/tissue deltas; interpret magnitude/direction.
4. **(light)** emit a delta-track / effect artifact.

## Outputs

- **evidence:** per-assay deltas, nearest gene/regulatory context, confidence.
- **artifacts:** `genome_track`/delta plot (`artifact_model.md`).

## Organism notes

Mammalian → AlphaGenome; non-mammalian → Evo 2. Never apply mammalian heads to bacteria
(`coordinate_systems.md`, `task_patterns.md` §1).

## Open questions

- Report AlphaGenome + Evo 2 both for human variants, or pick one?
- Default tissue/assay set when unspecified.

## Related

`specs/biology/variant_effect_prediction.md` · `tool_use_policy.md` · catalog §1/§2 ·
`binding.md` (occupancy deltas) · `gwas.md` (corroboration).

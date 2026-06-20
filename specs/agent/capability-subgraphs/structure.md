# structure Subgraph

> Status: Draft v0.1. Capability: structure prediction (`FR-18`; protein design hooks `FR-18a`).
> Parent: `graph_spec.md` §5. Impl: `agent/subgraphs/structure.py`, `services/structure/`.
> Methodology: `specs/biology/structure_prediction.md`. Not actionable (design output → gated).

## Purpose

Predict 3D structure (protein, nucleic-acid, complex), DNA shape, nucleosome positioning, and
chromatin contacts, with per-residue confidence.

## Input (Subtask)

A sequence (protein/NA) or interval (+ organism/assembly for genomic structure), complex/ligand spec
if relevant.

## Steps

1. **(light)** classify the structure task (monomer / complex / NA / shape / contacts).
2. **(heavy)** predict: **ESMFold** (fast single-seq), **Boltz-2** (complex/ligand/NA + affinity)
   (catalog §3/§4); DNA shape via **DNAshapeR**, contacts via **Orca** (catalog §5). Runs as a job.
3. **(light)** attach per-residue confidence (pLDDT-style); flag low-confidence regions.
4. **(light)** emit 3D / contact-map / shape-track artifacts.

## Outputs

- **evidence:** structure + confidence, contacts/shape, (Boltz) affinity, citations.
- **artifacts:** `structure_3d`, `contact_map`, shape `genome_track`.

## Actionable note

Pure structure prediction is analysis. **Protein/sequence design** (`FR-18a`: LigandMPNN,
RFdiffusion, catalog §12) is actionable/generative → review-gated; handled here or in a future
`design` subgraph.

## Organism notes

Structure models are largely organism-agnostic (sequence-based); genomic-structure (contacts/shape)
respects assembly + circularity.

## Open questions

- ESMFold vs Boltz-2 default per input size/complexity. *(X3 decision: single protein
  monomer → ESMFold; any ligand, multiple chains, `complex`, or `nucleic_acid` → Boltz-2;
  a monomer exceeding the ESMFold length ceiling returns a validation error pending a
  chunking/Boltz-2 reroute strategy. See `select_structure_model` in `services/structure/`.)*
- Auto-reroute oversized ESMFold monomers to Boltz-2 / a chunking strategy instead of
  returning a validation error (X3 returns a validation error for now).
- Bare-interval genomic structure defaults to `contacts`; a `dna_shape` request needs an
  explicit subtask `kind` hint — revisit whether the planner should disambiguate.
- Where protein design lives (extend here vs new `design` subgraph). *(X3 scope is
  prediction only; generative design FR-18a stays review-gated, deferred to X6.)*

## Related

`specs/biology/structure_prediction.md` · catalog §3/§4/§5/§12 · `human_review_policy.md` (design).

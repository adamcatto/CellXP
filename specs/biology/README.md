# Biology Methodology Specs

These specs define **how each scientific capability works programmatically** — the typed inputs,
the models/tools invoked, the data **transforms** in the pipeline, and the typed outputs (evidence +
artifacts). They are the methodology contract that sits between:

- the **capability subgraph** (orchestration: `specs/agent/capability-subgraphs/*`),
- the **service** (deployment/interface: `specs/services/*`), and
- the **model catalog** (what models exist: `documentation/reference/external_models_and_services.md`,
  cited as *catalog §N*).

Focus is on **I/O and transforms**, not biological tutorial content.

## Index

| Spec | Capability (FR) | Catalog |
|---|---|---|
| `variant_effect_prediction.md` | FR-13 | §1, §2, §8 |
| `gwas_qtl_lookup.md` | FR-14 | §9, §8 |
| `crispr_design.md` | FR-15 | §10 |
| `inverse_edit_design.md` | FR-18c | §11 (+§1, §10) |
| `sequence_annotation.md` | FR-16 | §7, §15 |
| `binding_site_prediction.md` | FR-17 | §6, §1 |
| `structure_prediction.md` | FR-18 | §3, §4, §5 |
| `protein_function_and_design.md` | FR-18a | §15, §12, §3 |
| `metabolites_and_small_molecules.md` | FR-18b | §13, §14 |
| `networks_systems_analysis.md` | FR-18d | §14 |
| `dna_origami.md` | FR-19 | §16 |
| `supported_species.md` | reference | — |
| `supported_assays.md` | reference | — |

## Shared conventions (apply to every spec)

- **Typed I/O.** Inputs/outputs reference the domain models in `specs/agent/state_schema.md` §7/§9
  (`SequenceInput`, `Variant`, `GenomicInterval`, `Entity`, `EvidenceItem`, `ArtifactRef`) and
  `src/backend/.../domain/models.py`. Schemas shown here are sketches; the binding contract is the
  domain model.
- **Coordinates.** Every positioned input/output carries organism + assembly + 0-based/half-open
  convention internally (`coordinate_systems.md`); circular bacterial genomes are handled, not
  assumed-linear. A silent coordinate error is a P0 defect (`NFR-3`).
- **Organism-appropriate models.** Model selection MUST respect organism applicability
  (`supported_species.md`, `tool_use_policy.md` §4) — e.g. AlphaGenome heads for mammalian, Evo 2 for
  other clades. This is a 100% guardrail (`success_metrics.md`).
- **Steps & provenance.** Each model/tool/transform call is a `Step` with tool+version+params+IO refs
  (`state_schema.md` §8); every output carries `Confidence` + `Provenance`
  (`evidence_and_confidence.md`).
- **Light vs heavy.** Pipeline steps are tagged `light` (CPU prep/post) or `heavy` (GPU/long; async
  job) per `harness_and_context_engineering.md` / `control-flow/concurrency.md`.
- **Actionable.** Capabilities producing buildable/wet-lab output (CRISPR, inverse design, protein
  design, origami) mark outputs `is_actionable` → human-review gate (`human_review_policy.md`).

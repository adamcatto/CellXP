# Networks & Systems-Level Analysis — Methodology & Programmatic Contract

> Capability: FR-18d. Subgraph: composed (traverses `annotation`/`variant_effect`/`binding` + systems
> tools). Service: `services/*` + GEM/GRN tooling. Catalog: §14 (COBRApy, CarveMe, ModelSEED,
> GRNBoost2/SCENIC, ABC model). Conventions: `specs/biology/README.md`. Cookbook:
> `documentation/explanation/task_patterns.md` §2–§6.

## 1. Task

Infer and analyze biological networks and propagate perturbations across scales:
(a) **GRN** inference + variant-impact propagation; (b) **metabolic network** reconstruction (genome →
genome-scale model) + flux analysis; (c) **variant → metabolism** (how variants shift flux/yield,
esp. in bacterial strains).

## 2. Inputs

```python
class NetworkRequest(BaseModel):
    mode: Literal["grn_infer","grn_variant_impact","gem_reconstruct","fba","variant_to_metabolism"]
    organism: str
    assembly: str | None = None
    genome_ref: GenomeRef | None = None       # for GEM reconstruction
    expression_ref: str | None = None         # matrix for GRN inference
    variants: list[Variant] | None = None     # for impact modes
    objective: str | None = None              # FBA objective (e.g. biomass, target metabolite)
    media: dict[str, float] | None = None      # exchange constraints for FBA
```

## 3. Models/tools & selection

| Mode | Tools | Catalog |
|---|---|---|
| GEM reconstruction | **CarveMe / ModelSEED** (from annotated genome) | §14 |
| Flux analysis | **COBRApy** (FBA/FVA) | §14 |
| GRN inference | **GRNBoost2 / SCENIC** (expression) ; **ABC model** (enhancer→gene) | §14 |
| Forward effect oracles (edges/impact) | AlphaGenome/Evo 2, binding | §1/§6 |

## 4. Pipeline (transforms)

**GEM reconstruct → FBA**
1. **(heavy)** annotate genome (`sequence_annotation.md`) → gene/enzyme set (EC via CLEAN).
2. **(heavy)** build GEM (CarveMe/ModelSEED): genes→reactions→metabolites; set media/exchange.
3. **(heavy)** FBA/FVA (COBRApy) for the objective → flux distribution, growth, yields.

**GRN infer / variant impact**
1. **(heavy)** infer edges (GRNBoost2/SCENIC from expression; or ABC for enhancer→gene).
2. **(heavy)** for a variant: score its effect on TF binding/regulatory activity (forward oracle,
   `binding_site_prediction.md`/`variant_effect_prediction.md`) → perturb edge weights.
3. **(light)** propagate perturbation downstream; identify dysregulated targets/pathways.

**Variant → metabolism**
1. map variant → affected gene/enzyme (effect oracle) → reaction(s) in the GEM →
2. constrain/knock-down the reaction → re-run FBA → Δ flux/growth/yield.

Each chain **records compounded uncertainty** across stages (`evidence_and_confidence.md`,
`evidence_integration.md` §8).

## 5. Outputs

```python
class NetworkResult(BaseModel):
    grn: GraphRef | None                      # nodes/edges (+weights)
    gem_ref: str | None                       # SBML model storage_ref
    flux: list[ReactionFlux] | None           # FBA solution
    perturbation: list[PerturbationEffect] | None  # Δ downstream / Δ flux
    confidence: Confidence                     # compounded across chain
    provenance: Provenance                     # all stage tools/versions
```

- **Artifacts:** network graph, flux map/pathway view, GEM file (SBML).
- **Evidence:** edges/flux/perturbation claims with per-stage provenance and compounded confidence.

## 6. Applicability

GEMs are especially strong for **microbes** (e.g. *G. oxydans* strain engineering); GRN inference
needs expression data. Mammalian vs prokaryote oracle selection applies at each forward step
(`supported_species.md`).

## 7. Failure modes & edge cases

- Missing expression data for GRN → require/clarify.
- Infeasible FBA (no growth) → report infeasibility + likely constraint cause.
- Long chains: surface that confidence is bounded by the weakest stage.

## 8. Validation

Reconstruct/FBA against curated GEMs (e.g. known growth phenotypes); GRN edges vs known regulons;
provenance + compounded-confidence completeness.

## 9. Related

`variant_effect_prediction.md` · `binding_site_prediction.md` · `sequence_annotation.md` ·
`metabolites_and_small_molecules.md` · `inverse_edit_design.md` · `task_patterns.md`.

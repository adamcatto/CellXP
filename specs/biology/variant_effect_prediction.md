# Variant Effect Prediction — Methodology & Programmatic Contract

> Capability: FR-13. Subgraph: `variant_effect`. Service: `services/alphagenome/`. Catalog: §1
> (AlphaGenome, Evo 2), §2 (SpliceAI), §8 (VEP/annotation). Not actionable. Conventions:
> `specs/biology/README.md`.

## 1. Task

Given a variant (or set), predict its regulatory/functional effect as **deltas** on model readouts
(expression, chromatin, splicing, binding) — tissue/assay-resolved where the model supports it
(`supported_assays.md`).

## 2. Inputs

```python
class VariantEffectRequest(BaseModel):
    variants: list[Variant]                 # chrom,pos,ref,alt (+rsid/hgvs) — domain/models.py
    organism: str                           # required (FR-11)
    assembly: str                           # required; variants must match
    assays: list[str] | None = None         # subset of supported_assays; default = model default set
    tissues: list[str] | None = None        # tissue/cell-type context where supported
    window_bp: int | None = None            # context window; default = model max
```

Preconditions: organism+assembly resolved (`entity_resolver`); variant coordinates validated against
the assembly; alleles match the reference base at `pos` (else flag).

## 3. Models & selection

| Need | Model | Catalog | Organism |
|---|---|---|---|
| Regulatory/functional effect, assay/tissue-resolved | **AlphaGenome** | §1 | mammalian (human/mouse) |
| Long-range / cross-species / microbial variant scoring | **Evo 2** | §1 | non-mammalian, microbial |
| Splice-altering effect | **SpliceAI** | §2 | mammalian |
| Known-variant annotation (corroboration) | VEP/dbNSFP | §8 | per DB |

Selection rule: organism class decides the oracle (`tool_use_policy.md` §4). Mammalian → AlphaGenome
(+ SpliceAI for splice questions); other clades → Evo 2. Never apply mammalian heads to bacteria.

## 4. Pipeline (transforms)

1. **(light) Coordinate framing** — normalize variant to internal 0-based; locate the gene/regulatory
   context; choose the sequence window centered per model requirement.
2. **(light) Sequence extraction + alleles** — pull reference window from the assembly; build the
   **ref** and **alt** sequences by substituting the allele; apply strand/reverse-complement as the
   model expects; encode (one-hot/tokenize) per model.
3. **(heavy) Forward passes** — run the model on ref and alt (and per requested assay/tissue head);
   for Evo 2, compute likelihood/embedding-based scores.
4. **(light) Delta computation** — `delta = f(alt) − f(ref)` per assay/tissue; summarize
   magnitude/direction; flag the most affected tracks.
5. **(light) Splice branch** — if splice-relevant, run SpliceAI; merge donor/acceptor gain/loss.
6. **(light) Artifact build** — assemble a delta-track / per-assay effect plot.

## 5. Outputs

```python
class VariantEffectResult(BaseModel):
    per_variant: list[VariantEffect]        # one per input variant

class VariantEffect(BaseModel):
    variant_id: str
    deltas: list[AssayDelta]                 # {assay, tissue?, value, direction}
    top_effects: list[AssayDelta]            # ranked
    nearest_gene: str | None
    regulatory_context: str | None
    confidence: Confidence
    provenance: Provenance
```

- **Evidence:** one `EvidenceItem` per salient delta (claim = "variant X reduces accessibility in
  tissue Y"), with value + confidence + provenance.
- **Artifacts:** `genome_track` (delta) and/or per-assay effect plot (`artifact_model.md`).
- **Confidence:** model-reported where available; otherwise qualitative band by effect size + model
  reliability for that organism/assay.

## 6. Organism applicability

See `supported_species.md`. Mammalian assays only via AlphaGenome; microbial/non-model via Evo 2 with
appropriately framed (often circular) coordinates.

## 7. Failure modes & edge cases

- Ref allele mismatch at `pos` → flag, do not silently proceed.
- Variant outside any modeled context → return "no modeled effect" with reason.
- Multi-allelic / indels → handle per model capability; note truncation if window-limited.
- Organism without a valid oracle → return clear "unsupported organism for this capability".

## 8. Validation

Golden variants with known direction (e.g. eQTL sign, ClinVar) → direction-agreement metric;
coordinate validation tests (`NFR-3`); organism-appropriate selection = 100% (`success_metrics.md`).

## 9. Related

`binding_site_prediction.md` (occupancy deltas) · `gwas_qtl_lookup.md` (corroboration) ·
`inverse_edit_design.md` (uses this as the forward oracle) · `specs/services/alphagenome_service.md` ·
`supported_assays.md`.

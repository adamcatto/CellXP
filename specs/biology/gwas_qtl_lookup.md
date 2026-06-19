# GWAS / QTL Lookup — Methodology & Programmatic Contract

> Capability: FR-14. Subgraph: `gwas`. Service: `services/gwas/`. Catalog: §9 (GWAS Catalog, Open
> Targets, eQTL Catalogue/GTEx, SuSiE, coloc, PLINK), §8. Not actionable. Conventions:
> `specs/biology/README.md`.

## 1. Task

For a variant/locus/gene, retrieve trait associations and statistical-genetics evidence: known
associations, LD, fine-mapping (credible sets), and colocalization with molecular QTLs.

## 2. Inputs

```python
class GwasRequest(BaseModel):
    subject: Locus | Variant | GeneRef       # one of; +organism+assembly
    organism: str
    assembly: str
    traits: list[str] | None = None          # restrict to traits/phenotypes
    tissues: list[str] | None = None         # for QTL/coloc
    ld_population: str | None = None          # e.g. EUR/EAS for LD
    do_finemap: bool = True
    do_coloc: bool = True
```

Preconditions: human-centric resources (most data is human); for non-human, return "limited/no data"
rather than mismatched results.

## 3. Models/tools & selection

| Need | Tool | Catalog |
|---|---|---|
| Trait associations | GWAS Catalog, Open Targets Genetics | §9 |
| Molecular QTL | eQTL Catalogue / GTEx | §9 |
| LD | PLINK / reference LD panel | §9 |
| Fine-mapping (credible sets) | **SuSiE** | §9 |
| Colocalization | **coloc** | §9 |

## 4. Pipeline (transforms)

1. **(light) Resolve subject → coordinates** (gene→region, rsID→locus) in the assembly.
2. **(light) Association query** — fetch associations overlapping the locus from GWAS Catalog / Open
   Targets; normalize to a common record (trait, effect size/beta, p, allele, study).
3. **(light/heavy) LD expansion** — compute/lookup LD around lead variants (population-specific).
4. **(heavy) Fine-mapping** — run SuSiE on regional summary stats → credible sets + PIPs.
5. **(heavy) Colocalization** — run coloc between GWAS signal and eQTL signal per tissue → posterior
   (H4) of shared causal variant.
6. **(light) Rank + artifact** — rank associations/credible sets; build a locus plot.

## 5. Outputs

```python
class GwasResult(BaseModel):
    associations: list[Association]          # {trait, beta, p, allele, study, citation}
    credible_sets: list[CredibleSet]         # {variants, pip, region}
    coloc: list[ColocResult]                 # {trait, tissue, h4}
    ld: list[LdPair] | None
    confidence: Confidence
    provenance: Provenance
```

- **Evidence:** associations, credible sets, coloc results — each with citation (study accession/PMID)
  and confidence.
- **Artifacts:** `locus_plot`; ranked association/credible-set table.
- **Confidence:** from study power, p-values, PIP, and coloc H4; qualitative band rolled up.

## 6. Organism applicability

Primarily human; some non-human GWAS exist but coverage is sparse. Non-human request → explicit
data-availability note (`supported_species.md`).

## 7. Failure modes & edge cases

- No associations at locus → report "no known associations" (not an error).
- Mismatched assembly between query and study → liftover or flag.
- Cross-population LD mismatch → state the population used.

## 8. Validation

Known trait-locus pairs as golden seeds; citation-resolution checks (`success_metrics.md` D2);
liftover correctness (`NFR-3`).

## 9. Related

`variant_effect_prediction.md` (mechanistic corroboration) · `networks_systems_analysis.md` ·
`specs/services/gwas_service.md` · `capability-subgraphs/gwas.md`.

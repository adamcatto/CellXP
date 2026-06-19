# GWAS / QTL Service

> Status: Draft v0.1. Logical service contract for statistical-genetics lookup and analysis. Impl:
> `src/backend/cellxp/services/gwas/`. Methodology:
> `specs/biology/gwas_qtl_lookup.md`. Catalog:
> `documentation/reference/external_models_and_services.md` §8, §9.

## 1. Purpose

Provide a stable boundary for trait associations, QTL evidence, LD expansion, fine-mapping, and
colocalization. The service turns normalized variants, genes, and loci into cited statistical
evidence plus locus artifacts.

## 2. Operations

```python
class GwasService(Service):
    def lookup_associations(self, request: GwasRequest) -> ServiceResult[GwasResult]: ...
    def compute_ld(self, request: LdRequest) -> ServiceResult[LdResult]: ...
    def fine_map(self, request: FineMapRequest) -> ServiceResult[FineMapResult]: ...
    def coloc(self, request: ColocRequest) -> ServiceResult[ColocBatchResult]: ...
```

`lookup_associations` MAY orchestrate the other operations when `do_finemap` or `do_coloc` is set.
Heavy statistical jobs dispatch through the job layer.

## 3. Inputs

The service accepts `Variant`, `GenomicInterval`, or gene references resolved by the reference
service. Human data resources dominate; non-human requests MUST return an explicit data-availability
note rather than silently projecting human evidence onto another organism.

Inputs MUST include:

- organism and assembly for positioned subjects;
- trait/tissue/population filters where requested;
- source dataset releases, or `default` to use registry-pinned releases;
- liftover details when input assembly differs from a dataset assembly.

## 4. Data Sources & Tools

The registry provides adapters for GWAS Catalog, Open Targets Genetics, eQTL Catalogue/GTEx, gnomAD,
dbSNP, ClinVar, LD panels, SuSiE, coloc, PLINK/LDSC-class tools. Each adapter declares release,
license/access mode, organism coverage, and citation metadata.

## 5. Outputs & Artifacts

| Output | Artifact type | Storage |
|---|---|---|
| associations | `association_table` | inline top rows + object for full table |
| credible sets / PIPs | `credible_set_table`, `locus_plot` | object for full regional data |
| colocalization | `coloc_table`, `locus_plot` | inline summary + object payload |
| LD matrix | `ld_matrix`, `locus_plot` | object storage |

Reports MUST distinguish "no known association" from "query failed" and "resource lacks coverage."

## 6. Provenance & Confidence

Each evidence item records source database/tool, release, query coordinates, filters, population,
study accession/PMID where available, and any liftover transform. Confidence reflects p-values,
sample size/study power, PIP, coloc H4, LD-panel fit, and source directness.

## 7. Failure Modes

- no records: valid empty result with source coverage note;
- assembly mismatch: liftover or validation error, with provenance if lifted;
- population mismatch: warning and confidence downgrade;
- missing summary stats for fine-mapping/coloc: partial result, recoverable error;
- upstream API failure: recoverable `RunError` and any cached/local data returned.

## 8. Requirements

- **GWS-1** All database-backed claims MUST include source release and citation/accession metadata.
- **GWS-2** Human-only datasets MUST NOT be treated as evidence for non-human organisms.
- **GWS-3** Fine-mapping and colocalization outputs MUST expose their statistical assumptions and
  input datasets.
- **GWS-4** Locus plots and large tables MUST be persisted via object storage.
- **GWS-5** Empty evidence and unavailable evidence MUST be represented as distinct result states.

## 9. Related

`specs/biology/gwas_qtl_lookup.md` · `specs/services/reference_genome_service.md` ·
`specs/data/provenance_model.md` · `specs/interface/genome_browser.md`.

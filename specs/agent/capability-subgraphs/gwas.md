# gwas Subgraph

> Status: Draft v0.1. Capability: GWAS/QTL (`FR-14`). Parent: `graph_spec.md` §5. Impl:
> `agent/subgraphs/gwas.py`, `services/gwas/`. Methodology: `specs/biology/gwas_qtl_lookup.md`.
> Not actionable.

## Purpose

Look up trait associations, LD, fine-mapping, and colocalization for a variant/locus/gene.

## Input (Subtask)

A variant/locus/gene (+ organism + assembly), optional trait/tissue.

## Steps

1. **(light)** resolve locus/gene → coordinates; map to study datasets.
2. **(light/heavy)** query GWAS Catalog, Open Targets, eQTL Catalogue/GTEx (catalog §9).
3. **(heavy)** fine-mapping (**SuSiE**) + colocalization (**coloc**); LD via PLINK where needed.
4. **(light)** rank associations / credible sets; emit a locus plot.

## Outputs

- **evidence:** associations, credible sets, eQTL/coloc results, allele frequencies, citations.
- **artifacts:** `locus_plot`, association/credible-set `guide_table`-style table.

## Organism notes

Human-centric data resources; for non-human organisms, availability is limited — return clear "no
data for this organism" rather than mismatched results.

## Open questions

- Default trait scope; which fine-mapper config.
- Cross-population LD handling.

## Related

`specs/biology/gwas_qtl_lookup.md` · catalog §9 · `variant_effect.md` (corroboration) · `rag.md`.

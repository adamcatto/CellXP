# rag Subgraph

> Status: Draft v0.1. Capability: literature grounding / RAG (`FR-20`). Parent: `graph_spec.md` §5.
> Impl: `agent/subgraphs/rag.py`, `services/rag/`. Not actionable.
> Implementation checkpoint (2026-06-20): subgraph factory and default no-backend node implemented;
> live source adapters remain deployment work.

## Purpose

Retrieve and cite primary literature and database records that support (or contest) the answer.

## Input (Subtask)

A claim/topic/entity to ground; optional recency/source constraints.

## Steps

1. **(light)** formulate queries from entities/claims.
2. **(light/heavy)** retrieve: **PubMed/PMC**, bioRxiv/medRxiv, plus structured DBs (UniProt,
   Reactome/KEGG/GO) (catalog §17). Several available via MCP servers (`mcps/`).
3. **(heavy)** rank + extract supporting passages; deduplicate.
4. **(light)** produce citations + claim-linked evidence.

## Outputs

- **evidence:** literature/database items with citations (DOI/PMID/accession), `source_kind`,
  confidence.
- **artifacts:** citation set (linked into the report).

## Notes

RAG evidence feeds `evidence_integration.md` for corroboration/conflict handling. Citation validity is
a tracked metric (`success_metrics.md` D2).

## Open questions

- Default corpora + recency weighting; passage-extraction model.
- Independence handling when a DB and a paper report the same finding.

## Related

`evidence_integration.md` · catalog §17 · `specs/services/rag_service.md`.

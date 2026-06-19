# entity_resolver Node

> Status: Draft v0.1. Node 4. Parent: `graph_spec.md` §4, `routing_policy.md` §4, `state_schema.md`
> §7. Impl: `agent/nodes/entity_resolver.py`, `services/reference/*`. LLM + reference tools.

## Purpose

Resolve the biological entities a query refers to (genes, variants, intervals, proteins, metabolites,
organism, assembly) into canonical, cross-referenced `Entity` objects — or ask the user when
ambiguous.

## Reads → Writes

- **Reads:** `normalized_inputs`, `user_query`, `intent`.
- **Writes:** `entities` (merge-by-id), `clarifications` (merge-by-id); may update
  `normalized_inputs.organism/assembly`.

## Behavior

1. Resolve identifiers against reference services (Ensembl/UCSC/NCBI/UniProt; `services/reference/`):
   gene symbol→IDs, rsID→locus, accession→record.
2. **Establish organism + assembly** — required before any coordinate-dependent work (`FR-11`,
   `coordinate_systems.md`). If absent and consequential → emit a **blocking** `Clarification`.
3. Disambiguate: if a symbol/name maps to multiple entities, populate `Entity.ambiguity` and ask
   (one targeted question, batched; `FR-7`).
4. Cross-reference DBs into `Entity.refs`; mark `resolved=true/false`.

## Errors / edge cases

- Unknown identifier → unresolved entity + clarification or graceful note.
- Conflicting organism/assembly between inputs → flag and ask.
- Safe low-stakes inference allowed with an explicit recorded assumption.

## Prompt

`agent/prompts/entity_resolver.md`.

## Open questions

- When to auto-infer assembly vs always ask (per-organism defaults).
- Caching resolved entities across turns within a run.

## Related

`routing_policy.md` §4 · `coordinate_systems.md` · `state_schema.md` §7 ·
`specs/services/reference_genome_service.md`.

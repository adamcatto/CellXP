# input_normalizer Node

> Status: Draft v0.1. Node 1. Parent: `graph_spec.md` §4, `state_schema.md` §7. Impl:
> `agent/nodes/input_normalizer.py`. Deterministic (no LLM).

## Purpose

Turn heterogeneous `raw_inputs` (free text, pasted sequences, uploaded files, identifiers) into a
validated, typed `NormalizedInputs` object that downstream nodes can rely on.

## Reads → Writes

- **Reads:** `raw_inputs`, `user_query`.
- **Writes:** `normalized_inputs` (last-write-wins), may append `errors`, may set `messages`.

## Behavior

1. Detect input kind per item: text, FASTA/sequence, variant (rsID/HGVS/VCF-ish), interval, file
   (resolve `file_ref` from object store), identifier (gene symbol/accession).
2. Parse + validate: alphabet (DNA/RNA/protein), FASTA structure, variant syntax, interval bounds.
3. Normalize to canonical forms: sequences (uppercase, alphabet-tagged), variants/intervals to the
   canonical coordinate representation (`coordinate_systems.md`) — **without** assuming organism/
   assembly (that is `entity_resolver`'s job; record what's present).
4. Record `warnings` for lossy/ambiguous parses; raise actionable validation `errors` for malformed
   input (`FR-10`).

## Errors / edge cases

- Unparseable file/sequence → recoverable error + user-facing message; do not silently drop.
- Oversized upload → reject with limit (config; `FR-12`).
- Mixed alphabets / ambiguous IUPAC codes → flag, keep, annotate.

## Open questions

- Size limits + accepted file types (defer to config/`api_contracts.md`).
- Auto-detect vs require explicit format hints for pasted sequences.

## Related

`state_schema.md` §7 · `coordinate_systems.md` · `entity_resolver.md` · `api_contracts.md`.

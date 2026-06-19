# Coordinate Systems

> Status: Draft v0.1 — explanation, and a **correctness invariant**. How CellXP represents
> and validates genomic coordinates, assemblies, and strands so that a silent positional error can
> never occur. Enforced by `domain/coordinates.py`, `domain/validators/{coordinates,assembly,
> species}.py`, and tested by `tests/unit/test_coordinate_validation.py`. A silent coordinate error
> is a release-blocking P0 (`NFR-3`); target error rate is **zero** (`success_metrics.md` D1).

## 1. Why this is a first-class concern

"Coordinates are sacred" (`mission.md` §5). A variant placed on the wrong assembly, the wrong strand,
or off-by-one can send a researcher to the wrong locus and invalidate an edit or interpretation —
that is both a correctness and a safety failure (`safety_model.md` §6). So every positioned entity
makes its conventions **explicit and validated**; nothing is implicit.

## 2. The canonical positioned types

From `domain/models.py`:
- `GenomicInterval{species, assembly, chrom, start, end, strand}`
- `Variant{chrom, pos, ref, alt, assembly, rsid}`

Any entity with a genomic position MUST carry **species/organism + assembly** (and strand where
meaningful). Resolution that cannot establish organism+assembly pauses for clarification
(`routing_policy.md` §4, `FR-11`).

## 3. Conventions we standardize on

To avoid the classic 0-based/1-based and open/closed ambiguities, we fix an **internal canonical
representation** and convert at the edges:

- **Internal canonical:** 0-based, half-open intervals `[start, end)` (BED-style) for ranges; this is
  the representation used in `GenomicInterval` internally.
- **Variant positions:** stored with an explicit convention; user-facing variant notations (VCF is
  1-based; HGVS has its own rules) are converted to canonical on input and back on output.
- **Strand:** `+`, `-`, or `.` (unstranded/unknown); strand-aware operations must state how they use
  it.
- **Display:** user-facing output uses the convention familiar to the input format (e.g. 1-based
  inclusive for genome-browser-style display), with the convention labeled.

Every coordinate that crosses a boundary (input parse, model call, artifact, report) is converted
through a single, tested utility (`domain/coordinates.py`) — never ad hoc.

## 4. Assemblies & liftover

- Assembly is part of identity: `chr1:1000` means nothing without `GRCh38` vs `GRCh37` (or a mouse/
  bacterial assembly).
- Cross-assembly comparison requires explicit **liftover** (`services/reference/liftover.py`); the
  agent never compares positions across assemblies without it, and records the liftover in provenance.
- Contig/chromosome naming differences (`chr1` vs `1`, RefSeq accessions) are normalized via the
  reference service (`services/reference/`).

## 5. Organism-specific realities

- **Mammalian** (human/mouse): linear chromosomes, standard assemblies; the home turf of most
  reference tooling.
- **Bacterial / archaeal** (e.g. *G. oxydans*): genomes are often **circular**, single- or
  few-replicon, gene-dense, intron-poor, operon-organized. Canonical handling must support **circular
  coordinates** (wrap-around intervals/origin crossing) and not assume linear-chromosome semantics
  (`mission.md` §4). Model input framing respects this (`tool_use_policy.md` §5).
- The system must not inherit human-centric assumptions silently when operating on other clades.

## 6. Validation rules (enforced)

`domain/validators/*` enforce, at minimum:
- `0 ≤ start ≤ end` (canonical), within contig bounds for the named assembly;
- `chrom`/contig exists in the named assembly;
- `strand ∈ {+, -, .}`;
- assembly/species are recognized and mutually consistent;
- variant `ref` matches the reference base(s) at `pos` for the named assembly (reference-allele
  check) where feasible;
- circular-genome intervals are only allowed for assemblies declared circular.
Validation failures are actionable errors surfaced to the user (`FR-10`), never silently corrected.

## 7. Provenance & invariants

- Every coordinate transformation (parse, liftover, convention conversion, strand flip) is recorded
  so results are reproducible and auditable (`FR-24`, `evidence_and_confidence.md`).
- Invariant: **no result depends on an unstated coordinate assumption.** If an assumption is made
  (e.g. default assembly), it is explicit in the answer and the trace.

## 8. Testing & guardrail

`tests/unit/test_coordinate_validation.py` (and `test_variant_normalization.py`) cover convention
round-trips, assembly checks, reference-allele checks, and circular handling. Coordinate-error rate
is a zero-tolerance guardrail in CI (`success_metrics.md` D1/§8).

## 9. Related specs

`specs/agent/state_schema.md` (positioned entities) · `specs/agent/tool_use_policy.md` §5
(input framing) · `specs/services/reference_genome_service.md` · `specs/biology/*` ·
`safety_model.md` §6 · `specs/product/product_requirements.md` (`NFR-3`).

# Evidence & Confidence

> Status: Draft v0.1 — explanation. The semantics behind every claim CellXP makes:
> what counts as evidence, how provenance is recorded, and how confidence is expressed and combined.
> Binding shapes are in `specs/agent/state_schema.md` §9; integration rules in
> `specs/agent/evidence_integration.md`; persistence in `specs/data/provenance_model.md`.

## 1. Why this exists

Two of the product's core principles are "evidence-grounded by default" and "confidence is explicit"
(`mission.md` §5). This doc defines what those mean concretely so every spec uses the same vocabulary.

## 2. What is evidence

An **evidence item** is a single, attributable basis for a claim. Kinds (`source_kind`):

| Kind | Examples | Typical reliability |
|---|---|---|
| `measurement` (experimental) | assay readout, validated experimental record | highest |
| `database` | GWAS Catalog, ClinVar, UniProt, GTEx record | high |
| `literature` | a cited paper/preprint passage (RAG) | varies — depends on study |
| `model` | AlphaGenome/Evo2/ESMFold/Boltz prediction | varies — depends on model + applicability |
| `computation` | deterministic calc (e.g. GC content, coordinate mapping) | high if inputs correct |

Reliability is a *prior* on the kind; the actual weight also depends on directness, applicability
(e.g. organism), and corroboration (`evidence_integration.md`).

## 3. Provenance (what we always record)

Every evidence item carries provenance sufficient to **reproduce and audit** it (`FR-24`):
tool/source identity + **version**, parameters, the (normalized) inputs used, a pointer to the
output, citations (DOI/PMID/accession/URL) for data/literature, and a timestamp. No substantive claim
ships without it; provenance completeness target ≥95% (`success_metrics.md` D2).

## 4. Confidence

Confidence is expressed as a `Confidence{band, score?, basis}`:

- **band** — `high | medium | low | unknown` (always present).
- **score** — optional `0..1` when a calibrated value exists (e.g. model probability, pLDDT-derived).
- **basis** — a short statement of *what the confidence rests on* (model applicability, agreement,
  sample size, etc.).

Rules:
- Every prediction MUST carry confidence (`FR-23`); 100% coverage (`success_metrics.md` D2).
- Prefer **calibrated** scores where models provide them; otherwise use qualitative bands with an
  explicit basis.
- Confidence must reflect **applicability**: a mammalian model applied at the edge of its domain is
  not "high" just because its raw score is (ties to organism-appropriate selection,
  `tool_use_policy.md` §4).
- **"unknown" / "insufficient evidence" is a valid, preferred answer** over confident fabrication
  (`mission.md` §5).

## 5. Combining evidence

When multiple items bear on one claim (`evidence_integration.md` §6–§7):
- **Corroboration** from *independent* sources raises confidence; shared-model/shared-data sources
  are not independent.
- **Conflicts** are surfaced, not averaged away; more-direct/higher-reliability evidence is preferred
  but dissent is reported in limitations.
- Per-claim confidence blends source reliability, directness, agreement, and native confidences.

## 6. Confidence across composed chains

For multi-step tasks (`task_patterns.md`), confidence **compounds** and is bounded by the weakest
load-bearing step; the limiting step is named, and intermediate evidence stays individually
inspectable so users see *where* uncertainty enters. Never present an end-to-end conclusion at the
confidence of its last step alone.

## 7. How it surfaces to the user

- Inline **citations** in the report map to evidence items (`state_schema.md` §11); each substantive
  sentence is traceable.
- A **confidence summary** + **limitations** accompany the answer.
- Artifacts link back to the evidence/run that produced them (`FR-29`).
- The run inspector exposes the full evidence/provenance chain (`FR-30`,
  `specs/interface/workspace_interface.md`).

## 8. Anti-patterns (disallowed)

- Asserting a substantive claim with no linked evidence.
- Reporting a single confidence for a long chain as if it were one step.
- Treating non-independent sources as corroboration.
- Hiding conflicting evidence.
- Silent coordinate/assembly assumptions affecting a result (see `coordinate_systems.md`).

## 9. Related specs

`specs/agent/state_schema.md` §9 · `specs/agent/evidence_integration.md` ·
`specs/data/provenance_model.md` · `specs/product/success_metrics.md` (D1/D2) ·
`specs/evaluation/provenance` rubric · `coordinate_systems.md`.

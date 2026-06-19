# evidence_integrator Node

> Status: Draft v0.1. Node 7. Parent: `graph_spec.md` §4, `evidence_integration.md`. Impl:
> `agent/nodes/evidence_integrator.py`, `domain/evidence.py`. Deterministic + light LLM for
> claim-grouping.

## Purpose

Reduce the raw `evidence` accumulated by subgraphs into a normalized, de-duplicated, reconciled set
with per-claim confidence and a citation map for the report.

## Reads → Writes

- **Reads:** `evidence` (append-only), `artifacts`, `entities`, `subtasks`.
- **Writes:** normalized/merged `evidence`, plus `final_report.citation_map`/`confidence_summary`
  inputs; flags for `critic`.

## Behavior

Runs the pipeline in `evidence_integration.md` §5: normalize → de-duplicate → group-by-claim →
reconcile (corroboration vs conflict) → weight/score → build citation map → flag gaps/conflicts.
Idempotent and re-runnable after replanning loops. Propagates compounded uncertainty for composed
chains (`evidence_integration.md` §8).

## Errors / edge cases

- Claim lacking complete provenance → drop, demote to labeled speculation, or flag (target ≥95%
  completeness, `success_metrics.md` D2).
- Conflicting evidence → keep both, mark `contested`, never silently average.

## Open questions

- Reliability weights per source kind/tool.
- LLM vs rules for claim clustering.

## Related

`evidence_integration.md` · `evidence_and_confidence.md` · `critic.md` · `report_generator.md`.

# critic Node

> Status: Draft v0.1. Node 9. Parent: `graph_spec.md` §4, `evidence_integration.md` §10. Impl:
> `agent/nodes/critic.py`, prompt `agent/prompts/critic.md`. LLM-backed.

## Purpose

Self-check the integrated evidence and draft answer before it reaches the user: catch unsupported
claims, ignored conflicts, overconfidence, and missing limitations.

## Reads → Writes

- **Reads:** integrated `evidence`, draft `final_report`, `confidence_summary`, flags.
- **Writes:** quality flags / limitations; may request replanning (`routing_policy.md` §9).

## Behavior

1. Verify every substantive claim has linked evidence with adequate provenance (`FR-22/24`).
2. Check that conflicts surfaced by the integrator are acknowledged (not silently dropped).
3. Check confidence language matches evidence strength (no overclaiming; chain confidence bounded by
   weakest step).
4. If a fillable gap exists and budget remains → request a replanning subtask; else → annotate
   `Report.limitations`.

## Errors / edge cases

- Runs once pre-report (current design; `graph_spec.md` §11). Avoid infinite critique/repl-loops via
  the revision cap.

## Open questions

- Once pre-report vs per-subtask critique.
- Whether critic can downgrade confidence directly vs only flag.

## Related

`evidence_integration.md` · `report_generator.md` · `routing_policy.md` §9 ·
`success_metrics.md` D1/D2.
